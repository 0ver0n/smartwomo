"""Backup/Restore V2.2 – Fix #2: vollständiges Backup/Restore aller Zustände.

Änderungen vs V2.1:
- `init_applied` wird jetzt im Backup gesichert
- `energy_snapshots` und `period_timestamps` sind Top-Level-Felder im Backup
  (nicht mehr in extra_meta verschachtelt → direkter Restore-Zugriff)
- `async_restore()` stellt ALLE Felder direkt wieder her (kein halbblinder Zustand)

Ehrliche Einschränkungen:
- `meter_mode` ist ein Laufzeit-Diagnostikwert, wird im nächsten Compute-Zyklus
  neu berechnet → nicht persistiert (macht keinen Sinn, würde nur veralten)
- `_debounce_task` ist ein Laufzeit-Objekt → nie persistiert
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from .const import DATA_ROOT, DATA_DIR_BACKUP, BACKUP_FILENAME, VERSION, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


def _backup_path(hass: HomeAssistant) -> str:
    return os.path.join(hass.config.config_dir, DATA_ROOT, DATA_DIR_BACKUP, BACKUP_FILENAME)


class BackupManager:
    """V2.2: Vollständiges Backup/Restore aller persistierbaren Zustände."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._last_backup: Optional[str] = None
        self._last_restore: Optional[str] = None
        self._restore_log: list[str] = []

    @property
    def last_backup_time(self) -> Optional[str]:
        return self._last_backup

    @property
    def last_restore_time(self) -> Optional[str]:
        return self._last_restore

    @property
    def restore_log(self) -> list[str]:
        return self._restore_log.copy()

    async def async_save_backup(
        self,
        accumulators: dict[str, float],
        compare_values: dict[str, Optional[float]],
        period_timestamps: dict[str, Optional[int]],
        energy_snapshots: dict[str, Optional[float]],
        init_applied: bool,
        init_values: dict[str, Any],
        source_mapping: dict[str, Optional[str]],
    ) -> bool:
        """FIX #2: Sichert ALLE relevanten Zustände."""
        return await self._hass.async_add_executor_job(
            self._save_sync,
            accumulators, compare_values, period_timestamps,
            energy_snapshots, init_applied, init_values, source_mapping,
        )

    def _save_sync(
        self,
        accumulators: dict[str, float],
        compare_values: dict[str, Optional[float]],
        period_timestamps: dict[str, Optional[int]],
        energy_snapshots: dict[str, Optional[float]],
        init_applied: bool,
        init_values: dict[str, Any],
        source_mapping: dict[str, Optional[str]],
    ) -> bool:
        path = _backup_path(self._hass)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        now_str = datetime.now().isoformat(timespec="seconds")

        backup = {
            "meta": {
                "integration": "solar_mix_balance",
                "version": VERSION,
                "storage_version": STORAGE_VERSION,
                "exported_at": now_str,
                "description": "Solar Mix Balance V2.2 vollständiges Backup",
            },
            "accumulators": {k: float(v) for k, v in accumulators.items()},
            "compare_values": {
                k: (float(v) if v is not None else None)
                for k, v in compare_values.items()
            },
            # FIX #2: Top-Level statt extra_meta
            "period_timestamps": {k: v for k, v in period_timestamps.items()},
            "energy_snapshots": {
                k: (float(v) if v is not None else None)
                for k, v in energy_snapshots.items()
            },
            "init_applied": bool(init_applied),  # FIX #2: war vorher nicht gesichert
            "init_values": {k: v for k, v in init_values.items() if v is not None},
            "source_mapping": {k: v for k, v in source_mapping.items()},
        }

        # Atomisches Schreiben via tmp → replace
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(backup, fh, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp, path)
            self._last_backup = now_str
            _LOGGER.info("Backup gespeichert: %s", path)
            return True
        except Exception as err:
            _LOGGER.error("Backup-Schreibfehler: %s", err)
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return False

    async def async_load_backup(self) -> Optional[dict[str, Any]]:
        return await self._hass.async_add_executor_job(self._load_sync)

    def _load_sync(self) -> Optional[dict[str, Any]]:
        path = _backup_path(self._hass)
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            _LOGGER.info("Backup geladen: %s", path)
            return data
        except Exception as err:
            _LOGGER.error("Backup-Ladefehler: %s", err)
            return None

    async def async_restore(
        self,
        current_accumulators: dict[str, float],
        current_compare: dict[str, Optional[float]],
        current_period_timestamps: dict[str, Optional[int]],
        current_energy_snapshots: dict[str, Optional[float]],
        force_overwrite: bool = False,
    ) -> tuple[
        dict[str, float],
        dict[str, Optional[float]],
        dict[str, Optional[int]],
        dict[str, Optional[float]],
        bool,
        list[str],
    ]:
        """FIX #2: Vollständiger Restore aller Zustände aus Backup.

        Returns: (accumulators, compare_values, period_timestamps,
                  energy_snapshots, init_applied, log_messages)
        """
        backup = await self.async_load_backup()
        log: list[str] = []
        now_str = datetime.now().isoformat(timespec="seconds")

        if backup is None:
            log.append(f"{now_str}: Keine Backup-Datei – Restore übersprungen")
            self._restore_log = log
            return (
                current_accumulators, current_compare,
                current_period_timestamps, current_energy_snapshots,
                False, log
            )

        meta = backup.get("meta", {})
        bv = meta.get("storage_version", 1)
        if bv != STORAGE_VERSION:
            log.append(f"Backup StorageVersion={bv} ≠ aktuell={STORAGE_VERSION} – Best-effort")
            _LOGGER.warning("Backup-Version %s ≠ aktuell %s", bv, STORAGE_VERSION)

        # ── Akkumulatoren ─────────────────────────────────────────────────────
        restored_acc = dict(current_accumulators)
        for k, v in backup.get("accumulators", {}).items():
            if k not in restored_acc:
                log.append(f"Acc {k}: unbekannt – übersprungen")
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                log.append(f"Acc {k}: ungültig '{v}' – übersprungen")
                continue
            cur = restored_acc.get(k, 0.0)
            if cur > 0.0 and not force_overwrite:
                log.append(f"Acc {k}: aktuell {cur:.4f} > 0 → Backup {fv:.4f} NICHT überschrieben (sicher)")
            else:
                restored_acc[k] = fv
                log.append(f"Acc {k}: restored {fv:.4f} kWh")

        # ── Vergleichswerte ───────────────────────────────────────────────────
        restored_cmp = dict(current_compare)
        for k, v in backup.get("compare_values", {}).items():
            if k in restored_cmp:
                restored_cmp[k] = float(v) if v is not None else None

        # ── FIX #2: Period-Timestamps direkt aus Top-Level ────────────────────
        restored_pts = dict(current_period_timestamps)
        for k, v in backup.get("period_timestamps", {}).items():
            if k in restored_pts:
                restored_pts[k] = int(v) if v is not None else None
                log.append(f"PeriodTimestamp {k}: {v}")

        # ── FIX #2: Energy-Snapshots direkt aus Top-Level ─────────────────────
        restored_snaps = dict(current_energy_snapshots)
        for k, v in backup.get("energy_snapshots", {}).items():
            if k in restored_snaps:
                restored_snaps[k] = float(v) if v is not None else None
                log.append(f"EnergySnapshot {k}: {v}")

        # ── FIX #2: init_applied direkt aus Top-Level ─────────────────────────
        restored_init_applied = bool(backup.get("init_applied", False))
        log.append(f"init_applied: {restored_init_applied}")

        self._last_restore = now_str
        self._restore_log = log
        _LOGGER.info(
            "Restore V2.2 abgeschlossen: %d acc, %d cmp, %d pts, %d snaps",
            len(restored_acc), len(restored_cmp),
            len(restored_pts), len(restored_snaps),
        )
        return (
            restored_acc, restored_cmp, restored_pts, restored_snaps,
            restored_init_applied, log
        )

    def backup_exists(self) -> bool:
        return os.path.exists(_backup_path(self._hass))
