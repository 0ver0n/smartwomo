"""DataUpdateCoordinator V5.7 – Finale Stabilisierung.

Fixes vs V2.2:
- #1: Zentraler async_shutdown() – ein einziger Pfad für Stop/Unload/Reload
- #1: _shutdown_guard verhindert Doppel-Flush
- #2: Defensives init_applied: wenn Backup init_applied=True aber alle Akkus 0
      (z.B. nach vollständigem Zähler-Reset) → init_applied auf False zurücksetzen
      damit Startwerte neu angewendet werden können
- #4: CSV-Schreibfehler werden in coordinator.diag['archive_errors'] eingetragen
      via error_callback aus archive.py
- Alle anderen V2.2-Fixes bleiben erhalten
"""
from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, VERSION, STORAGE_KEY, STORAGE_VERSION,
    CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2,
    CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
    CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY, CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC, CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH,
    CONF_HOUSE_POWER, CONF_HOUSE_ENERGY, CONF_GRID_POWER, CONF_GRID_ENERGY,
    CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
    CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS, ALL_INIT_KEYS,
    CONF_INIT_SOLAR_WEEK, CONF_INIT_SOLAR_MONTH, CONF_INIT_SOLAR_YEAR,
    CONF_INIT_GRID_WEEK, CONF_INIT_GRID_MONTH, CONF_INIT_GRID_YEAR,
    CONF_INIT_BAT_CHARGE_WEEK, CONF_INIT_BAT_CHARGE_MONTH, CONF_INIT_BAT_CHARGE_YEAR,
    CONF_INIT_BAT_DISCHARGE_WEEK, CONF_INIT_BAT_DISCHARGE_MONTH, CONF_INIT_BAT_DISCHARGE_YEAR,
    CONF_INIT_HOUSE_WEEK, CONF_INIT_HOUSE_MONTH, CONF_INIT_HOUSE_YEAR,
    CONF_INIT_SOLAR_DIRECT_WEEK, CONF_INIT_SOLAR_DIRECT_MONTH, CONF_INIT_SOLAR_DIRECT_YEAR,
    DEBOUNCE_SECONDS, SAFETY_REFRESH_MINUTES, MAX_ACCUMULATION_GAP_SECONDS,
    MAX_SOLAR_POWER_W, MAX_HOUSE_POWER_W, MAX_BATTERY_POWER_W, MAX_GRID_POWER_W,
    CONF_GRID_PRICE, CONF_MONTHLY_PRICES, CONF_MONTHLY_GRID_KWH, DEFAULT_GRID_PRICE,
)
from .helpers import (
    get_numeric_state, normalize_to_watt, normalize_to_kwh,
    safe_add, clamp_non_negative, safe_subtract, round_value,
    calculate_energy_flows, calculate_autarky, calculate_pct_change, validate_power,
)
from .archive import CSVArchive
from .restore import BackupManager

_LOGGER = logging.getLogger(__name__)

PERIODS = ("today", "week", "month", "year")
ACC_FIELDS = ("solar", "bat_charge", "bat_discharge", "house", "grid", "solar_direct", "home_output", "grid_charge", "grid_to_battery", "solar_to_battery", "battery_to_house", "grid_to_home")
ENERGY_SNAP_FIELDS = [
    "solar_today_start", "solar_week_start", "solar_month_start", "solar_year_start",
    "bat_charge_today_start", "bat_charge_week_start", "bat_charge_month_start", "bat_charge_year_start",
    "bat_discharge_today_start", "bat_discharge_week_start", "bat_discharge_month_start", "bat_discharge_year_start",
    "house_today_start", "house_week_start", "house_month_start", "house_year_start",
    "grid_today_start", "grid_week_start", "grid_month_start", "grid_year_start",
]

INIT_MAP = {
    CONF_INIT_SOLAR_WEEK: "solar_week",
    CONF_INIT_SOLAR_MONTH: "solar_month",
    CONF_INIT_SOLAR_YEAR: "solar_year",
    CONF_INIT_GRID_WEEK: "grid_week",
    CONF_INIT_GRID_MONTH: "grid_month",
    CONF_INIT_GRID_YEAR: "grid_year",
    CONF_INIT_BAT_CHARGE_WEEK: "bat_charge_week",
    CONF_INIT_BAT_CHARGE_MONTH: "bat_charge_month",
    CONF_INIT_BAT_CHARGE_YEAR: "bat_charge_year",
    CONF_INIT_BAT_DISCHARGE_WEEK: "bat_discharge_week",
    CONF_INIT_BAT_DISCHARGE_MONTH: "bat_discharge_month",
    CONF_INIT_BAT_DISCHARGE_YEAR: "bat_discharge_year",
    CONF_INIT_HOUSE_WEEK: "house_week",
    CONF_INIT_HOUSE_MONTH: "house_month",
    CONF_INIT_HOUSE_YEAR: "house_year",
    CONF_INIT_SOLAR_DIRECT_WEEK: "solar_direct_week",
    CONF_INIT_SOLAR_DIRECT_MONTH: "solar_direct_month",
    CONF_INIT_SOLAR_DIRECT_YEAR: "solar_direct_year",
}

# Bekannte Zendure-Gesamtzähler aus der bisherigen Helferlogik.
# Diese Fallbacks greifen nur, wenn das neue Feld nach einem Update noch leer ist.
AUTO_ENTITY_FALLBACKS = {
    CONF_ZENDURE_SOLAR_ENERGY: [],
    CONF_BATTERY_CHARGE_ENERGY: [],
    CONF_BATTERY_DISCHARGE_ENERGY: [],
}

# V5.8: Physikalische Messpunkte des SolarFlow 800 Pro.
# Diese Entitaeten kommen direkt aus Zendure-HA und erlauben eine echte
# AC-Bilanz statt der alten Schaetzung Solar - Akkuladung + Akkuentladung.
ZENDURE_FLOW_ENTITIES = {
    "pv": "sensor.solarflow_800_pro2_solar_input_power",
    "grid_charge": "sensor.solarflow_800_pro2_grid_input_power",
    "home_output": "sensor.solarflow_800_pro2_output_home_power",
    "battery_charge": "sensor.solarflow_800_pro2_output_pack_power",
    "battery_discharge": "sensor.solarflow_800_pro2_pack_input_power",
}


class SolarMixBalanceCoordinator(DataUpdateCoordinator):
    """Coordinator V5.7 mit zentralem Shutdown-Pfad."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=SAFETY_REFRESH_MINUTES),
        )
        self.entry = entry
        self.config: dict[str, Any] = dict(entry.data)

        self._acc: dict[str, float] = {
            f"{f}_{p}": 0.0 for f in ACC_FIELDS for p in PERIODS
        }
        self._cmp: dict[str, Optional[float]] = {
            f"{m}_{p}": None
            for m in ("solar", "bat_charge", "bat_discharge", "house", "grid", "solar_direct", "autarky")
            for p in ("yesterday", "last_week", "last_month", "last_year")
        }
        self._snap: dict[str, Optional[float]] = {k: None for k in ENERGY_SNAP_FIELDS}
        self._period: dict[str, Optional[int]] = {
            "day": None, "week": None, "month": None, "year": None
        }
        self._last_power: dict[str, Optional[float]] = {
            "solar": None, "bat_charge": None, "bat_discharge": None,
            "house": None, "grid": None,
            "home_output": None, "grid_charge": None,
            "grid_to_battery": None, "solar_to_battery": None,
            "solar_direct": None, "battery_to_house": None, "grid_to_home": None,
        }
        self._last_update: Optional[datetime] = None
        self._init_applied = False
        self._meter_disabled: set[str] = set()

        # FIX #1: Shutdown-Guard – verhindert Doppel-Flush
        self._shutdown_started: bool = False

        self.diag: dict[str, Any] = {
            "source_mapping": {},
            "fallback_flags": {},
            "data_quality_issues": [],
            "unavailable_sources": [],
            "last_calc": None,
            "last_csv_write": {},
            "last_backup": None,
            "last_restore": None,
            "restore_log": [],
            "archive_errors": [],
            "meter_mode": {},
        }

        # FIX #4: CSV-Schreibfehler via Callback in diag eintragen
        def _on_archive_error(error_msg: str) -> None:
            now = dt_util.now().isoformat(timespec="seconds")
            self.diag["archive_errors"].append(f"{now}: {error_msg}")
            if len(self.diag["archive_errors"]) > 20:
                self.diag["archive_errors"] = self.diag["archive_errors"][-20:]
            _LOGGER.error("Archiv-Fehler (Diagnose): %s", error_msg)

        self._store = Store(hass, version=STORAGE_VERSION, key=f"{STORAGE_KEY}_{entry.entry_id}")
        # FIX #4: error_callback für Diagnosemeldungen
        self._archive = CSVArchive(hass, error_callback=_on_archive_error)
        self._backup_mgr = BackupManager(hass)
        self._debounce_task: Optional[asyncio.Task] = None
        self._unsub_state_listeners: list[Any] = []

    # ── Config ────────────────────────────────────────────────────────────────

    def _get_entity(self, key: str) -> Optional[str]:
        val = self.config.get(key)
        if val and val not in ("none", "", None):
            return val
        for fallback in AUTO_ENTITY_FALLBACKS.get(key, []):
            if self.hass.states.get(fallback) is not None:
                self.diag["fallback_flags"][f"Auto-kWh-Zähler genutzt: {key}"] = fallback
                return fallback
        return None


    def _grid_price(self) -> float:
        """Fallback-Preis in €/kWh."""
        try:
            return max(0.0, float(self.config.get(CONF_GRID_PRICE, DEFAULT_GRID_PRICE) or DEFAULT_GRID_PRICE))
        except (TypeError, ValueError):
            return DEFAULT_GRID_PRICE

    def _monthly_prices(self) -> dict[str, float]:
        raw = self.config.get(CONF_MONTHLY_PRICES) or {}
        if not isinstance(raw, dict):
            return {}
        prices: dict[str, float] = {}
        for key, value in raw.items():
            try:
                prices[str(key)] = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
        return prices

    def _monthly_grid_kwh(self) -> dict[str, float]:
        """Belegter Netzbezug je Monat in kWh, getrennt vom Solar-Monatsarchiv."""
        raw = self.config.get(CONF_MONTHLY_GRID_KWH) or {}
        if not isinstance(raw, dict):
            return {}
        values: dict[str, float] = {}
        for key, value in raw.items():
            try:
                values[str(key)] = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
        return values

    def _price_for_month(self, year: int, month: int) -> tuple[float, str]:
        key = f"{year:04d}-{month:02d}"
        prices = self._monthly_prices()
        if key in prices and prices[key] > 0:
            return prices[key], f"Monatspreis {key}"
        return self._grid_price(), "Fallback-Strompreis"

    def _current_price(self, now: datetime) -> tuple[float, str]:
        return self._price_for_month(now.year, now.month)

    def _read_monthly_archive_rows(self) -> list[dict[str, str]]:
        """Liest abgeschlossene Monatszeilen für monatsgenaue Jahreskosten.

        Fehlt die Datei oder sind Zeilen unlesbar, wird still auf Fallback-
        Jahrespreisberechnung umgestellt und ein Diagnosehinweis gesetzt.
        """
        path = os.path.join(
            self.hass.config.config_dir,
            "solar_mix_balance_data",
            "monat",
            "monthly_values.csv",
        )
        if not os.path.exists(path):
            return []
        rows: list[dict[str, str]] = []
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    rows.append(dict(row))
        except Exception as err:
            self.diag["data_quality_issues"].append(f"Monatsarchiv konnte nicht gelesen werden: {err}")
            self.diag["data_quality_issues"] = self.diag["data_quality_issues"][-50:]
        return rows

    @staticmethod
    def _row_float(row: dict[str, str], key: str) -> float:
        try:
            return max(0.0, float(row.get(key) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def _year_price_costs(self, now: datetime, fp_year: dict[str, float], fp_month: dict[str, float]) -> tuple[float, float, str]:
        """Berechnet Jahreskosten monatsgenau, inklusive belegter Netz-Monatswerte.

        Priorität:
        1. echte Solar-Mix-Monatsarchive,
        2. belegte Netzverbrauchs-Monatswerte für Archivlücken,
        3. aktueller Monat,
        4. nur der verbleibende nicht aufteilbare Rest zum Fallbackpreis.

        Belegte Netz-Monatswerte beeinflussen ausschließlich grid_cost. Solar-
        und Batteriehistorie wird dadurch ausdrücklich nicht erfunden.
        """
        fallback = self._grid_price()
        grid_cost = 0.0
        savings = 0.0
        archived_grid = 0.0
        archived_self = 0.0
        used_months: list[str] = []
        used_month_ids: set[str] = set()

        year_grid = max(0.0, self._acc["grid_year"])
        year_self = max(0.0, fp_year["solar_direct"] + fp_year["bat_to_house"])

        for row in getattr(self, "_monthly_archive_rows_cache", []):
            pid = str(row.get("period_id") or "")
            try:
                year_s, month_s = pid.split("-", 1)
                year, month = int(year_s), int(month_s)
            except Exception:
                continue
            if year != now.year or month >= now.month:
                continue
            price, _source = self._price_for_month(year, month)
            grid = self._row_float(row, "grid_energy_imported_kwh")
            solar_direct = self._row_float(row, "solar_energy_directly_consumed_kwh")
            bat = self._row_float(row, "battery_energy_to_house_kwh")
            grid_cost += grid * price
            savings += (solar_direct + bat) * price
            archived_grid += grid
            archived_self += solar_direct + bat
            used_months.append(f"{year:04d}-{month:02d}")
            used_month_ids.add(f"{year:04d}-{month:02d}")

        # Rechnungs-/Belegwerte schließen ausschließlich Lücken im Netzbezug.
        # Bestehende Solar-Mix-Monatsarchive haben immer Vorrang.
        manual_months: list[str] = []
        for pid, raw_grid in sorted(self._monthly_grid_kwh().items()):
            try:
                year_s, month_s = pid.split("-", 1)
                year, month = int(year_s), int(month_s)
            except Exception:
                continue
            if year != now.year or month >= now.month or pid in used_month_ids:
                continue
            remaining_history = max(0.0, year_grid - archived_grid)
            if remaining_history <= 0.001:
                break
            grid = min(max(0.0, raw_grid), remaining_history)
            if grid <= 0.0:
                continue
            price, _source = self._price_for_month(year, month)
            grid_cost += grid * price
            archived_grid += grid
            manual_months.append(pid)
            used_months.append(f"{pid} Beleg")

        if manual_months:
            self.diag["fallback_flags"]["Belegter Monats-Netzbezug für Archivlücken genutzt"] = True

        current_price, current_source = self._current_price(now)

        # Aktueller Monat wird nur bis zum verbleibenden Jahresrest angesetzt.
        # Damit können Monatsarchiv, belegte Archivlücken, laufender Monat und
        # nicht aufteilbare Startwerte nicht doppelt gezählt werden.
        remaining_grid_for_current = max(0.0, year_grid - archived_grid)
        remaining_self_for_current = max(0.0, year_self - archived_self)
        current_grid = min(max(0.0, self._acc["grid_month"]), remaining_grid_for_current)
        current_self = min(max(0.0, fp_month["solar_direct"] + fp_month["bat_to_house"]), remaining_self_for_current)
        grid_cost += current_grid * current_price
        savings += current_self * current_price

        residual_grid = max(0.0, year_grid - archived_grid - current_grid)
        residual_self = max(0.0, year_self - archived_self - current_self)
        if residual_grid > 0.001 or residual_self > 0.001:
            grid_cost += residual_grid * fallback
            savings += residual_self * fallback
            self.diag["fallback_flags"]["Jahreskosten enthalten nicht auf Monate aufteilbare Startwerte"] = True

        source = f"Monatspreise ({', '.join(used_months) or 'keine abgeschlossenen Monate'} + {now.year:04d}-{now.month:02d}: {current_source}; Rest: Fallback)"
        return grid_cost, savings, source

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        await self.hass.async_add_executor_job(self._archive.setup)
        await self._async_load_state()
        self._apply_init_values()
        self._sync_legacy_helper_values()
        await self._async_ensure_snapshots()
        self._register_state_listeners()

    async def _async_ensure_snapshots(self) -> None:
        """Initialisiert fehlende Energiezähler-Snapshots für alle kWh-Zähler.

        Wichtig für Updates: Wenn Startwerte vorhanden sind, wird der Snapshot
        als aktueller Gesamtzähler minus bereits vorhandener Akkumulator gesetzt.
        Dadurch bleiben alte Helfer-/Startwerte erhalten und neue kWh-Zähler
        laufen ab dem Update korrekt weiter.
        """
        meters = {
            "solar": self._read_solar_energy_kwh(),
            "bat_charge": self._read_bat_charge_energy_kwh(),
            "bat_discharge": self._read_bat_discharge_energy_kwh(),
            "house": self._read_house_energy_kwh(),
            "grid": self._read_grid_energy_kwh(),
        }
        for metric, meter in meters.items():
            if meter is None:
                continue
            for period in PERIODS:
                sk = f"{metric}_{period}_start"
                ak = f"{metric}_{period}"
                if self._snap.get(sk) is None:
                    implied = meter - self._acc.get(ak, 0.0)
                    if implied < 0:
                        self._snap[sk] = None
                        self._meter_disabled.add(sk)
                        _LOGGER.warning("Startwert > Zähler für %s: acc=%.3f kWh, meter=%.3f kWh – Meter-Modus für diese Laufzeit deaktiviert, Trapez-Fallback erhält Startwert", sk, self._acc.get(ak, 0.0), meter)
                    else:
                        self._snap[sk] = implied
                        _LOGGER.info("Snapshot %s initialisiert: %.3f kWh", sk, self._snap[sk])

    def _register_state_listeners(self) -> None:

        for unsub in self._unsub_state_listeners:
            unsub()
        self._unsub_state_listeners.clear()

        tracked: set[str] = set()
        for key in [
            CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY,
            CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2,
            CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
            CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY,
            CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC,
            CONF_HOUSE_POWER, CONF_HOUSE_ENERGY,
            CONF_GRID_POWER, CONF_GRID_ENERGY,
            CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
        ]:

            eid = self._get_entity(key)
            if eid:
                tracked.add(eid)

        # V5.8: auch die echten SolarFlow-Energiefluss-Sensoren verfolgen.
        for eid in ZENDURE_FLOW_ENTITIES.values():
            if self.hass.states.get(eid) is not None:
                tracked.add(eid)

        if not tracked:
            _LOGGER.warning("Keine Entitäten konfiguriert – kein State-Listener")
            return

        @callback
        def _on_state_change(event: Event) -> None:
            self._trigger_debounced_refresh()

        unsub = async_track_state_change_event(self.hass, list(tracked), _on_state_change)
        self._unsub_state_listeners.append(unsub)
        _LOGGER.debug("State-Listener: %d Entitäten", len(tracked))

    @callback
    def _trigger_debounced_refresh(self) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = self.hass.async_create_task(self._debounced_coro())

    async def _debounced_coro(self) -> None:
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            await self.async_refresh()
        except asyncio.CancelledError:
            pass

    # ── FIX #1: Zentraler Shutdown-Pfad ──────────────────────────────────────

    async def async_shutdown(self) -> None:
        """FIX #1: Einziger, zentraler Shutdown-Pfad.

        Wird von __init__.py sowohl für HA-Stop als auch für Unload aufgerufen.
        Idempotent: zweiter Aufruf wird durch _shutdown_started ignoriert.

        Reihenfolge:
        1. _shutdown_started = True → keine neuen Write-Tasks mehr
        2. State-Listener entfernen
        3. Debounce-Task abbrechen
        4. archive.shutdown() → flush_pending() awaited + shutdown guard
        5. async_save_state() → HA Storage + Backup
        """
        if self._shutdown_started:
            _LOGGER.debug("async_shutdown: bereits aktiv – ignoriert")
            return

        self._shutdown_started = True
        _LOGGER.debug(" V5.7 async_shutdown gestartet")

        # 1. Listener entfernen
        for unsub in self._unsub_state_listeners:
            unsub()
        self._unsub_state_listeners.clear()

        # 2. Debounce abbrechen
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        # 3. FIX #1/#4: Archive Shutdown (setzt Guard + flusht alle Tasks)
        try:
            await self._archive.shutdown()
        except Exception as err:
            _LOGGER.error("Fehler beim Archive-Shutdown: %s", err)

        # 4. Finales Speichern
        try:
            await self.async_save_state()
            _LOGGER.debug(" V5.7 async_shutdown abgeschlossen")
        except Exception as err:
            _LOGGER.error("Fehler beim finalen Speichern: %s", err)

    # Rückwärtskompatibilität für Code der cleanup_listeners() direkt aufruft
    def cleanup_listeners(self) -> None:
        """Sync-Entfernung der Listener. Kein Save, kein Flush."""
        for unsub in self._unsub_state_listeners:
            unsub()
        self._unsub_state_listeners.clear()
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

    # ── Startwerte ────────────────────────────────────────────────────────────

    def _apply_init_values(self) -> None:
        """FIX #2: Defensiv – prüft ob init_applied wirklich noch sinnvoll ist."""
        if self._init_applied:
            # FIX #2: Wenn init_applied=True aber alle Akkumulatoren = 0,
            # wurde entweder ein Zähler-Reset durchgeführt oder der Storage
            # war leer. Dann init_applied zurücksetzen damit Startwerte
            # erneut angewendet werden können.
            all_zero = all(v == 0.0 for v in self._acc.values())
            if all_zero:
                _LOGGER.info(
                    "init_applied=True aber alle Akkumulatoren=0 → reset auf False "
                    "(Startwerte können neu angewendet werden)"
                )
                self._init_applied = False
            else:
                return  # init_applied korrekt, nicht erneut anwenden

        count = 0
        for ck, ak in INIT_MAP.items():
            raw = self.config.get(ck)
            if raw in (None, "", 0, 0.0):
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            if val > 0.0 and self._acc.get(ak, 0.0) == 0.0:
                self._acc[ak] = val
                count += 1
                _LOGGER.info("Startwert: %s = %.3f kWh", ak, val)

        self._init_applied = True
        if count:
            _LOGGER.info("Startwerte angewendet: %d Felder", count)


    def _sync_legacy_helper_values(self) -> None:
        """Übernimmt vorhandene alte Helferwerte als Startbasis.

        In einer früheren Installation wurden vor dieser Integration Utility-Meter-/Template-Helfer auf Basis
        echter kWh-Gesamtzähler. Wenn diese Sensoren noch vorhanden sind, sind sie
        für die laufende Woche/Monat/Jahr genauer als alte, aus Watt integrierte
        Akkumulatoren früherer Solar-Mix-Versionen. Deshalb übernehmen wir sie
        beim Start, falls der Helferwert größer ist als der aktuell gespeicherte
        Akkumulator. Es wird nichts erzwungen, wenn die Helfer fehlen.
        """
        legacy_map = {
            "grid_today": ["sensor.stromverbrauch_heute"],
            "grid_week": ["sensor.stromverbrauch_diese_woche"],
            "grid_month": ["sensor.stromverbrauch_dieser_monat"],
            "grid_year": ["sensor.stromverbrauch_dieses_jahr"],
            "solar_week": ["sensor.solar_ertrag_woche"],
            "solar_month": ["sensor.solar_ertrag_monat"],
            "solar_year": ["sensor.solar_ertrag_jahr"],
            "bat_charge_week": ["sensor.batterie_ladung_woche"],
            "bat_charge_month": ["sensor.batterie_ladung_monat"],
            "bat_charge_year": ["sensor.batterie_ladung_jahr"],
            "bat_discharge_week": ["sensor.batterie_entladung_woche"],
            "bat_discharge_month": ["sensor.batterie_entladung_monat"],
            "bat_discharge_year": ["sensor.batterie_entladung_jahr"],
            "solar_direct_week": ["sensor.solar_direkt_verbraucht_woche"],
            "solar_direct_month": ["sensor.solar_direkt_ins_haus_monat", "sensor.solar_direkt_verbraucht_monat"],
            "solar_direct_year": ["sensor.solar_direkt_verbraucht_jahr", "sensor.solar_direkt_ins_haus_jahr"],
        }
        imported = []
        for acc_key, entities in legacy_map.items():
            for entity_id in entities:
                raw = get_numeric_state(self.hass, entity_id)
                if raw is None:
                    continue
                val = normalize_to_kwh(self.hass, entity_id, raw)
                if val is None or val < 0:
                    continue
                current = self._acc.get(acc_key, 0.0)
                if val > current + 0.01:
                    self._acc[acc_key] = float(val)
                    imported.append(f"{acc_key}={val:.3f} ({entity_id})")
                break
        if imported:
            self.diag["fallback_flags"]["Alte Helferwerte importiert"] = imported
            _LOGGER.info("Alte Helferwerte übernommen: %s", "; ".join(imported))

    # ── Leistungsabfragen ─────────────────────────────────────────────────────

    def _read_solar_z(self, qi: list[str]) -> Optional[float]:
        eid = self._get_entity(CONF_ZENDURE_SOLAR)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return validate_power(normalize_to_watt(self.hass, eid, raw), MAX_SOLAR_POWER_W, "Zendure Solar", qi) if raw is not None else None

    def _read_solar_e(self, qi: list[str]) -> Optional[float]:
        total = 0.0
        found = False
        for key, label in [
            (CONF_ECOFLOW_SOLAR, "EcoFlow Solar"),
            (CONF_ECOFLOW_SOLAR_2, "EcoFlow Solar 2"),
        ]:
            eid = self._get_entity(key)
            if not eid:
                continue
            raw = get_numeric_state(self.hass, eid)
            if raw is None:
                continue
            val = validate_power(normalize_to_watt(self.hass, eid, raw), MAX_SOLAR_POWER_W, label, qi)
            if val is not None:
                total += val
                found = True
        return total if found else None

    def _read_energy_entity(self, key: str) -> Optional[float]:
        eid = self._get_entity(key)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return normalize_to_kwh(self.hass, eid, raw) if raw is not None else None

    def _read_solar_energy_kwh(self) -> Optional[float]:
        values: list[float] = []
        for key in [CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY]:
            val = self._read_energy_entity(key)
            if val is not None:
                values.append(val)
        return sum(values) if values else None

    def _read_bat_charge_energy_kwh(self) -> Optional[float]:
        return self._read_energy_entity(CONF_BATTERY_CHARGE_ENERGY)

    def _read_bat_discharge_energy_kwh(self) -> Optional[float]:
        return self._read_energy_entity(CONF_BATTERY_DISCHARGE_ENERGY)

    def _read_bat_charge(self, qi: list[str]) -> Optional[float]:
        eid = self._get_entity(CONF_BATTERY_CHARGE)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return validate_power(normalize_to_watt(self.hass, eid, raw), MAX_BATTERY_POWER_W, "Bat Charge", qi) if raw is not None else None

    def _read_bat_discharge(self, qi: list[str]) -> Optional[float]:
        eid = self._get_entity(CONF_BATTERY_DISCHARGE)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return validate_power(normalize_to_watt(self.hass, eid, raw), MAX_BATTERY_POWER_W, "Bat Discharge", qi) if raw is not None else None

    def _read_battery_soc(self) -> Optional[float]:
        eid = self._get_entity(CONF_BATTERY_SOC)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        if raw is None:
            return None
        try:
            return max(0.0, min(100.0, float(raw)))
        except (TypeError, ValueError):
            return None

    def _battery_capacity_kwh(self) -> Optional[float]:
        raw = self.config.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH)
        try:
            cap = float(raw)
        except (TypeError, ValueError):
            return None
        return cap if cap > 0 else None

    def _physical_flow_capable(self) -> bool:
        """True wenn alle benoetigten SolarFlow-800-Pro-Messpunkte existieren."""
        return all(self.hass.states.get(eid) is not None for eid in ZENDURE_FLOW_ENTITIES.values())

    def _read_fixed_power(self, entity_id: str, max_w: float, label: str, qi: list[str]) -> Optional[float]:
        raw = get_numeric_state(self.hass, entity_id)
        if raw is None:
            return None
        return validate_power(
            clamp_non_negative(normalize_to_watt(self.hass, entity_id, raw)),
            max_w, label, qi,
        )

    def _read_zendure_physical_flows(self, qi: list[str]) -> dict[str, Any]:
        """Liest und verteilt die realen SolarFlow-800-Pro-Leistungsfluesse.

        outputHomePower ist der tatsaechliche AC-Ausgang Richtung Haus.
        Dieser wird nach den gleichzeitig gemessenen Quellen PV, Batterie und
        ggf. Netz aufgeteilt. Damit werden Wechselrichterverluste nicht mehr
        faelschlich als Hausverbrauch verbucht.
        """
        pv = self._read_fixed_power(ZENDURE_FLOW_ENTITIES["pv"], MAX_SOLAR_POWER_W, "SolarFlow PV", qi)
        grid_in = self._read_fixed_power(ZENDURE_FLOW_ENTITIES["grid_charge"], MAX_GRID_POWER_W, "SolarFlow Netzladung", qi)
        home_out = self._read_fixed_power(ZENDURE_FLOW_ENTITIES["home_output"], MAX_HOUSE_POWER_W, "SolarFlow AC ans Haus", qi)
        bat_ch = self._read_fixed_power(ZENDURE_FLOW_ENTITIES["battery_charge"], MAX_BATTERY_POWER_W, "SolarFlow Batterieladung", qi)
        bat_dis = self._read_fixed_power(ZENDURE_FLOW_ENTITIES["battery_discharge"], MAX_BATTERY_POWER_W, "SolarFlow Batterieabgabe", qi)

        configured = self._physical_flow_capable()
        valid = configured and all(v is not None for v in (pv, grid_in, home_out, bat_ch, bat_dis))
        if not valid:
            return {
                "configured": configured, "valid": False,
                "pv": pv, "grid_charge": grid_in, "home_output": home_out,
                "battery_charge": bat_ch, "battery_discharge": bat_dis,
                "grid_to_battery": None, "solar_to_battery": None,
                "solar_direct": None, "battery_to_house": None, "grid_to_home": None,
            }

        pv = max(0.0, pv or 0.0)
        grid_in = max(0.0, grid_in or 0.0)
        home_out = max(0.0, home_out or 0.0)
        bat_ch = max(0.0, bat_ch or 0.0)
        bat_dis = max(0.0, bat_dis or 0.0)

        # Naeherung an den Messpunkten: Netzladung zuerst als Quelle der
        # Batterieladung abziehen. Der Rest der Batterieladung stammt aus PV.
        grid_to_battery = min(bat_ch, grid_in)
        solar_to_battery = max(0.0, bat_ch - grid_to_battery)
        pv_to_inverter = max(0.0, pv - solar_to_battery)
        grid_to_home_supply = max(0.0, grid_in - grid_to_battery)

        total_supply = pv_to_inverter + bat_dis + grid_to_home_supply
        if total_supply > 0.001:
            solar_direct = home_out * pv_to_inverter / total_supply
            battery_to_house = home_out * bat_dis / total_supply
            grid_to_home = home_out * grid_to_home_supply / total_supply
        else:
            solar_direct = 0.0
            battery_to_house = 0.0
            grid_to_home = home_out if grid_in > 0.0 else 0.0

        return {
            "configured": configured, "valid": True,
            "pv": pv, "grid_charge": grid_in, "home_output": home_out,
            "battery_charge": bat_ch, "battery_discharge": bat_dis,
            "grid_to_battery": grid_to_battery,
            "solar_to_battery": solar_to_battery,
            "solar_direct": solar_direct,
            "battery_to_house": battery_to_house,
            "grid_to_home": grid_to_home,
        }

    def _read_house_power(self, qi: list[str]) -> Optional[float]:
        eid = self._get_entity(CONF_HOUSE_POWER)
        if eid:
            raw = get_numeric_state(self.hass, eid)
            if raw is not None:
                return validate_power(normalize_to_watt(self.hass, eid, raw), MAX_HOUSE_POWER_W, "House Power", qi)

        phases = []
        for pkey in [CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER]:
            peid = self._get_entity(pkey)
            if peid:
                raw = get_numeric_state(self.hass, peid)
                if raw is not None:
                    v = clamp_non_negative(normalize_to_watt(self.hass, peid, raw)) or 0.0
                    phases.append(v)
        if phases:
            if len(phases) < 3:
                self.diag["fallback_flags"][f"Hausverbrauch Phasensumme {len(phases)}/3"] = True
            return validate_power(sum(phases), MAX_HOUSE_POWER_W, "House Power (Phases)", qi)
        return None

    def _read_grid_power(self, qi: list[str]) -> Optional[float]:
        eid = self._get_entity(CONF_GRID_POWER)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return validate_power(clamp_non_negative(normalize_to_watt(self.hass, eid, raw)), MAX_GRID_POWER_W, "Grid Power", qi) if raw is not None else None

    def _read_house_energy_kwh(self) -> Optional[float]:
        eid = self._get_entity(CONF_HOUSE_ENERGY)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return normalize_to_kwh(self.hass, eid, raw) if raw is not None else None

    def _read_grid_energy_kwh(self) -> Optional[float]:
        eid = self._get_entity(CONF_GRID_ENERGY)
        if not eid:
            return None
        raw = get_numeric_state(self.hass, eid)
        return normalize_to_kwh(self.hass, eid, raw) if raw is not None else None

    def _update_energy_from_meter(
        self, meter_val: Optional[float], snap_key: str,
        acc_key: str, metric: str, period: str,
    ) -> bool:
        if meter_val is None:
            return False
        snap = self._snap.get(snap_key)
        if snap is None:
            implied = meter_val - self._acc[acc_key]
            if implied < 0:
                self._snap[snap_key] = None
                self._meter_disabled.add(snap_key)
                _LOGGER.warning("Startwert > Zähler für %s: acc=%.3f kWh, meter=%.3f kWh – Meter-Modus für diese Laufzeit deaktiviert, Trapez-Fallback erhält Startwert", snap_key, self._acc[acc_key], meter_val)
            else:
                self._snap[snap_key] = implied
            return True
        delta = meter_val - snap
        if delta < 0:
            _LOGGER.warning(
                "Zähler-Reset %s/%s: snap=%.3f meter=%.3f → Snapshot neu gesetzt",
                metric, period, snap, meter_val
            )
            self._snap[snap_key] = meter_val
            return True
        self._acc[acc_key] = delta
        return True

    # ── Hauptberechnung ───────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # CSV-Dateizugriff darf den Home-Assistant-Eventloop nicht blockieren.
            # Die Zeilen werden deshalb im Executor gelesen; die eigentliche
            # Energieberechnung bleibt anschließend unverändert im Coordinator.
            self._monthly_archive_rows_cache = await self.hass.async_add_executor_job(
                self._read_monthly_archive_rows
            )
            return self._compute()
        except Exception as err:
            _LOGGER.error("Berechnungsfehler V5.7: %s", err, exc_info=True)
            raise UpdateFailed(f"Berechnungsfehler: {err}") from err

    def _compute(self) -> dict[str, Any]:
        now = dt_util.now()
        qi: list[str] = []

        self._check_period_resets(now)

        solar_z = self._read_solar_z(qi)
        solar_e = self._read_solar_e(qi)
        bat_charge_w = self._read_bat_charge(qi)
        bat_discharge_w = self._read_bat_discharge(qi)
        battery_soc = self._read_battery_soc()
        battery_capacity = self._battery_capacity_kwh()
        house_power_w = self._read_house_power(qi)
        grid_power_direct = self._read_grid_power(qi)

        physical = self._read_zendure_physical_flows(qi)
        # Der gemessene AC-Fluss gilt fuer den Zendure. Falls spaeter eine
        # separate EcoFlow-Quelle aktiv wird, faellt die Integration bewusst
        # auf die alte generische Logik zurueck, statt beide Systeme zu vermischen.
        physical_mode = bool(physical.get("configured")) and not (solar_e is not None and solar_e > 0.1)
        physical_valid = physical_mode and bool(physical.get("valid"))
        if physical_valid:
            solar_z = physical.get("pv")
            bat_charge_w = physical.get("battery_charge")
            bat_discharge_w = physical.get("battery_discharge")

        solar_total_w = safe_add(solar_z, solar_e)
        has_house_entity = bool(self._get_entity(CONF_HOUSE_POWER) or self._get_entity(CONF_HOUSE_ENERGY))
        use_derived_house = not has_house_entity

        grid_power_w = grid_power_direct
        if physical_valid and use_derived_house and grid_power_w is not None:
            house_power_w = max(
                0.0,
                grid_power_w - (physical.get("grid_charge") or 0.0) + (physical.get("home_output") or 0.0),
            )
            self.diag["fallback_flags"]["Hausverbrauch aus realem AC-Fluss"] = True
        elif grid_power_w is None and house_power_w is not None:
            calc = (house_power_w or 0.0) - max(0.0, (solar_total_w or 0.0) - (bat_charge_w or 0.0)) \
                   - (bat_discharge_w or 0.0)
            grid_power_w = max(0.0, calc)
            self.diag["fallback_flags"]["Netzbezug berechnet (kein Sensor)"] = True
        elif use_derived_house and not physical_mode:
            solar_direct_live = max(0.0, (solar_total_w or 0.0) - (bat_charge_w or 0.0))
            house_power_w = max(0.0, (grid_power_w or 0.0) + solar_direct_live + (bat_discharge_w or 0.0))
            self.diag["fallback_flags"]["Hausverbrauch berechnet (Legacy-Fallback)"] = True

        solar_meter = self._read_solar_energy_kwh()
        bat_charge_meter = self._read_bat_charge_energy_kwh()
        bat_discharge_meter = self._read_bat_discharge_energy_kwh()
        house_meter = self._read_house_energy_kwh()
        grid_meter = self._read_grid_energy_kwh()
        meter_mode: dict[str, str] = {}

        if self._last_update is not None:
            dt_sec = (now - self._last_update).total_seconds()
            if dt_sec < 0:
                _LOGGER.warning("Systemzeit sprang rückwärts: dt_sec=%.3f – keine Akkumulation", dt_sec)
            elif 0 < dt_sec <= MAX_ACCUMULATION_GAP_SECONDS:
                dt_h = dt_sec / 3600.0

                def _trap(cur: Optional[float], last: Optional[float]) -> float:
                    if cur is None and last is None:
                        return 0.0
                    c = cur if cur is not None else (last or 0.0)
                    l_ = last if last is not None else c
                    return ((c + l_) / 2.0) * dt_h / 1000.0

                delta_solar = _trap(solar_total_w, self._last_power["solar"])
                delta_bat_ch = _trap(bat_charge_w, self._last_power["bat_charge"])
                delta_bat_dis = _trap(bat_discharge_w, self._last_power["bat_discharge"])
                delta_house_trap = _trap(house_power_w, self._last_power["house"])
                delta_grid_trap = _trap(grid_power_w, self._last_power["grid"])

                if physical_valid:
                    delta_home_output = _trap(physical.get("home_output"), self._last_power["home_output"])
                    delta_grid_charge = _trap(physical.get("grid_charge"), self._last_power["grid_charge"])
                    delta_grid_to_battery = _trap(physical.get("grid_to_battery"), self._last_power["grid_to_battery"])
                    delta_solar_to_battery = _trap(physical.get("solar_to_battery"), self._last_power["solar_to_battery"])
                    delta_solar_direct = _trap(physical.get("solar_direct"), self._last_power["solar_direct"])
                    delta_battery_to_house = _trap(physical.get("battery_to_house"), self._last_power["battery_to_house"])
                    delta_grid_to_home = _trap(physical.get("grid_to_home"), self._last_power["grid_to_home"])
                else:
                    delta_home_output = delta_grid_charge = delta_grid_to_battery = 0.0
                    delta_solar_to_battery = delta_solar_direct = delta_battery_to_house = delta_grid_to_home = 0.0

                for p in PERIODS:
                    self._acc[f"solar_{p}"] += delta_solar
                    self._acc[f"bat_charge_{p}"] += delta_bat_ch
                    self._acc[f"bat_discharge_{p}"] += delta_bat_dis
                    if physical_valid:
                        self._acc[f"home_output_{p}"] += delta_home_output
                        self._acc[f"grid_charge_{p}"] += delta_grid_charge
                        self._acc[f"grid_to_battery_{p}"] += delta_grid_to_battery
                        self._acc[f"solar_to_battery_{p}"] += delta_solar_to_battery
                        self._acc[f"solar_direct_{p}"] += delta_solar_direct
                        self._acc[f"battery_to_house_{p}"] += delta_battery_to_house
                        self._acc[f"grid_to_home_{p}"] += delta_grid_to_home

                for p in PERIODS:
                    for metric, meter_val in [
                        ("solar", solar_meter),
                        ("bat_charge", bat_charge_meter),
                        ("bat_discharge", bat_discharge_meter),
                    ]:
                        sk = f"{metric}_{p}_start"
                        ak = f"{metric}_{p}"
                        if meter_val is not None and sk not in self._meter_disabled and self._snap.get(sk) is not None:
                            used = self._update_energy_from_meter(meter_val, sk, ak, metric, p)
                            meter_mode[ak] = "meter" if used else "trapez"
                        else:
                            meter_mode.setdefault(ak, "trapez")

                    hk = f"house_{p}_start"
                    gk = f"grid_{p}_start"
                    hak = f"house_{p}"
                    gak = f"grid_{p}"

                    if house_meter is not None and hk not in self._meter_disabled and self._snap.get(hk) is not None:
                        used = self._update_energy_from_meter(house_meter, hk, hak, "house", p)
                        meter_mode[hak] = "meter" if used else "trapez"
                    elif not use_derived_house:
                        self._acc[hak] += delta_house_trap
                        meter_mode[hak] = "trapez"
                    else:
                        meter_mode[hak] = "derived"

                    if grid_meter is not None and gk not in self._meter_disabled and self._snap.get(gk) is not None:
                        used = self._update_energy_from_meter(grid_meter, gk, gak, "grid", p)
                        meter_mode[gak] = "meter" if used else "trapez"
                    else:
                        self._acc[gak] += delta_grid_trap
                        meter_mode[gak] = "trapez"

                if use_derived_house:
                    for p in PERIODS:
                        if physical_mode:
                            # Hauptzaehler-Netzbezug enthaelt eine eventuelle AC-Netzladung.
                            # Diese ist kein Hausverbrauch. Dagegen ist outputHomePower der
                            # tatsaechliche AC-Beitrag des SolarFlow zum Haus.
                            self._acc[f"house_{p}"] = max(
                                0.0,
                                self._acc[f"grid_{p}"] - self._acc[f"grid_charge_{p}"] + self._acc[f"home_output_{p}"],
                            )
                        else:
                            solar_direct = max(0.0, self._acc[f"solar_{p}"] - self._acc[f"bat_charge_{p}"])
                            self._acc[f"solar_direct_{p}"] = solar_direct
                            self._acc[f"battery_to_house_{p}"] = self._acc[f"bat_discharge_{p}"]
                            self._acc[f"house_{p}"] = max(0.0, self._acc[f"grid_{p}"] + solar_direct + self._acc[f"bat_discharge_{p}"])

        self._last_power["solar"] = solar_total_w
        self._last_power["bat_charge"] = bat_charge_w
        self._last_power["bat_discharge"] = bat_discharge_w
        self._last_power["house"] = house_power_w
        self._last_power["grid"] = grid_power_w
        if physical_valid:
            for key in ("home_output", "grid_charge", "grid_to_battery", "solar_to_battery", "solar_direct", "battery_to_house", "grid_to_home"):
                self._last_power[key] = physical.get(key)
        elif physical_mode:
            for key in ("home_output", "grid_charge", "grid_to_battery", "solar_to_battery", "solar_direct", "battery_to_house", "grid_to_home"):
                self._last_power[key] = None
        self._last_update = now

        def _fp(p: str) -> dict[str, float]:
            if physical_mode:
                solar_direct = max(0.0, self._acc[f"solar_direct_{p}"])
                bat_to_house = max(0.0, self._acc[f"battery_to_house_{p}"])
                house = max(0.0, self._acc[f"house_{p}"])
                return {
                    "solar_direct": solar_direct,
                    "bat_to_house": bat_to_house,
                    "net": max(0.0, self._acc[f"grid_{p}"]),
                    "solar_surplus": max(0.0, self._acc[f"solar_{p}"] - self._acc[f"solar_to_battery_{p}"] - solar_direct),
                    "house_total": house,
                    "autark_covered": solar_direct + bat_to_house,
                }
            house_arg = None if use_derived_house else self._acc[f"house_{p}"]
            return calculate_energy_flows(
                self._acc[f"solar_{p}"], self._acc[f"bat_discharge_{p}"],
                self._acc[f"bat_charge_{p}"], house_arg,
                self._acc[f"grid_{p}"] if self._acc[f"grid_{p}"] > 0 else 0.0,
            )

        fp_today = _fp("today")
        fp_week = _fp("week")
        fp_month = _fp("month")
        fp_year = _fp("year")

        aut_today = calculate_autarky(fp_today["solar_direct"], fp_today["bat_to_house"], self._acc["house_today"])
        aut_week = calculate_autarky(fp_week["solar_direct"], fp_week["bat_to_house"], self._acc["house_week"])
        aut_month = calculate_autarky(fp_month["solar_direct"], fp_month["bat_to_house"], self._acc["house_month"])
        aut_year = calculate_autarky(fp_year["solar_direct"], fp_year["bat_to_house"], self._acc["house_year"])
        current_price, current_price_source = self._current_price(now)
        year_grid_cost, year_savings, year_price_source = self._year_price_costs(now, fp_year, fp_month)

        # Diagnostik
        source_map: dict[str, Optional[str]] = {}
        unavail: list[str] = []
        for label, key in [
            ("Zendure Solar Leistung", CONF_ZENDURE_SOLAR),
            ("Zendure Solar Energie", CONF_ZENDURE_SOLAR_ENERGY),
            ("EcoFlow Solar Leistung", CONF_ECOFLOW_SOLAR),
            ("EcoFlow Solar 2 Leistung", CONF_ECOFLOW_SOLAR_2),
            ("EcoFlow Solar Energie", CONF_ECOFLOW_SOLAR_ENERGY),
            ("EcoFlow Solar 2 Energie", CONF_ECOFLOW_SOLAR_2_ENERGY),
            ("Bat Charge Leistung", CONF_BATTERY_CHARGE),
            ("Bat Charge Energie", CONF_BATTERY_CHARGE_ENERGY),
            ("Bat Discharge Leistung", CONF_BATTERY_DISCHARGE),
            ("Bat Discharge Energie", CONF_BATTERY_DISCHARGE_ENERGY),
            ("Battery SOC", CONF_BATTERY_SOC),

            ("House Power", CONF_HOUSE_POWER), ("House Energy", CONF_HOUSE_ENERGY),
            ("Grid Power", CONF_GRID_POWER), ("Grid Energy", CONF_GRID_ENERGY),
            ("Phase L1", CONF_PHASE1_POWER), ("Phase L2", CONF_PHASE2_POWER), ("Phase L3", CONF_PHASE3_POWER),
        ]:
            eid = self._get_entity(key)
            source_map[label] = eid
            if eid is None:
                unavail.append(f"{label}: nicht konfiguriert")

        if qi:
            self.diag["data_quality_issues"].extend(qi)
        if battery_capacity and self._acc["bat_discharge_today"] > battery_capacity * 1.05:
            self.diag["data_quality_issues"].append(
                f"Speicherabgabe heute ({self._acc['bat_discharge_today']:.2f} kWh) > Batteriekapazität ({battery_capacity:.2f} kWh) – Sensorwerte prüfen"
            )
        self.diag["data_quality_issues"] = self.diag["data_quality_issues"][-50:]

        source_map.update({
            "SolarFlow PV physikalisch": ZENDURE_FLOW_ENTITIES["pv"],
            "SolarFlow Netzladung physikalisch": ZENDURE_FLOW_ENTITIES["grid_charge"],
            "SolarFlow AC ans Haus physikalisch": ZENDURE_FLOW_ENTITIES["home_output"],
            "SolarFlow Batterie laden physikalisch": ZENDURE_FLOW_ENTITIES["battery_charge"],
            "SolarFlow Batterie entladen physikalisch": ZENDURE_FLOW_ENTITIES["battery_discharge"],
        })
        self.diag.update({
            "source_mapping": source_map,
            "physical_flow_mode": physical_mode,
            "physical_flow_data_valid": physical_valid,
            "unavailable_sources": unavail,
            "last_calc": now.isoformat(),
            "meter_mode": meter_mode,
            "meter_disabled_due_to_startvalue": sorted(self._meter_disabled),
            "last_backup": self._backup_mgr.last_backup_time,
            "last_restore": self._backup_mgr.last_restore_time,
            "restore_log": self._backup_mgr.restore_log,
            # archive_errors bleibt akkumuliert (nicht überschrieben)
            "last_csv_write": self._archive.last_write_times,
            "grid_price_current": current_price,
            "grid_price_source": current_price_source,
            "monthly_prices": self._monthly_prices(),
            "year_price_source": year_price_source,
            "battery_capacity_kwh": battery_capacity,
            "battery_soc": battery_soc,
        })

        def _diff_pct(current: float, cmp_key: str):
            prev = self._cmp.get(cmp_key)
            return safe_subtract(current, prev), calculate_pct_change(current, prev)

        data: dict[str, Any] = {
            "solar_power_zendure": round_value(solar_z),
            "solar_power_ecoflow": round_value(solar_e),
            "solar_power_total": round_value(solar_total_w),
            "battery_charge_power": round_value(bat_charge_w),
            "battery_discharge_power": round_value(bat_discharge_w),
            "zendure_home_output_power": round_value(physical.get("home_output") if physical_mode else None),
            "grid_charge_power": round_value(physical.get("grid_charge") if physical_mode else None),
            "battery_soc": round_value(battery_soc, 1),
            "battery_remaining_kwh": round_value((battery_soc or 0.0) / 100.0 * battery_capacity, 3) if battery_soc is not None and battery_capacity else None,
            "battery_free_kwh": round_value((100.0 - (battery_soc or 0.0)) / 100.0 * battery_capacity, 3) if battery_soc is not None and battery_capacity else None,
            "house_power": round_value(house_power_w),
            "grid_power": round_value(grid_power_w),
            "current_grid_price": round_value(current_price, 4),
        }

        for p, fp, aut in [
            ("today", fp_today, aut_today),
            ("week", fp_week, aut_week),
            ("month", fp_month, aut_month),
            ("year", fp_year, aut_year),
        ]:
            data.update({
                f"solar_energy_{p}": round_value(self._acc[f"solar_{p}"]),
                f"battery_charge_{p}": round_value(self._acc[f"bat_charge_{p}"]),
                f"battery_discharge_{p}": round_value(self._acc[f"bat_discharge_{p}"]),
                f"house_energy_{p}": round_value(self._acc[f"house_{p}"]),
                f"grid_energy_{p}": round_value(self._acc[f"grid_{p}"]),
                f"home_output_{p}": round_value(self._acc[f"home_output_{p}"]),
                f"grid_charge_{p}": round_value(self._acc[f"grid_charge_{p}"]),
                f"grid_to_battery_{p}": round_value(self._acc[f"grid_to_battery_{p}"]),
                f"solar_to_battery_{p}": round_value(self._acc[f"solar_to_battery_{p}"]),
                f"grid_to_home_{p}": round_value(self._acc[f"grid_to_home_{p}"]),
                f"solar_direct_{p}": round_value(self._acc[f"solar_direct_{p}"]),
                f"battery_share_{p}": round_value(fp["bat_to_house"]),
                f"solar_share_{p}": round_value(fp["solar_direct"]),
                f"grid_cost_{p}": round_value(year_grid_cost if p == "year" else self._acc[f"grid_{p}"] * current_price, 2),
                f"solar_savings_{p}": round_value(year_savings if p == "year" else (fp["solar_direct"] + fp["bat_to_house"]) * current_price, 2),
                f"autarky_{p}": round_value(aut, 1),
                f"self_consumption_ratio_{p}": round_value(
                    min(100.0, max(0.0, ((fp['solar_direct'] + self._acc.get('solar_to_battery_' + p, 0.0)) / self._acc.get('solar_' + p, 1.0) * 100.0)))
                    if self._acc.get('solar_' + p, 0.0) > 0 else 0.0, 1
                ),
                # V5.8: echte Plausibilitaetswerte gegen unabhaengige Messpunkte.
                f"audit_house_balance_error_{p}": round_value(
                    self._acc[f"house_{p}"] - (self._acc[f"grid_{p}"] - self._acc[f"grid_charge_{p}"] + self._acc[f"home_output_{p}"]), 3
                ),
                f"audit_solar_balance_rest_{p}": round_value(
                    max(0.0, self._acc[f"solar_{p}"] - self._acc[f"solar_to_battery_{p}"] - self._acc[f"solar_direct_{p}"]), 3
                ),
                f"audit_battery_delta_{p}": round_value(
                    max(0.0, self._acc[f"bat_discharge_{p}"] - fp["bat_to_house"]), 3
                ),
                f"grid_charge_conversion_loss_{p}": round_value(
                    max(0.0, self._acc[f"grid_charge_{p}"] - self._acc[f"grid_to_battery_{p}"]), 3
                ),
            })

        aut_map = {"yesterday": aut_today, "week": aut_week, "month": aut_month, "year": aut_year}

        for suffix, short in [
            ("yesterday", "yesterday"), ("last_week", "week"),
            ("last_month", "month"), ("last_year", "year")
        ]:
            cur_period = {"yesterday": "today"}.get(short, short)
            cur_aut = aut_map[short]

            for metric, prefix in [
                ("solar", "solar_energy"),
                ("grid", "grid_energy"),
                ("house", "house_energy"),
                ("bat_charge", "battery_charge"),
                ("bat_discharge", "battery_discharge"),
                ("solar_direct", "solar_direct"),
            ]:
                cur_val = self._acc[f"{metric}_{cur_period}"]
                d, p = _diff_pct(cur_val, f"{metric}_{suffix}")
                data[f"{prefix}_{suffix}"] = round_value(self._cmp.get(f"{metric}_{suffix}"))
                data[f"{prefix}_diff_{short}"] = round_value(d)
                data[f"{prefix}_pct_{short}"] = round_value(p, 1)

            d, _ = _diff_pct(cur_aut, f"autarky_{suffix}")
            data[f"autarky_{suffix}"] = round_value(self._cmp.get(f"autarky_{suffix}"), 1)
            data[f"autarky_diff_{short}"] = round_value(d, 1)

        data["diagnostics"] = self.diag.copy()
        return data

    # ── Perioden-Resets ───────────────────────────────────────────────────────

    def _check_period_resets(self, now: datetime) -> None:
        day = now.timetuple().tm_yday
        iso = now.isocalendar()
        week_key = iso[0] * 100 + iso[1]
        month = now.month
        year = now.year

        if self._period["day"] is not None and day != self._period["day"]:
            self._do_daily_reset(now)
        if self._period["week"] is not None and week_key != self._period["week"]:
            self._do_weekly_reset(now, iso[0], iso[1])
        if self._period["month"] is not None and month != self._period["month"]:
            self._do_monthly_reset(now)
        if self._period["year"] is not None and year != self._period["year"]:
            self._do_yearly_reset(now)

        self._period["day"] = day
        self._period["week"] = week_key
        self._period["month"] = month
        self._period["year"] = year

    def _snapshot_period(self, period: str, price_date: Optional[datetime] = None) -> dict[str, float]:
        if self._physical_flow_capable():
            fp = {
                "solar_direct": max(0.0, self._acc[f"solar_direct_{period}"]),
                "bat_to_house": max(0.0, self._acc[f"battery_to_house_{period}"]),
            }
        else:
            fp = calculate_energy_flows(
                self._acc[f"solar_{period}"], self._acc[f"bat_discharge_{period}"],
                self._acc[f"bat_charge_{period}"], self._acc[f"house_{period}"],
                self._acc[f"grid_{period}"] if self._acc[f"grid_{period}"] > 0 else None,
            )
        aut = calculate_autarky(fp["solar_direct"], fp["bat_to_house"], self._acc[f"house_{period}"])
        ref_date = price_date or dt_util.now()
        price, _source = self._current_price(ref_date)
        return {
            "solar": self._acc[f"solar_{period}"],
            "bat_charge": self._acc[f"bat_charge_{period}"],
            "bat_discharge": self._acc[f"bat_discharge_{period}"],
            "house": self._acc[f"house_{period}"],
            "grid": self._acc[f"grid_{period}"],
            "solar_direct": self._acc[f"solar_direct_{period}"],
            "bat_to_house": fp["bat_to_house"],
            "home_output": self._acc[f"home_output_{period}"],
            "grid_charge": self._acc[f"grid_charge_{period}"],
            "grid_to_battery": self._acc[f"grid_to_battery_{period}"],
            "solar_to_battery": self._acc[f"solar_to_battery_{period}"],
            "grid_to_home": self._acc[f"grid_to_home_{period}"],
            "autarky": aut,
            "grid_price_per_kwh": price,
            "grid_cost": self._acc[f"grid_{period}"] * price,
            "solar_savings": (fp["solar_direct"] + fp["bat_to_house"]) * price,
        }

    def _save_compare(self, suffix: str, snap: dict[str, float]) -> None:
        for k in ("solar", "bat_charge", "bat_discharge", "house", "grid", "solar_direct", "autarky"):
            self._cmp[f"{k}_{suffix}"] = snap.get(k)

    def _reset_period_acc(self, period: str) -> None:
        for f in ACC_FIELDS:
            self._acc[f"{f}_{period}"] = 0.0

    def _reset_meter_snapshots_for_period(self, period: str) -> None:
        """Setzt Zähler-Snapshots für einen neu beginnenden Zeitraum."""
        readers = {
            "solar": self._read_solar_energy_kwh,
            "bat_charge": self._read_bat_charge_energy_kwh,
            "bat_discharge": self._read_bat_discharge_energy_kwh,
            "house": self._read_house_energy_kwh,
            "grid": self._read_grid_energy_kwh,
        }
        for metric, reader in readers.items():
            key = f"{metric}_{period}_start"
            self._meter_disabled.discard(key)
            self._snap[key] = reader()

    def _do_daily_reset(self, now: datetime) -> None:
        yesterday_dt = now - timedelta(days=1)
        snap = self._snapshot_period("today", yesterday_dt)
        self._save_compare("yesterday", snap)
        yesterday = yesterday_dt.strftime("%Y-%m-%d")
        self._archive.schedule_write(self._archive.write_daily, yesterday, snap)
        self._reset_meter_snapshots_for_period("today")
        self._reset_period_acc("today")
        _LOGGER.info("Tagesreset: %s", yesterday)

    def _do_weekly_reset(self, now: datetime, iso_year: int, iso_week: int) -> None:
        snap = self._snapshot_period("week", now - timedelta(days=1))
        self._save_compare("last_week", snap)
        prev_w = iso_week - 1
        prev_y = iso_year
        if prev_w == 0:
            prev_y -= 1
            prev_w = datetime(prev_y, 12, 28).isocalendar()[1]
        week_str = f"{prev_y}-W{prev_w:02d}"
        self._archive.schedule_write(self._archive.write_weekly, week_str, snap)
        self._reset_meter_snapshots_for_period("week")
        self._reset_period_acc("week")
        _LOGGER.info("Wochenreset: %s", week_str)

    def _do_monthly_reset(self, now: datetime) -> None:
        prev = (now.replace(day=1) - timedelta(days=1))
        snap = self._snapshot_period("month", prev)
        self._save_compare("last_month", snap)
        month_str = prev.strftime("%Y-%m")
        self._archive.schedule_write(self._archive.write_monthly, month_str, snap)
        self._reset_meter_snapshots_for_period("month")
        self._reset_period_acc("month")
        _LOGGER.info("Monatsreset: %s", month_str)

    def _do_yearly_reset(self, now: datetime) -> None:
        prev_year_date = now.replace(year=now.year - 1, month=12, day=31)
        snap = self._snapshot_period("year", prev_year_date)
        self._save_compare("last_year", snap)
        year_str = str(now.year - 1)
        self._archive.schedule_write(self._archive.write_yearly, year_str, snap)
        self._reset_meter_snapshots_for_period("year")
        self._reset_period_acc("year")
        _LOGGER.info("Jahresreset: %s", year_str)

    # ── Storage ───────────────────────────────────────────────────────────────

    async def _async_load_state(self) -> None:
        stored = await self._store.async_load()

        if stored is not None:
            try:
                for k in self._acc:
                    if k in stored.get("accumulators", {}):
                        self._acc[k] = float(stored["accumulators"][k])
                for k in self._cmp:
                    v = stored.get("compare_values", {}).get(k)
                    self._cmp[k] = float(v) if v is not None else None
                for k in self._period:
                    v = stored.get("period_timestamps", {}).get(k)
                    self._period[k] = int(v) if v is not None else None
                for k in self._snap:
                    v = stored.get("energy_snapshots", {}).get(k)
                    self._snap[k] = float(v) if v is not None else None
                self._init_applied = bool(stored.get("init_applied", False))
                _LOGGER.info("Zustand aus HA Storage geladen")
            except Exception as err:
                _LOGGER.warning("HA Storage Ladefehler: %s – Neustart", err)
        else:
            _LOGGER.info("Kein HA Storage – versuche Backup-Restore")
            (
                self._acc, self._cmp, self._period, self._snap,
                self._init_applied, log,
            ) = await self._backup_mgr.async_restore(
                self._acc, self._cmp, self._period, self._snap,
                force_overwrite=False,
            )
            self.diag["restore_log"] = log

    async def async_save_state(self) -> None:
        """Speichert vollständigen Zustand in HA Storage + Backup."""
        data = {
            "accumulators": dict(self._acc),
            "compare_values": dict(self._cmp),
            "period_timestamps": dict(self._period),
            "energy_snapshots": dict(self._snap),
            "init_applied": self._init_applied,
            "saved_at": dt_util.now().isoformat(),
        }
        await self._store.async_save(data)

        await self._backup_mgr.async_save_backup(
            accumulators=self._acc,
            compare_values=self._cmp,
            period_timestamps=self._period,
            energy_snapshots=self._snap,
            init_applied=self._init_applied,
            init_values={k: self.config.get(k) for k in ALL_INIT_KEYS},
            source_mapping=self.diag.get("source_mapping", {}),
        )

    @callback
    def update_config(self, new_config: dict) -> None:
        old_init = {k: self.config.get(k) for k in ALL_INIT_KEYS}
        new_init = {k: new_config.get(k) for k in ALL_INIT_KEYS}
        self.config = new_config
        if old_init != new_init:
            self._init_applied = False
            self._apply_init_values()
        self._register_state_listeners()
