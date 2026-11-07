"""Config Flow V5.7 – Fix #5: Entity-Validierung + ehrliche EntitySelector-Entscheidung.

Entscheidung EntitySelector vs SelectSelector (dokumentiert):

HA's EntitySelector zeigt nur Friendly Name + Entity-ID.
Die Anforderung lautet: Friendly Name | Entity-ID | aktueller Wert | Einheit.
Das ist mit EntitySelector NICHT nativ umsetzbar.

Daher: SelectSelector mit custom_value=True und display_label() als Option-Label.
Das ist die technisch korrekte und ehrliche Lösung für diese Anforderung.

FIX #5: Neu hinzugekommen: Validierung manuell eingegebener Entity-IDs.
Wenn ein Nutzer eine eigene entity_id eintippt, wird geprüft ob diese in HA existiert.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector, SelectSelectorConfig, SelectSelectorMode, SelectOptionDict,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
)

from .const import (
    DOMAIN, VERSION,
    CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2, CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
    CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY, CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC, DEFAULT_BATTERY_CAPACITY_KWH,
    CONF_HOUSE_POWER, CONF_HOUSE_ENERGY, CONF_GRID_POWER, CONF_GRID_ENERGY,
    CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
    CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS,
    CONF_INIT_SOLAR_WEEK, CONF_INIT_SOLAR_MONTH, CONF_INIT_SOLAR_YEAR,
    CONF_INIT_GRID_WEEK, CONF_INIT_GRID_MONTH, CONF_INIT_GRID_YEAR,
    CONF_INIT_BAT_CHARGE_WEEK, CONF_INIT_BAT_CHARGE_MONTH, CONF_INIT_BAT_CHARGE_YEAR,
    CONF_INIT_BAT_DISCHARGE_WEEK, CONF_INIT_BAT_DISCHARGE_MONTH, CONF_INIT_BAT_DISCHARGE_YEAR,
    CONF_INIT_HOUSE_WEEK, CONF_INIT_HOUSE_MONTH, CONF_INIT_HOUSE_YEAR,
    CONF_INIT_SOLAR_DIRECT_WEEK, CONF_INIT_SOLAR_DIRECT_MONTH, CONF_INIT_SOLAR_DIRECT_YEAR,
    CONF_BATTERY_CAPACITY_KWH, CONF_GRID_PRICE, CONF_MONTHLY_PRICES, DEFAULT_GRID_PRICE,
    SENSOR_GROUP_BASIC, SENSOR_GROUP_COMPARE, SENSOR_GROUP_DIAGNOSTICS, SENSOR_GROUP_EXPERT,
)
from .helpers import discover_entities, build_labeled_options, validate_entity_id

_LOGGER = logging.getLogger(__name__)

NONE_VALUE = "none"
PRICE_ACTION = "prices"
SOURCES_ACTION = "sources"
GROUPS_ACTION = "groups"
INIT_ACTION = "init_values"
MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

ENTITY_CONF_KEYS = [
    CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2,
    CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
    CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY, CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC,
    CONF_HOUSE_POWER, CONF_HOUSE_ENERGY,
    CONF_GRID_POWER, CONF_GRID_ENERGY,
    CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
]

GROUP_LABELS = {
    SENSOR_GROUP_BASIC: "Basiswerte (Live-Sensoren + Zeitraumwerte)",
    SENSOR_GROUP_COMPARE: "Vergleichswerte (Vortag, Vorwoche, Vormonat, Vorjahr)",
    SENSOR_GROUP_DIAGNOSTICS: "Diagnosewerte",
    SENSOR_GROUP_EXPERT: "Expertenwerte",
}

# Keys die nicht leer sein dürfen (mindestens einer muss gesetzt sein)
SOLAR_REQUIRED_KEYS = [CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2, CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY]


def _build_selector(labeled: list[tuple[str, str]]) -> SelectSelector:
    """SelectSelector mit lesbaren Labels.

    Hinweis: HA's EntitySelector wurde für diese Funktion evaluiert.
    EntitySelector unterstützt keine Anzeige des aktuellen Werts/Einheit.
    SelectSelector mit custom_value=True ist die korrekte Alternative.
    """
    opts = [SelectOptionDict(value=NONE_VALUE, label="– Nicht konfigurieren –")]
    for eid, label in labeled:
        opts.append(SelectOptionDict(value=eid, label=label))
    return SelectSelector(SelectSelectorConfig(
        options=opts,
        mode=SelectSelectorMode.DROPDOWN,
        custom_value=True,
    ))


def _build_entity_schema(
    candidates: dict[str, list[tuple[str, str]]],
    defaults: dict[str, str],
) -> vol.Schema:
    fields: dict = {}
    for key in ENTITY_CONF_KEYS:
        labeled = candidates.get(key, [])
        default = defaults.get(key, NONE_VALUE)
        fields[vol.Optional(key, default=default)] = _build_selector(labeled)
    return vol.Schema(fields)


def _build_groups_schema(defaults: list[str]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_SENSOR_GROUPS, default=defaults): SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=v) for k, v in GROUP_LABELS.items()],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
    })


def _build_init_schema(defaults: dict[str, Any]) -> vol.Schema:
    num = NumberSelector(NumberSelectorConfig(
        min=0.0, max=999999.0, step=0.001,
        mode=NumberSelectorMode.BOX, unit_of_measurement="kWh"
    ))

    def _opt(key: str) -> vol.Optional:
        return vol.Optional(key, default=defaults.get(key) or 0.0)

    return vol.Schema({
        vol.Optional(CONF_GRID_PRICE, default=defaults.get(CONF_GRID_PRICE, DEFAULT_GRID_PRICE)): NumberSelector(NumberSelectorConfig(
            min=0.0, max=5.0, step=0.001, mode=NumberSelectorMode.BOX, unit_of_measurement="€/kWh"
        )),
        _opt(CONF_INIT_SOLAR_WEEK): num, _opt(CONF_INIT_SOLAR_MONTH): num, _opt(CONF_INIT_SOLAR_YEAR): num,
        _opt(CONF_INIT_GRID_WEEK): num, _opt(CONF_INIT_GRID_MONTH): num, _opt(CONF_INIT_GRID_YEAR): num,
        _opt(CONF_INIT_BAT_CHARGE_WEEK): num, _opt(CONF_INIT_BAT_CHARGE_MONTH): num, _opt(CONF_INIT_BAT_CHARGE_YEAR): num,
        _opt(CONF_INIT_BAT_DISCHARGE_WEEK): num, _opt(CONF_INIT_BAT_DISCHARGE_MONTH): num, _opt(CONF_INIT_BAT_DISCHARGE_YEAR): num,
        _opt(CONF_INIT_HOUSE_WEEK): num, _opt(CONF_INIT_HOUSE_MONTH): num, _opt(CONF_INIT_HOUSE_YEAR): num,
        _opt(CONF_INIT_SOLAR_DIRECT_WEEK): num, _opt(CONF_INIT_SOLAR_DIRECT_MONTH): num, _opt(CONF_INIT_SOLAR_DIRECT_YEAR): num,
        vol.Optional(CONF_BATTERY_CAPACITY_KWH, default=defaults.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH)): NumberSelector(NumberSelectorConfig(
            min=0.0, max=100.0, step=0.01, mode=NumberSelectorMode.BOX, unit_of_measurement="kWh"
        )),
    })



def _price_key(month: int) -> str:
    return f"price_month_{month:02d}"


def _build_options_menu_schema(default: str = PRICE_ACTION) -> vol.Schema:
    return vol.Schema({
        vol.Required("action", default=default): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=PRICE_ACTION, label="Strompreise schnell bearbeiten"),
                    SelectOptionDict(value=SOURCES_ACTION, label="Quell-Entitäten ändern"),
                    SelectOptionDict(value=GROUPS_ACTION, label="Sensorgruppen ändern"),
                    SelectOptionDict(value=INIT_ACTION, label="Startwerte ändern"),
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    })


def _build_prices_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Robuste Strompreis-Seite für den Options Flow.

    0 bedeutet: für diesen Monat keinen Sonderpreis setzen, sondern den
    Fallback-Preis (CONF_GRID_PRICE) verwenden.

    Wichtig: Diese Seite verwendet absichtlich einfache Float-Felder statt
    dynamischer NumberSelector-Felder. Damit vermeiden wir den HA-Frontend-
    Fehler "Unknown error occurred" beim Öffnen der Preis-Seite.
    """
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_GRID_PRICE,
            default=defaults.get(CONF_GRID_PRICE, DEFAULT_GRID_PRICE),
        ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
    }
    for month in range(1, 13):
        schema[
            vol.Optional(
                _price_key(month),
                default=defaults.get(_price_key(month), 0.0) or 0.0,
            )
        ] = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0))
    return vol.Schema(schema)

def _monthly_price_defaults(entry_data: dict[str, Any], year: int) -> dict[str, Any]:
    defaults: dict[str, Any] = {CONF_GRID_PRICE: entry_data.get(CONF_GRID_PRICE, DEFAULT_GRID_PRICE)}
    monthly = entry_data.get(CONF_MONTHLY_PRICES) or {}
    if not isinstance(monthly, dict):
        monthly = {}
    for month in range(1, 13):
        defaults[_price_key(month)] = monthly.get(f"{year:04d}-{month:02d}", 0.0) or 0.0
    return defaults


def _extract_monthly_prices(user_input: dict[str, Any], current: dict[str, Any], year: int) -> dict[str, Any]:
    data = dict(current)
    data[CONF_GRID_PRICE] = user_input.get(CONF_GRID_PRICE, DEFAULT_GRID_PRICE)
    monthly = dict(data.get(CONF_MONTHLY_PRICES) or {})
    for month in range(1, 13):
        raw = user_input.get(_price_key(month), 0.0) or 0.0
        key = f"{year:04d}-{month:02d}"
        try:
            price = max(0.0, float(raw))
        except (TypeError, ValueError):
            price = 0.0
        if price > 0:
            monthly[key] = price
        else:
            monthly.pop(key, None)
    data[CONF_MONTHLY_PRICES] = monthly
    return data


def _sanitize(user_input: dict[str, Any]) -> dict[str, Any]:
    return {k: (None if v in (NONE_VALUE, "", None) else v) for k, v in user_input.items()}


def _discover_labeled(hass: Any) -> dict[str, list[tuple[str, str]]]:
    discovered = discover_entities(hass)
    return {key: build_labeled_options(cands, 20) for key, cands in discovered.items()}


def _validate_entity_inputs(
    hass: Any,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """FIX #5: Validiert manuell eingegebene Entity-IDs.

    Gibt dict mit Fehler-Keys zurück (leer = alles ok).
    Validierung:
    - Format (domain.name)
    - Entität muss in HA existieren
    - Warnung bei unavailable (kein Fehler)
    """
    errors: dict[str, str] = {}
    for key in ENTITY_CONF_KEYS:
        val = user_input.get(key)
        if val in (None, NONE_VALUE, "", "None"):
            continue
        valid, reason = validate_entity_id(hass, val)
        if not valid:
            errors[key] = "entity_not_found"
            _LOGGER.warning("Config Flow Validierung: %s → %s: %s", key, val, reason)
    return errors


class SolarMixBalanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """V5 Config Flow mit Entity-Validierung."""

    VERSION = 5
    MINOR_VERSION = 7

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._candidates: dict[str, list[tuple[str, str]]] = {}
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not self._candidates:
            self._candidates = _discover_labeled(self.hass)

        if user_input is not None:
            sanitized = _sanitize(user_input)

            # FIX #5: Entity-Validierung
            val_errors = _validate_entity_inputs(self.hass, sanitized)
            self._errors = val_errors

            if not any(sanitized.get(k) for k in SOLAR_REQUIRED_KEYS):
                self._errors["base"] = "no_solar_source"

            if not self._errors:
                self._data.update(sanitized)
                return await self.async_step_groups()

        defaults = {key: lbl[0][0] if lbl else NONE_VALUE for key, lbl in self._candidates.items()}
        return self.async_show_form(
            step_id="user",
            data_schema=_build_entity_schema(self._candidates, defaults),
            errors=self._errors,
            description_placeholders={
                "zendure_count": str(len(self._candidates.get(CONF_ZENDURE_SOLAR, []))),
                "ecoflow_count": str(len(self._candidates.get(CONF_ECOFLOW_SOLAR, []))),
                "house_count": str(len(self._candidates.get(CONF_HOUSE_POWER, []))),
                "version": VERSION,
            },
        )

    async def async_step_groups(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_SENSOR_GROUPS] = user_input.get(CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS) or [SENSOR_GROUP_BASIC]
            return await self.async_step_init_values()
        return self.async_show_form(step_id="groups", data_schema=_build_groups_schema(ALL_SENSOR_GROUPS))

    async def async_step_init_values(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            for k in list(user_input.keys()):
                if k == CONF_GRID_PRICE:
                    continue
                if user_input[k] is None or user_input[k] == 0.0:
                    user_input[k] = None
            self._data.update(user_input)
            return self.async_create_entry(title="Solar Mix Balance", data=self._data)
        return self.async_show_form(step_id="init_values", data_schema=_build_init_schema({'grid_price_per_kwh': DEFAULT_GRID_PRICE}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> "SolarMixOptionsFlow":
        return SolarMixOptionsFlow(entry)


class SolarMixOptionsFlow(config_entries.OptionsFlow):
    """V5.7.0 Options Flow mit robuster Strompreis-Seite.

    Die schnelle Strompreis-Seite verwendet einfache Float-Felder statt
    NumberSelector, weil der dynamische NumberSelector-Options-Flow in einigen
    HA-Frontend-Kombinationen mit "Unknown error occurred" abbrechen kann.
    """

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._candidates: dict[str, list[tuple[str, str]]] = {}
        self._new_data: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            action = user_input.get("action")
            try:
                if action == PRICE_ACTION:
                    return await self.async_step_prices()
                if action == SOURCES_ACTION:
                    return await self.async_step_sources()
                if action == GROUPS_ACTION:
                    return await self.async_step_groups()
                if action == INIT_ACTION:
                    return await self.async_step_init_values()
            except Exception:  # noqa: BLE001 - Options-Flow darf nicht hart abstürzen
                _LOGGER.exception("Fehler beim Öffnen des Options-Bereichs %s", action)
                errors["base"] = "options_step_failed"

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_menu_schema(),
            errors=errors,
            description_placeholders={"version": VERSION},
        )

    async def async_step_prices(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        from homeassistant.util import dt as dt_util

        year = dt_util.now().year
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                merged = _extract_monthly_prices(user_input, self._entry.data, year)
                self.hass.config_entries.async_update_entry(self._entry, data=merged)
                return self.async_create_entry(title="", data={})
            except Exception:  # noqa: BLE001 - Benutzer soll Fehler sehen, keinen Flow-Abbruch
                _LOGGER.exception("Fehler beim Speichern der Strompreise")
                errors["base"] = "price_save_failed"

        defaults = _monthly_price_defaults(self._entry.data, year)
        return self.async_show_form(
            step_id="prices",
            data_schema=_build_prices_schema(defaults),
            errors=errors,
            description_placeholders={"year": str(year)},
        )

    async def async_step_sources(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        if not self._candidates:
            self._candidates = _discover_labeled(self.hass)

        if user_input is not None:
            sanitized = _sanitize(user_input)
            val_errors = _validate_entity_inputs(self.hass, sanitized)
            self._errors = val_errors
            if not self._errors:
                self._new_data.update(sanitized)
                merged = {**self._entry.data, **self._new_data}
                self.hass.config_entries.async_update_entry(self._entry, data=merged)
                return self.async_create_entry(title="", data={})

        current = self._entry.data
        defaults = {key: current.get(key) or NONE_VALUE for key in ENTITY_CONF_KEYS}
        for key in ENTITY_CONF_KEYS:
            val = current.get(key)
            if val and val not in [eid for eid, _ in self._candidates.get(key, [])]:
                self._candidates.setdefault(key, []).insert(0, (val, val))

        return self.async_show_form(
            step_id="sources",
            data_schema=_build_entity_schema(self._candidates, defaults),
            errors=self._errors,
            description_placeholders={
                "zendure_count": str(len(self._candidates.get(CONF_ZENDURE_SOLAR, []))),
                "ecoflow_count": str(len(self._candidates.get(CONF_ECOFLOW_SOLAR, []))),
                "house_count": str(len(self._candidates.get(CONF_HOUSE_POWER, []))),
                "version": VERSION,
            },
        )

    async def async_step_groups(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            merged = {**self._entry.data, CONF_SENSOR_GROUPS: user_input.get(CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS)}
            self.hass.config_entries.async_update_entry(self._entry, data=merged)
            return self.async_create_entry(title="", data={})
        current_groups = self._entry.data.get(CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS)
        return self.async_show_form(step_id="groups", data_schema=_build_groups_schema(current_groups))

    async def async_step_init_values(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            cleaned = dict(user_input)
            for k in list(cleaned.keys()):
                if k == CONF_GRID_PRICE:
                    continue
                if cleaned[k] == 0.0:
                    cleaned[k] = None
            merged = {**self._entry.data, **cleaned}
            self.hass.config_entries.async_update_entry(self._entry, data=merged)
            return self.async_create_entry(title="", data={})

        current = self._entry.data
        defaults = {k: current.get(k, 0.0) for k in [
            CONF_INIT_SOLAR_WEEK, CONF_INIT_SOLAR_MONTH, CONF_INIT_SOLAR_YEAR,
            CONF_INIT_GRID_WEEK, CONF_INIT_GRID_MONTH, CONF_INIT_GRID_YEAR,
            CONF_INIT_BAT_CHARGE_WEEK, CONF_INIT_BAT_CHARGE_MONTH, CONF_INIT_BAT_CHARGE_YEAR,
            CONF_INIT_BAT_DISCHARGE_WEEK, CONF_INIT_BAT_DISCHARGE_MONTH, CONF_INIT_BAT_DISCHARGE_YEAR,
            CONF_INIT_HOUSE_WEEK, CONF_INIT_HOUSE_MONTH, CONF_INIT_HOUSE_YEAR,
            CONF_INIT_SOLAR_DIRECT_WEEK, CONF_INIT_SOLAR_DIRECT_MONTH, CONF_INIT_SOLAR_DIRECT_YEAR,
            CONF_BATTERY_CAPACITY_KWH, CONF_GRID_PRICE,
        ]}
        return self.async_show_form(step_id="init_values", data_schema=_build_init_schema(defaults))
