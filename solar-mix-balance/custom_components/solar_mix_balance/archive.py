"""CSV-Archivierung V5.7 – Finale Robustheit.

Fixes seit V5.2:
- #1: `_shutdown_started` Guard verhindert neue Write-Tasks nach shutdown()
- #4: `flush_pending()` iteriert über `set.copy()` – verhindert Set-Mutation während Iteration
- #4: Schreibfehler werden als Diagnoseeintrag an Coordinator zurückgemeldet (via Callback)
- Atomisches Schreiben (tmp + os.replace) war bereits vorhanden, bleibt erhalten
- asyncio.Lock war bereits vorhanden, bleibt erhalten

Ehrliche Einschränkung:
  Das asyncio.Lock serialisiert Write-Starts auf derselben CSVArchive-Instanz.
  Da es eine Instanz pro Coordinator gibt, ist das ausreichend.
  Dateisystem-externe Konkurrenz (andere Prozesse) wird nicht abgesichert –
  das ist bei HA single-process Architektur aber kein Praxisproblem.
"""
from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import datetime
from typing import Any, Callable, Optional

from homeassistant.core import HomeAssistant

from .const import (
    DATA_ROOT, DATA_DIR_TAG, DATA_DIR_WOCHE, DATA_DIR_MONAT, DATA_DIR_JAHR,
    CSV_DAILY, CSV_WEEKLY, CSV_MONTHLY, CSV_YEARLY, CSV_COLUMNS, VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _data_path(hass: HomeAssistant, *parts: str) -> str:
    return os.path.join(hass.config.config_dir, DATA_ROOT, *parts)


def ensure_directories(hass: HomeAssistant) -> None:
    """Synchron: Verzeichnisse erstellen (wird im Executor aufgerufen)."""
    for sub in [DATA_DIR_TAG, DATA_DIR_WOCHE, DATA_DIR_MONAT, DATA_DIR_JAHR, "backup"]:
        os.makedirs(_data_path(hass, sub), exist_ok=True)
    _LOGGER.debug("CSV-Verzeichnisse sichergestellt: %s", _data_path(hass))


def _read_existing(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    rows: list[dict] = []
    try:
        with open(filepath, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(dict(row))
    except Exception as err:
        _LOGGER.warning("CSV Lesefehler %s: %s", filepath, err)
    return rows


def _write_csv_sync(
    filepath: str,
    period_id: str,
    row: dict[str, Any],
    update_if_exists: bool = True,
) -> str:
    """Synchroner CSV-Schreibvorgang.

    Atomisches Schreiben: tmp-Datei → os.replace().
    Bei Fehler bleibt die alte Datei erhalten.

    Returns: "" bei Erfolg, Fehlermeldung bei Fehler.
    """
    existing = _read_existing(filepath)
    found = any(r.get("period_id") == period_id for r in existing)

    if found and not update_if_exists:
        _LOGGER.debug("Period %s in %s bereits vorhanden – übersprungen", period_id, filepath)
        return ""

    if found:
        existing = [r for r in existing if r.get("period_id") != period_id]

    complete = {col: row.get(col, "") for col in CSV_COLUMNS}
    existing.append(complete)

    tmp_path = filepath + ".tmp"
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for r in existing:
                writer.writerow({col: r.get(col, "") for col in CSV_COLUMNS})
        os.replace(tmp_path, filepath)
        return ""
    except Exception as err:
        error_msg = f"CSV Schreibfehler {filepath}: {err}"
        _LOGGER.error(error_msg)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return error_msg


def _build_row(
    period_id: str, solar_kwh: float, bat_charge_kwh: float,
    bat_to_house_kwh: float, grid_kwh: float, solar_direct_kwh: float,
    house_kwh: float, bat_share_kwh: float, solar_share_kwh: float,
    autarky_pct: float, grid_cost_eur: float, solar_savings_eur: float, source_info: str = "",
) -> dict[str, Any]:
    return {
        "period_id": period_id,
        "solar_energy_generated_kwh": round(solar_kwh, 4),
        "battery_energy_charged_kwh": round(bat_charge_kwh, 4),
        "battery_energy_to_house_kwh": round(bat_to_house_kwh, 4),
        "grid_energy_imported_kwh": round(grid_kwh, 4),
        "solar_energy_directly_consumed_kwh": round(solar_direct_kwh, 4),
        "house_energy_total_kwh": round(house_kwh, 4),
        "battery_share_of_consumption_kwh": round(bat_share_kwh, 4),
        "solar_share_of_consumption_kwh": round(solar_share_kwh, 4),
        "autarky_percent": round(autarky_pct, 2),
        "grid_cost_eur": round(grid_cost_eur, 2),
        "solar_savings_eur": round(solar_savings_eur, 2),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "source_info": source_info or f"smb_v{VERSION}",
    }


class CSVArchive:
    """V5.7: Robuste CSV-Archivierung mit Shutdown-Guard und korrektem Task-Tracking.

    Änderungen seit V5.2:
    - _shutdown_started: verhindert neue Write-Tasks nach shutdown()
    - flush_pending: iteriert über set.copy() statt des lebenden Sets
    - Schreibfehler werden über error_callback gemeldet
    """

    def __init__(
        self,
        hass: HomeAssistant,
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._hass = hass
        self._lock = asyncio.Lock()
        # FIX #4: Pending Tasks als Set – done_callback nutzt discard()
        self._pending_tasks: set[asyncio.Task] = set()
        self._last_write: dict[str, Optional[str]] = {
            "daily": None, "weekly": None, "monthly": None, "yearly": None,
        }
        self._last_errors: list[str] = []
        # FIX #1: Shutdown-Guard – nach shutdown() werden keine neuen Tasks mehr erstellt
        self._shutdown_started: bool = False
        # Callback um Schreibfehler an Coordinator zu melden
        self._error_callback = error_callback

    @property
    def last_write_times(self) -> dict[str, Optional[str]]:
        return self._last_write.copy()

    @property
    def last_errors(self) -> list[str]:
        return self._last_errors.copy()

    def setup(self) -> None:
        """Synchron (im Executor): Verzeichnisse erstellen."""
        ensure_directories(self._hass)

    async def flush_pending(self) -> None:
        """FIX #1/#4: Wartet alle ausstehenden Write-Tasks ab.

        FIX #4: Iteriert über set.copy() – verhindert Set-Mutation
        durch Done-Callbacks während der Iteration.

        Nach flush_pending() ist das Set leer (alle Tasks fertig oder gecancelt).
        """
        # FIX #4: set.copy() verhindert RuntimeError durch Set-Mutation
        pending_snapshot = set(self._pending_tasks)
        pending_snapshot = {t for t in pending_snapshot if not t.done()}

        if not pending_snapshot:
            return

        _LOGGER.debug("flush_pending: warte %d Write-Tasks", len(pending_snapshot))
        results = await asyncio.gather(*pending_snapshot, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                _LOGGER.error("Write-Task Ausnahme: %s", result)

        # Nach gather sind alle Tasks fertig – Set bereinigen
        self._pending_tasks = {t for t in self._pending_tasks if not t.done()}
        _LOGGER.debug("flush_pending: abgeschlossen, %d Tasks verbleiben", len(self._pending_tasks))

    async def shutdown(self) -> None:
        """FIX #1: Setzt Shutdown-Guard und flusht alle ausstehenden Tasks.

        Nach shutdown() werden keine neuen Write-Tasks mehr akzeptiert.
        """
        self._shutdown_started = True
        await self.flush_pending()
        _LOGGER.debug("CSVArchive: shutdown abgeschlossen")

    async def write_daily(self, date_str: str, data: dict[str, float]) -> bool:
        return await self._write(
            _data_path(self._hass, DATA_DIR_TAG, CSV_DAILY),
            date_str, data, "daily",
        )

    async def write_weekly(self, week_str: str, data: dict[str, float]) -> bool:
        return await self._write(
            _data_path(self._hass, DATA_DIR_WOCHE, CSV_WEEKLY),
            week_str, data, "weekly",
        )

    async def write_monthly(self, month_str: str, data: dict[str, float]) -> bool:
        return await self._write(
            _data_path(self._hass, DATA_DIR_MONAT, CSV_MONTHLY),
            month_str, data, "monthly",
        )

    async def write_yearly(self, year_str: str, data: dict[str, float]) -> bool:
        return await self._write(
            _data_path(self._hass, DATA_DIR_JAHR, CSV_YEARLY),
            year_str, data, "yearly",
        )

    async def _write(
        self, filepath: str, period_id: str,
        data: dict[str, float], period_type: str,
    ) -> bool:
        # V5.7: Archiv nutzt den bereits vom Coordinator berechneten Snapshot.
        # So können CSV-Werte nicht durch eine zweite Flow-Berechnung von den
        # angezeigten Sensorwerten abweichen.
        solar = max(0.0, data.get("solar", 0.0))
        bat_ch = max(0.0, data.get("bat_charge", 0.0))
        bat_dis = max(0.0, data.get("bat_discharge", 0.0))
        house = max(0.0, data.get("house", 0.0))
        grid_val = max(0.0, data.get("grid", 0.0))
        solar_direct = max(0.0, data.get("solar_direct", 0.0))
        bat_to_house = max(0.0, data.get("bat_to_house", data.get("battery_share", bat_dis)))
        autarky = max(0.0, min(100.0, data.get("autarky", 0.0)))
        grid_cost = max(0.0, data.get("grid_cost", 0.0))
        solar_savings = max(0.0, data.get("solar_savings", 0.0))
        row = _build_row(
            period_id=period_id,
            solar_kwh=solar,
            bat_charge_kwh=bat_ch,
            bat_to_house_kwh=bat_to_house,
            grid_kwh=grid_val,
            solar_direct_kwh=solar_direct,
            house_kwh=house,
            bat_share_kwh=bat_to_house,
            solar_share_kwh=solar_direct,
            autarky_pct=autarky,
            grid_cost_eur=grid_cost,
            solar_savings_eur=solar_savings,
            source_info=f"smb_v{VERSION}_{period_type}",
        )

        async with self._lock:
            error_msg = await self._hass.async_add_executor_job(
                _write_csv_sync, filepath, period_id, row, True
            )

        now_str = datetime.now().isoformat(timespec="seconds")
        success = not error_msg
        if success:
            self._last_write[period_type] = now_str
            _LOGGER.info("CSV %s: %s → %s", period_type, period_id, filepath)
        else:
            self._last_errors.append(f"{now_str}: {error_msg}")
            if len(self._last_errors) > 20:
                self._last_errors = self._last_errors[-20:]
            # FIX #4: Schreibfehler an Coordinator melden
            if self._error_callback is not None:
                self._error_callback(error_msg)
        return success

    def schedule_write(self, coro_fn, *args) -> Optional[asyncio.Task]:
        """FIX #1: Erstellt tracked Write-Task nur wenn kein Shutdown aktiv.

        Nach shutdown() werden keine neuen Tasks mehr erstellt.
        Gibt None zurück wenn Shutdown aktiv.
        """
        if self._shutdown_started:
            _LOGGER.warning(
                "schedule_write nach shutdown ignoriert: %s",
                getattr(coro_fn, "__name__", str(coro_fn))
            )
            return None

        task: asyncio.Task = self._hass.async_create_task(coro_fn(*args))

        def _on_done(t: asyncio.Task) -> None:
            # FIX #4: discard statt remove – kein KeyError wenn Task schon entfernt
            self._pending_tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                _LOGGER.error("Write-Task fehlgeschlagen: %s", t.exception())

        task.add_done_callback(_on_done)
        self._pending_tasks.add(task)
        return task
