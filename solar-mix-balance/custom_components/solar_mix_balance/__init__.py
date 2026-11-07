"""Solar Mix Balance 5.8.2.

Änderungen vs V4.1:
- manifest.json ohne integration_type (robusteste Variante, Standard = Integrationsliste)
- CONFIG_ENTRY_VERSION = 5, MINOR_VERSION = 1
- async_migrate_entry: unterstützt alle Quellversionen 1–4
- async_setup_entry: Exception in async_setup wird abgefangen und False zurückgegeben
- VERSION 5.7.0: Snapshot-, Audit-, SOC- und Plausibilitäts-Fixes
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, Event, ServiceCall
from homeassistant.helpers.event import async_track_time_interval
import voluptuous as vol

from .const import DOMAIN, COORDINATOR, PLATFORMS, VERSION, ALL_SENSOR_GROUPS, CONF_MONTHLY_PRICES, CONF_MONTHLY_GRID_KWH, CONF_GRID_PRICE, DEFAULT_GRID_PRICE
from .coordinator import SolarMixBalanceCoordinator

_LOGGER = logging.getLogger(__name__)

SAVE_INTERVAL = timedelta(minutes=5)

CONFIG_ENTRY_VERSION = 5
CONFIG_ENTRY_MINOR_VERSION = 7


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migriert bestehende Config Entries auf Version 5.

    Alle bestehenden Mappings, Sensorgruppen und Startwerte werden
    unverändert übernommen. Nur fehlende Felder bekommen Defaults.
    Keine Neueinrichtung erforderlich.
    """
    current_v = entry.version
    current_mv = getattr(entry, "minor_version", 1)
    _LOGGER.info(
        "Solar Mix Balance: Migriere %s von V%s.%s → V%s.%s",
        entry.entry_id, current_v, current_mv,
        CONFIG_ENTRY_VERSION, CONFIG_ENTRY_MINOR_VERSION,
    )

    if current_v == CONFIG_ENTRY_VERSION and current_mv == CONFIG_ENTRY_MINOR_VERSION:
        return True

    new_data = dict(entry.data)

    if "sensor_groups" not in new_data:
        new_data["sensor_groups"] = ALL_SENSOR_GROUPS
        _LOGGER.info("Migration: sensor_groups → alle Gruppen als Default")

    if "grid_price_per_kwh" not in new_data or new_data.get("grid_price_per_kwh") in (None, ""):
        new_data["grid_price_per_kwh"] = 0.30

    if CONF_MONTHLY_PRICES not in new_data or not isinstance(new_data.get(CONF_MONTHLY_PRICES), dict):
        new_data[CONF_MONTHLY_PRICES] = {}
    if CONF_MONTHLY_GRID_KWH not in new_data or not isinstance(new_data.get(CONF_MONTHLY_GRID_KWH), dict):
        new_data[CONF_MONTHLY_GRID_KWH] = {}

    for field in [
        "zendure_solar_entity", "zendure_solar_energy_entity",
        "ecoflow_solar_entity", "ecoflow_solar_2_entity",
        "ecoflow_solar_energy_entity", "ecoflow_solar_2_energy_entity",
        "battery_charge_entity", "battery_charge_energy_entity",
        "battery_discharge_entity", "battery_discharge_energy_entity",
        "house_power_entity", "house_energy_entity",
        "grid_power_entity", "grid_energy_entity",
        "phase1_power_entity", "phase2_power_entity", "phase3_power_entity",
        "battery_soc_entity", "battery_capacity_kwh",
    ]:
        if field not in new_data:
            new_data[field] = None

    # Update-Komfort: bekannte kWh-Gesamtzähler aus bisheriger Helferlogik
    # automatisch eintragen, wenn das neue Feld leer ist und die Entität existiert.
    auto_defaults = {
        "zendure_solar_energy_entity": "sensor.solarflow_800_pro_aggr_solar_total",
        "battery_charge_energy_entity": "sensor.solarflow_800_pro_aggr_charge_total",
        "battery_discharge_energy_entity": "sensor.solarflow_800_pro_aggr_discharge_total",
    }
    for field, entity_id in auto_defaults.items():
        if not new_data.get(field) and hass.states.get(entity_id) is not None:
            new_data[field] = entity_id
            _LOGGER.info("Migration V5.7: %s automatisch auf %s gesetzt", field, entity_id)

    for field in [
        "init_solar_week", "init_solar_month", "init_solar_year",
        "init_grid_week", "init_grid_month", "init_grid_year",
        "init_bat_charge_week", "init_bat_charge_month", "init_bat_charge_year",
        "init_bat_discharge_week", "init_bat_discharge_month", "init_bat_discharge_year",
        "init_house_week", "init_house_month", "init_house_year",
        "init_solar_direct_week", "init_solar_direct_month", "init_solar_direct_year",
        "grid_price_per_kwh",
    ]:
        if field not in new_data:
            new_data[field] = None

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )

    kept = {k: v for k, v in new_data.items() if k.endswith("_entity") and v is not None}
    _LOGGER.info("Migration V5 abgeschlossen. Beibehaltene Mappings: %s", kept)
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Registriert schnelle Dienste für Strompreise.

    Damit muss man nicht jedes Mal durch die komplette Options-Konfiguration,
    sondern kann monatliche vivi-power-Preise direkt per Dienst setzen.
    """
    async def _set_month_price(call: ServiceCall) -> None:
        year = int(call.data.get("year") or 0)
        month = int(call.data["month"])
        price = max(0.0, float(call.data["price"]))
        if year <= 0:
            from homeassistant.util import dt as dt_util
            year = dt_util.now().year
        key = f"{year:04d}-{month:02d}"

        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
            new_data = dict(cfg_entry.data)
            prices = dict(new_data.get(CONF_MONTHLY_PRICES) or {})
            prices[key] = price
            new_data[CONF_MONTHLY_PRICES] = prices
            hass.config_entries.async_update_entry(cfg_entry, data=new_data)

            coord = hass.data.get(DOMAIN, {}).get(cfg_entry.entry_id, {}).get(COORDINATOR)
            if coord is not None:
                coord.update_config(new_data)
                await coord.async_request_refresh()

        _LOGGER.info("Solar Mix Balance: Monatspreis gesetzt %s = %.4f €/kWh", key, price)

    async def _clear_month_price(call: ServiceCall) -> None:
        year = int(call.data.get("year") or 0)
        month = int(call.data["month"])
        if year <= 0:
            from homeassistant.util import dt as dt_util
            year = dt_util.now().year
        key = f"{year:04d}-{month:02d}"

        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
            new_data = dict(cfg_entry.data)
            prices = dict(new_data.get(CONF_MONTHLY_PRICES) or {})
            prices.pop(key, None)
            new_data[CONF_MONTHLY_PRICES] = prices
            hass.config_entries.async_update_entry(cfg_entry, data=new_data)

            coord = hass.data.get(DOMAIN, {}).get(cfg_entry.entry_id, {}).get(COORDINATOR)
            if coord is not None:
                coord.update_config(new_data)
                await coord.async_request_refresh()

        _LOGGER.info("Solar Mix Balance: Monatspreis gelöscht %s", key)

    async def _set_month_grid_energy(call: ServiceCall) -> None:
        """Speichert belegten Monats-Netzbezug für fehlende historische Monatsarchive."""
        year = int(call.data.get("year") or 0)
        month = int(call.data["month"])
        kwh = max(0.0, float(call.data["kwh"]))
        if year <= 0:
            from homeassistant.util import dt as dt_util
            year = dt_util.now().year
        key = f"{year:04d}-{month:02d}"

        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
            new_data = dict(cfg_entry.data)
            values = dict(new_data.get(CONF_MONTHLY_GRID_KWH) or {})
            values[key] = kwh
            new_data[CONF_MONTHLY_GRID_KWH] = values
            hass.config_entries.async_update_entry(cfg_entry, data=new_data)

            coord = hass.data.get(DOMAIN, {}).get(cfg_entry.entry_id, {}).get(COORDINATOR)
            if coord is not None:
                coord.update_config(new_data)
                await coord.async_request_refresh()

        _LOGGER.info("Solar Mix Balance: Monats-Netzbezug gesetzt %s = %.3f kWh", key, kwh)

    async def _clear_month_grid_energy(call: ServiceCall) -> None:
        year = int(call.data.get("year") or 0)
        month = int(call.data["month"])
        if year <= 0:
            from homeassistant.util import dt as dt_util
            year = dt_util.now().year
        key = f"{year:04d}-{month:02d}"

        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
            new_data = dict(cfg_entry.data)
            values = dict(new_data.get(CONF_MONTHLY_GRID_KWH) or {})
            values.pop(key, None)
            new_data[CONF_MONTHLY_GRID_KWH] = values
            hass.config_entries.async_update_entry(cfg_entry, data=new_data)

            coord = hass.data.get(DOMAIN, {}).get(cfg_entry.entry_id, {}).get(COORDINATOR)
            if coord is not None:
                coord.update_config(new_data)
                await coord.async_request_refresh()

        _LOGGER.info("Solar Mix Balance: Monats-Netzbezug gelöscht %s", key)

    async def _calibrate_period(call: ServiceCall) -> None:
        """Setzt einen Energie-Akkumulator samt Zähler-Snapshot kontrolliert neu."""
        metric = str(call.data["metric"])
        period = str(call.data["period"])
        value = max(0.0, float(call.data["value"]))

        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
            coord = hass.data.get(DOMAIN, {}).get(cfg_entry.entry_id, {}).get(COORDINATOR)
            if coord is None:
                continue
            acc_key = f"{metric}_{period}"
            if acc_key in coord._acc:
                coord._acc[acc_key] = value
            else:
                cmp_key = f"{metric}_{period}"
                if cmp_key not in coord._cmp:
                    continue
                coord._cmp[cmp_key] = value
                await coord.async_save_state()
                await coord.async_request_refresh()
                _LOGGER.warning("Solar Mix Balance: Vergleich %s auf %.3f kalibriert", cmp_key, value)
                continue

            readers = {
                "solar": coord._read_solar_energy_kwh,
                "bat_charge": coord._read_bat_charge_energy_kwh,
                "bat_discharge": coord._read_bat_discharge_energy_kwh,
                "house": coord._read_house_energy_kwh,
                "grid": coord._read_grid_energy_kwh,
            }
            reader = readers.get(metric)
            if reader is not None:
                meter = reader()
                snap_key = f"{metric}_{period}_start"
                if meter is not None and meter >= value:
                    coord._snap[snap_key] = meter - value
                    coord._meter_disabled.discard(snap_key)
                else:
                    coord._snap[snap_key] = None
                    coord._meter_disabled.add(snap_key)

            await coord.async_save_state()
            await coord.async_request_refresh()
            _LOGGER.warning(
                "Solar Mix Balance: %s/%s auf %.3f kWh kalibriert",
                metric, period, value,
            )

    month_schema = vol.All(vol.Coerce(int), vol.Range(min=1, max=12))
    year_schema = vol.All(vol.Coerce(int), vol.Range(min=0, max=2100))
    price_schema = vol.All(vol.Coerce(float), vol.Range(min=0, max=5))
    kwh_schema = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=999999.0))

    if not hass.services.has_service(DOMAIN, "set_month_price"):
        hass.services.async_register(
            DOMAIN,
            "set_month_price",
            _set_month_price,
            schema=vol.Schema({
                vol.Required("month"): month_schema,
                vol.Required("price"): price_schema,
                vol.Optional("year", default=0): year_schema,
            }),
        )
    if not hass.services.has_service(DOMAIN, "clear_month_price"):
        hass.services.async_register(
            DOMAIN,
            "clear_month_price",
            _clear_month_price,
            schema=vol.Schema({
                vol.Required("month"): month_schema,
                vol.Optional("year", default=0): year_schema,
            }),
        )
    if not hass.services.has_service(DOMAIN, "set_month_grid_energy"):
        hass.services.async_register(
            DOMAIN,
            "set_month_grid_energy",
            _set_month_grid_energy,
            schema=vol.Schema({
                vol.Required("month"): month_schema,
                vol.Required("kwh"): kwh_schema,
                vol.Optional("year", default=0): year_schema,
            }),
        )
    if not hass.services.has_service(DOMAIN, "clear_month_grid_energy"):
        hass.services.async_register(
            DOMAIN,
            "clear_month_grid_energy",
            _clear_month_grid_energy,
            schema=vol.Schema({
                vol.Required("month"): month_schema,
                vol.Optional("year", default=0): year_schema,
            }),
        )
    if not hass.services.has_service(DOMAIN, "calibrate_period"):
        hass.services.async_register(
            DOMAIN,
            "calibrate_period",
            _calibrate_period,
            schema=vol.Schema({
                vol.Required("metric"): vol.In(["solar", "bat_charge", "bat_discharge", "house", "grid", "solar_direct", "home_output", "grid_charge", "grid_to_battery", "solar_to_battery", "battery_to_house", "grid_to_home", "autarky"]),
                vol.Required("period"): vol.In(["today", "week", "month", "year", "yesterday", "last_week", "last_month", "last_year"]),
                vol.Required("value"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=999999.0)),
            }),
        )



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration einrichten."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SolarMixBalanceCoordinator(hass, entry)

    try:
        await coordinator.async_setup()
    except Exception as err:
        _LOGGER.error("coordinator.async_setup() fehlgeschlagen: %s", err, exc_info=True)
        return False

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Erster Update fehlgeschlagen (%s) – Fallback-Modus", err)

    hass.data[DOMAIN][entry.entry_id] = {COORDINATOR: coordinator}
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _periodic_save(_now: Any) -> None:
        try:
            await coordinator.async_save_state()
        except Exception as err:
            _LOGGER.debug("Periodisches Speichern fehlgeschlagen: %s", err)

    entry.async_on_unload(async_track_time_interval(hass, _periodic_save, SAVE_INTERVAL))

    async def _on_ha_stop(event: Event) -> None:
        coord = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(COORDINATOR)
        if coord is not None:
            try:
                await coord.async_shutdown()
            except Exception as err:
                _LOGGER.error("Fehler beim HA-Stop: %s", err)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _on_ha_stop)
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info("Solar Mix Balance V%s geladen: %s", VERSION, entry.entry_id)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coord = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(COORDINATOR)
    if coord is None:
        return
    old_groups = set(coord.config.get("sensor_groups", []))
    new_groups = set(entry.data.get("sensor_groups", []))
    coord.update_config(dict(entry.data))
    if old_groups != new_groups:
        _LOGGER.info("V5.7: Sensorgruppen geändert → Reload")
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(COORDINATOR)
    if coord is not None:
        try:
            await coord.async_shutdown()
        except Exception as err:
            _LOGGER.error("Fehler beim Unload: %s", err)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("V5.7 entladen: %s", entry.entry_id)
    return unload_ok
