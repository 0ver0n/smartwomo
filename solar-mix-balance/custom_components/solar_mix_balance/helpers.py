"""Helpers  V5.7 – Finale ehrliche Domain-Erkennung.

Änderungen vs V2.2:
- #3: Klare, ehrliche Dokumentation der Domain-Erkennung
- #3: config_entry.domain via hass.config_entries.async_get_entry() korrekt genutzt
- Keine überhöhten Versprechen mehr

Ehrliche Einschränkung Domain-Erkennung:
  Für custom integrations gilt: config_entry.domain == entry.platform.
  Das ist korrekt und kein Bug – custom integrations registrieren
  ihre Entitäten unter ihrer eigenen Domain.
  Für Core-Integrationen (z.B. shelly) weichen platform und config_entry.domain ab.
  In beiden Fällen nutzen wir config_entry.domain als primäre Quelle,
  mit platform als Fallback wenn kein Config Entry vorhanden.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er, device_registry as dr

from .const import (
    KW_ZENDURE, KW_ECOFLOW, KW_SOLAR, KW_BAT_CHARGE, KW_BAT_DISCHARGE,
    KW_HOUSE, KW_GRID, KW_PHASE,
    POWER_UNITS, ENERGY_UNITS,
    MAX_SOLAR_POWER_W, MAX_HOUSE_POWER_W, MAX_BATTERY_POWER_W, MAX_GRID_POWER_W,
    CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2, CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
    CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY, CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC,
    CONF_HOUSE_POWER, CONF_HOUSE_ENERGY, CONF_GRID_POWER, CONF_GRID_ENERGY,
    CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityCandidate:
    entity_id: str
    friendly_name: str
    current_value: Optional[str]
    unit: Optional[str]
    score: int
    integration_domain: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    device_name: Optional[str] = None

    def display_label(self) -> str:
        """Lesbare Beschriftung: Friendly Name | entity_id | Wert Einheit.

        Beispiel: 'EcoFlow Solar | sensor.ecoflow_solar_power | 742 W'
        Wird im Config Flow Dropdown als Option-Label angezeigt.
        """
        parts = [self.friendly_name, self.entity_id]
        val = self.current_value
        if val not in (None, STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown", ""):
            unit_str = f" {self.unit}" if self.unit else ""
            parts.append(f"{val}{unit_str}")
        return " | ".join(parts)


# ── State-Hilfsmethoden ───────────────────────────────────────────────────────

def get_numeric_state(hass: HomeAssistant, entity_id: Optional[str]) -> Optional[float]:
    """Liest numerischen Zustand. None bei unavailable/unknown/ungültig."""
    if not entity_id:
        return None
    state: Optional[State] = hass.states.get(entity_id)
    if state is None:
        return None
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, "none", "", "None"):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def get_unit(hass: HomeAssistant, entity_id: Optional[str]) -> Optional[str]:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    return state.attributes.get("unit_of_measurement") if state else None


def normalize_to_watt(hass: HomeAssistant, entity_id: str, raw: float) -> float:
    unit = get_unit(hass, entity_id)
    if unit in ("kW", UnitOfPower.KILO_WATT):
        return raw * 1000.0
    return raw


def normalize_to_kwh(hass: HomeAssistant, entity_id: str, raw: float) -> float:
    unit = get_unit(hass, entity_id)
    if unit in ("Wh", UnitOfEnergy.WATT_HOUR):
        return raw / 1000.0
    if unit in ("MWh", UnitOfEnergy.MEGA_WATT_HOUR):
        return raw * 1000.0
    return raw


def clamp_non_negative(v: Optional[float]) -> Optional[float]:
    return max(0.0, v) if v is not None else None


def safe_add(*values: Optional[float]) -> Optional[float]:
    non_none = [v for v in values if v is not None]
    return sum(non_none) if non_none else None


def safe_subtract(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def round_value(v: Optional[float], decimals: int = 3) -> Optional[float]:
    if v is None:
        return None
    return round(v, decimals)


def validate_power(
    value: Optional[float],
    max_w: float,
    name: str,
    quality_issues: list[str],
) -> Optional[float]:
    if value is None:
        return None
    if value < 0:
        quality_issues.append(f"{name}: negativer Wert {value:.1f} W → 0")
        return 0.0
    if value > max_w:
        quality_issues.append(f"{name}: Ausreißer {value:.1f} W → {max_w:.0f} W")
        _LOGGER.warning("Ausreißer %s: %.1f W begrenzt auf %.0f W", name, value, max_w)
        return max_w
    return value


def calculate_pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0.0:
        return None
    return ((current - previous) / previous) * 100.0


# ── Energieflusslogik ─────────────────────────────────────────────────────────

def calculate_energy_flows(
    solar_kwh: float,
    bat_discharge_kwh: float,
    bat_charge_kwh: float,
    house_kwh: Optional[float],
    grid_kwh: Optional[float],
) -> dict[str, float]:
    """Energiefluss-Bilanzierung.

    Für Setups ohne echten Hausverbrauchszähler wird der Hausverbrauch aus
    Netzbezug + direkt genutzter Solarenergie + Speicherabgabe abgeleitet.
    Das passt für typische Balkon-/Heimspeicher-Setups ohne Einspeisemessung.
    """
    solar = max(0.0, solar_kwh)
    bat_dis = max(0.0, bat_discharge_kwh)
    bat_ch = max(0.0, bat_charge_kwh)
    grid = max(0.0, grid_kwh or 0.0)

    solar_direct_raw = max(0.0, solar - bat_ch)
    bat_to_house_raw = bat_dis

    if house_kwh is None:
        # Ohne echten Hausverbrauchszähler ist die saubere Bilanz:
        # Haus = Netz + Solar-direkt + Speicher-ins-Haus.
        # solar_direct_raw ist hier bereits Solar - Speicherladung.
        house = max(0.0, grid + solar_direct_raw + bat_to_house_raw)
        bat_to_house = min(bat_to_house_raw, house)
        solar_direct = solar_direct_raw
    else:
        house = max(0.0, house_kwh)
        solar_direct = min(solar_direct_raw, house)
        remaining = max(0.0, house - solar_direct)
        bat_to_house = min(bat_to_house_raw, remaining)

    if grid_kwh is not None:
        net = grid
    else:
        net = max(0.0, house - solar_direct - bat_to_house)

    surplus = max(0.0, solar_direct_raw - solar_direct)

    return {
        "solar_direct": solar_direct,
        "bat_to_house": bat_to_house,
        "net": net,
        "solar_surplus": surplus,
        "house_total": house,
        "autark_covered": solar_direct + bat_to_house,
    }


def calculate_autarky(solar_direct: float, bat_to_house: float, house: float) -> float:
    if house <= 0.0:
        return 0.0
    return max(0.0, min(100.0, (solar_direct + bat_to_house) / house * 100.0))


# ── FIX #3: Ehrliche Domain-Erkennung ────────────────────────────────────────

def _get_entity_integration_info(
    hass: HomeAssistant,
    entity_id: str,
    ent_reg: er.EntityRegistry,
    dev_reg: dr.DeviceRegistry,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """FIX #3: Gibt (integration_domain, platform, manufacturer, model, device_name) zurück.

    Methodik:
    1. entity_registry.async_get() → entry.platform (= Integration-Domain für custom)
    2. hass.config_entries.async_get_entry(entry.config_entry_id) → config_entry.domain
       Das ist die offizielle, technisch korrekte Domain.
       Für custom integrations: config_entry.domain == entry.platform (korrekt so)
       Für Core-Integrationen: können abweichen (z.B. shelly)
    3. device_registry → Manufacturer, Model, Name

    Wenn kein Config Entry gefunden: platform als Fallback, offen dokumentiert.
    """
    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return None, None, None, None, None

    platform = entry.platform  # z.B. "zendure_solarflow"

    # Echte Config Entry Domain via offizielle API
    integration_domain: Optional[str] = platform  # Fallback
    domain_source = "platform (fallback)"

    if entry.config_entry_id is not None:
        config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
        if config_entry is not None:
            integration_domain = config_entry.domain
            domain_source = "config_entry.domain"
        else:
            # Config Entry nicht gefunden (z.B. gelöscht aber Entity noch vorhanden)
            _LOGGER.debug(
                "Config Entry %s für %s nicht gefunden – nutze platform '%s'",
                entry.config_entry_id, entity_id, platform
            )
    else:
        # Manuelle Entität ohne Config Entry (z.B. via template oder YAML)
        _LOGGER.debug("Keine Config Entry ID für %s – nutze platform '%s'", entity_id, platform)

    manufacturer: Optional[str] = None
    model: Optional[str] = None
    device_name: Optional[str] = None

    if entry.device_id:
        device = dev_reg.async_get(entry.device_id)
        if device:
            manufacturer = device.manufacturer
            model = device.model
            device_name = device.name_by_user or device.name

    return integration_domain, platform, manufacturer, model, device_name


# ── Entity-Validierung ────────────────────────────────────────────────────────

def validate_entity_id(hass: HomeAssistant, entity_id: Optional[str]) -> tuple[bool, str]:
    """Prüft ob eine entity_id in HA existiert.

    Validierungsregeln:
    - Leer/None = ok (optionales Feld)
    - Format: muss 'domain.name' sein
    - Existenz: muss in hass.states vorhanden sein
    - unavailable/unknown = Warnung, kein Fehler (Gerät könnte temporär offline sein)
    """
    if not entity_id or entity_id in ("none", "", "None"):
        return True, "not_configured"

    if "." not in entity_id:
        return False, f"Ungültiges Format: '{entity_id}' (erwartet: domain.name)"

    parts = entity_id.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False, f"Ungültiges Format: '{entity_id}'"

    state = hass.states.get(entity_id)
    if state is None:
        return False, f"Entität nicht gefunden: '{entity_id}'"

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        _LOGGER.warning(
            "Konfigurierte Entität '%s' ist aktuell %s – wird akzeptiert",
            entity_id, state.state
        )

    return True, "ok"


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_entity(
    entity_id: str,
    friendly_name: str,
    unit: Optional[str],
    device_class: Optional[str],
    state_class: Optional[str],
    integration_domain: Optional[str],
    platform: Optional[str],
    manufacturer: Optional[str],
    model: Optional[str],
    device_name: Optional[str],
    target_kw: list[str],
    exclude_kw: list[str],
    preferred_domains: list[str],
    preferred_manufacturers: list[str],
    want_power: bool,
) -> int:
    """Bewertet eine Entität für einen Verwendungszweck.

    Prioritäten (absteigend):
    1. Integration Domain / Manufacturer (starker Indikator)
    2. Keywords in entity_id, friendly_name, device_name, manufacturer, model
    3. Einheit / Device Class (technische Eignung)
    4. State Class (statistisch geeignet)
    """
    score = 0
    combined = " ".join(filter(None, [
        entity_id.lower(), friendly_name.lower(),
        (device_name or "").lower(), (manufacturer or "").lower(), (model or "").lower()
    ]))

    # Ausschluss-Keywords (sofortiger Ausschluss)
    for kw in exclude_kw:
        if kw.lower() in combined:
            return -9999

    # Keyword-Treffer
    for kw in target_kw:
        kw_l = kw.lower()
        if kw_l in entity_id.lower():
            score += 12
        if kw_l in friendly_name.lower():
            score += 9
        if device_name and kw_l in device_name.lower():
            score += 8
        if manufacturer and kw_l in manufacturer.lower():
            score += 18
        if model and kw_l in model.lower():
            score += 12

    # Integration Domain (primäre Quelle via Config Entry)
    effective_domain = integration_domain or platform or ""
    if effective_domain:
        domain_l = effective_domain.lower()
        for pd in preferred_domains:
            if pd.lower() in domain_l:
                score += 35
                break

    # Hersteller
    if manufacturer:
        for pm in preferred_manufacturers:
            if pm.lower() in manufacturer.lower():
                score += 28
                break

    # Einheit
    unit_str = unit or ""
    if want_power:
        if unit_str in ("W", UnitOfPower.WATT):
            score += 20
        elif unit_str in ("kW", UnitOfPower.KILO_WATT):
            score += 15
        elif unit_str in ("Wh", "kWh", "MWh"):
            score -= 30
    else:
        if unit_str in ("kWh", UnitOfEnergy.KILO_WATT_HOUR):
            score += 20
        elif unit_str in ("Wh", UnitOfEnergy.WATT_HOUR):
            score += 12
        elif unit_str in ("MWh", UnitOfEnergy.MEGA_WATT_HOUR):
            score += 8
        elif unit_str in ("W", "kW"):
            score -= 30

    if want_power and device_class == SensorDeviceClass.POWER:
        score += 25
    if not want_power and device_class == SensorDeviceClass.ENERGY:
        score += 25

    if want_power and state_class == SensorStateClass.MEASUREMENT:
        score += 8
    if not want_power and state_class in (SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING):
        score += 12

    return score


def discover_entities(hass: HomeAssistant) -> dict[str, list[EntityCandidate]]:
    """FIX #3: Entitätserkennung mit ehrlicher Domain-Ermittlung."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    all_states = hass.states.async_all("sensor")

    result: dict[str, list[EntityCandidate]] = {k: [] for k in [
        CONF_ZENDURE_SOLAR, CONF_ZENDURE_SOLAR_ENERGY,
        CONF_ECOFLOW_SOLAR, CONF_ECOFLOW_SOLAR_2,
        CONF_ECOFLOW_SOLAR_ENERGY, CONF_ECOFLOW_SOLAR_2_ENERGY,
        CONF_BATTERY_CHARGE, CONF_BATTERY_CHARGE_ENERGY,
        CONF_BATTERY_DISCHARGE, CONF_BATTERY_DISCHARGE_ENERGY, CONF_BATTERY_SOC,
        CONF_HOUSE_POWER, CONF_HOUSE_ENERGY,
        CONF_GRID_POWER, CONF_GRID_ENERGY,
        CONF_PHASE1_POWER, CONF_PHASE2_POWER, CONF_PHASE3_POWER,
    ]}

    # Bekannte Domain-Namen für Zendure und EcoFlow
    # Quellen: HACS-Integrations-Repositories (Stand 2024)
    ZENDURE_DOMAINS = [
        "zendure", "zendure_solarflow", "solarflow",
        "ha_zendure_solarflow", "zendure_ha",
    ]
    ECOFLOW_DOMAINS = [
        "ecoflow", "ecoflow_cloud", "powerocean", "ecoflow_ble",
    ]
    ZENDURE_MFR = ["Zendure", "SolarFlow", "zendure"]
    ECOFLOW_MFR = ["EcoFlow", "ECOFLOW", "PowerOcean", "ecoflow"]

    for state in all_states:
        eid = state.entity_id
        fn = state.attributes.get("friendly_name", eid)
        unit = state.attributes.get("unit_of_measurement")
        dc = state.attributes.get("device_class")
        sc = state.attributes.get("state_class")
        cur = state.state if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else None

        # FIX #3: hass-Referenz für echten Config Entry Domain Lookup
        integ_domain, platform, mfr, mdl, dev_name = _get_entity_integration_info(
            hass, eid, ent_reg, dev_reg
        )

        def _add(conf_key: str, target_kw: list[str], excl_kw: list[str],
                 pref_dom: list[str], pref_mfr: list[str], want_power: bool) -> None:
            s = _score_entity(
                entity_id=eid, friendly_name=fn, unit=unit, device_class=dc,
                state_class=sc, integration_domain=integ_domain, platform=platform,
                manufacturer=mfr, model=mdl, device_name=dev_name,
                target_kw=target_kw, exclude_kw=excl_kw,
                preferred_domains=pref_dom, preferred_manufacturers=pref_mfr,
                want_power=want_power,
            )
            if s > 0:
                result[conf_key].append(EntityCandidate(
                    entity_id=eid, friendly_name=fn, current_value=cur,
                    unit=unit, score=s, integration_domain=integ_domain,
                    manufacturer=mfr, model=mdl, device_name=dev_name,
                ))

        NO: list[str] = []

        _add(CONF_ZENDURE_SOLAR, KW_ZENDURE + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ZENDURE_DOMAINS, ZENDURE_MFR, True)

        _add(CONF_ECOFLOW_SOLAR, KW_ECOFLOW + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ECOFLOW_DOMAINS, ECOFLOW_MFR, True)
        _add(CONF_ECOFLOW_SOLAR_2, KW_ECOFLOW + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ECOFLOW_DOMAINS, ECOFLOW_MFR, True)
        _add(CONF_ZENDURE_SOLAR_ENERGY, KW_ZENDURE + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ZENDURE_DOMAINS, ZENDURE_MFR, False)
        _add(CONF_ECOFLOW_SOLAR_ENERGY, KW_ECOFLOW + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ECOFLOW_DOMAINS, ECOFLOW_MFR, False)
        _add(CONF_ECOFLOW_SOLAR_2_ENERGY, KW_ECOFLOW + KW_SOLAR,
             KW_BAT_CHARGE + KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID,
             ECOFLOW_DOMAINS, ECOFLOW_MFR, False)

        _add(CONF_BATTERY_CHARGE, KW_BAT_CHARGE,
             KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID + KW_SOLAR,
             ZENDURE_DOMAINS + ECOFLOW_DOMAINS, ZENDURE_MFR + ECOFLOW_MFR, True)
        _add(CONF_BATTERY_CHARGE_ENERGY, KW_BAT_CHARGE,
             KW_BAT_DISCHARGE + KW_HOUSE + KW_GRID + KW_SOLAR,
             ZENDURE_DOMAINS + ECOFLOW_DOMAINS, ZENDURE_MFR + ECOFLOW_MFR, False)

        _add(CONF_BATTERY_DISCHARGE, KW_BAT_DISCHARGE,
             KW_BAT_CHARGE + KW_HOUSE + KW_GRID + KW_SOLAR,
             ZENDURE_DOMAINS + ECOFLOW_DOMAINS, ZENDURE_MFR + ECOFLOW_MFR, True)
        _add(CONF_BATTERY_DISCHARGE_ENERGY, KW_BAT_DISCHARGE,
             KW_BAT_CHARGE + KW_HOUSE + KW_GRID + KW_SOLAR,
             ZENDURE_DOMAINS + ECOFLOW_DOMAINS, ZENDURE_MFR + ECOFLOW_MFR, False)

        _add(CONF_BATTERY_SOC, ["soc", "state_of_charge", "ladezustand", "battery", "batterie", "percentage", "prozent"],
             KW_SOLAR + KW_GRID + KW_HOUSE + ["power", "leistung", "energy", "energie", "kwh", "w"],
             ZENDURE_DOMAINS + ECOFLOW_DOMAINS, ZENDURE_MFR + ECOFLOW_MFR, True)

        _add(CONF_HOUSE_POWER, KW_HOUSE,
             KW_ZENDURE + KW_ECOFLOW + KW_GRID + KW_PHASE, NO, NO, True)
        _add(CONF_HOUSE_ENERGY, KW_HOUSE,
             KW_ZENDURE + KW_ECOFLOW + KW_GRID + KW_PHASE, NO, NO, False)
        _add(CONF_GRID_POWER, KW_GRID,
             KW_HOUSE + KW_SOLAR + KW_BAT_CHARGE + KW_BAT_DISCHARGE, NO, NO, True)
        _add(CONF_GRID_ENERGY, KW_GRID,
             KW_HOUSE + KW_SOLAR + KW_BAT_CHARGE + KW_BAT_DISCHARGE, NO, NO, False)

        p1 = ["phase_1", "l1_", "_l1", "p1_", "_p1", "phase1", "channel_1", "ch1"]
        p2 = ["phase_2", "l2_", "_l2", "p2_", "_p2", "phase2", "channel_2", "ch2"]
        p3 = ["phase_3", "l3_", "_l3", "p3_", "_p3", "phase3", "channel_3", "ch3"]

        _add(CONF_PHASE1_POWER, p1 + KW_GRID, p2 + p3, NO, NO, True)
        _add(CONF_PHASE2_POWER, p2 + KW_GRID, p1 + p3, NO, NO, True)
        _add(CONF_PHASE3_POWER, p3 + KW_GRID, p1 + p2, NO, NO, True)

    for k in result:
        result[k].sort(key=lambda c: c.score, reverse=True)

    return result


def build_labeled_options(candidates: list[EntityCandidate], limit: int = 20) -> list[tuple[str, str]]:
    """Gibt (entity_id, display_label) für Config Flow Dropdowns zurück."""
    return [(c.entity_id, c.display_label()) for c in candidates[:limit]]
