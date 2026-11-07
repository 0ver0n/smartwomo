"""Entity Descriptions V5.7 – HA-kompatible State Classes.

Regeln:
- Aktuelle Periodenwerte (heute/Woche/Monat/Jahr) sind kWh-Summen, die bei
  Periodenwechseln zurückgesetzt werden können: device_class=energy,
  state_class=total.
- Historische Snapshots (gestern/letzte Woche/letzter Monat/letztes Jahr)
  sind ebenfalls kWh-Summen: device_class=energy, state_class=total.
- Differenzen können negativ sein: keine energy-device_class, aber
  state_class=measurement und Einheit kWh.
- Prozentwerte und Kosten/Ersparnis: state_class=measurement.

Entity-IDs bleiben stabil (kein Rename).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntityDescription, SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, PERCENTAGE

from .const import (
    SENSOR_GROUP_BASIC, SENSOR_GROUP_COMPARE,
    SENSOR_GROUP_DIAGNOSTICS, SENSOR_GROUP_EXPERT,
)


@dataclass(frozen=True)
class SolarSensorDesc(SensorEntityDescription):
    """Erweiterte Beschreibung mit data_key und Gruppe."""
    data_key: str = ""
    group: str = SENSOR_GROUP_BASIC
    energy_dashboard: bool = False


# ── Live-Sensoren ─────────────────────────────────────────────────────────────
# Leistungssensoren: device_class=POWER, state_class=MEASUREMENT
LIVE_SENSORS: list[SolarSensorDesc] = [
    SolarSensorDesc(
        key="solar_power_zendure", data_key="solar_power_zendure",
        name="Solarleistung Zendure",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="solar_power_ecoflow", data_key="solar_power_ecoflow",
        name="Solarleistung EcoFlow",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power-variant", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="solar_power_total", data_key="solar_power_total",
        name="Solarleistung Gesamt",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-panel-large", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="battery_charge_power", data_key="battery_charge_power",
        name="Speicherladung aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="battery_discharge_power", data_key="battery_discharge_power",
        name="Speicherabgabe DC aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-down", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="zendure_home_output_power", data_key="zendure_home_output_power",
        name="SolarFlow AC ans Haus aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-lightning-bolt", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="grid_charge_power", data_key="grid_charge_power",
        name="Netzladung Speicher aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-import", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="house_power", data_key="house_power",
        name="Hausverbrauch aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-lightning-bolt", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="grid_power", data_key="grid_power",
        name="Netzbezug aktuell",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="current_grid_price", data_key="current_grid_price",
        name="Aktueller Strompreis",
        native_unit_of_measurement="€/kWh",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cash-clock", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="battery_soc", data_key="battery_soc",
        name="Speicher Ladezustand",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery", group=SENSOR_GROUP_BASIC,
    ),
    SolarSensorDesc(
        key="battery_remaining_kwh", data_key="battery_remaining_kwh",
        name="Speicherinhalt berechnet",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-medium", group=SENSOR_GROUP_EXPERT,
    ),
    SolarSensorDesc(
        key="battery_free_kwh", data_key="battery_free_kwh",
        name="Freie Speicherkapazität",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-outline", group=SENSOR_GROUP_EXPERT,
    ),
]


def _period_sensors(period: str, label: str, group: str) -> list[SolarSensorDesc]:
    """Periodenwerte für aktuelle Tag/Woche/Monat/Jahr.

    V5.7: Energie-Periodensensoren nutzen state_class=TOTAL statt
    TOTAL_INCREASING. Die Werte sind Summen innerhalb einer Periode und
    können bei Tages-, Wochen- oder Monatswechsel auf 0 zurückspringen.
    TOTAL bleibt HA-kompatibel für device_class=energy und vermeidet
    monotonicity-Reparaturmeldungen bei periodischen Resets.
    """
    kwh = UnitOfEnergy.KILO_WATT_HOUR
    pct = PERCENTAGE
    p = period
    lbl = label
    g = group
    ti = SensorStateClass.TOTAL
    m = SensorStateClass.MEASUREMENT
    de = SensorDeviceClass.ENERGY
    return [
        SolarSensorDesc(key=f"solar_energy_{p}", data_key=f"solar_energy_{p}", name=f"Solarenergie {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:solar-panel", group=g, energy_dashboard=True),
        SolarSensorDesc(key=f"battery_charge_{p}", data_key=f"battery_charge_{p}", name=f"Speicherladung {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:battery-charging-outline", group=g, energy_dashboard=True),
        SolarSensorDesc(key=f"battery_discharge_{p}", data_key=f"battery_discharge_{p}", name=f"Speicherabgabe ans Haus {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:battery-minus", group=g, energy_dashboard=True),
        SolarSensorDesc(key=f"house_energy_{p}", data_key=f"house_energy_{p}", name=f"Hausverbrauch {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:home-import-outline", group=g, energy_dashboard=True),
        SolarSensorDesc(key=f"grid_energy_{p}", data_key=f"grid_energy_{p}", name=f"Netzbezug {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:transmission-tower-import", group=g, energy_dashboard=True),
        SolarSensorDesc(key=f"home_output_{p}", data_key=f"home_output_{p}", name=f"SolarFlow AC ans Haus {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:home-lightning-bolt", group=g),
        SolarSensorDesc(key=f"grid_charge_{p}", data_key=f"grid_charge_{p}", name=f"Netzladung Speicher {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:transmission-tower-import", group=g),
        SolarSensorDesc(key=f"grid_to_battery_{p}", data_key=f"grid_to_battery_{p}", name=f"Netz in Speicher {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:battery-arrow-up", group=g),
        SolarSensorDesc(key=f"solar_to_battery_{p}", data_key=f"solar_to_battery_{p}", name=f"Solar in Speicher {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:battery-charging", group=g),
        SolarSensorDesc(key=f"grid_to_home_{p}", data_key=f"grid_to_home_{p}", name=f"Netz durch SolarFlow ans Haus {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:transmission-tower", group=g),
        SolarSensorDesc(key=f"solar_direct_{p}", data_key=f"solar_direct_{p}", name=f"Direkte Solarenergie AC im Haus {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:solar-panel-large", group=g),
        SolarSensorDesc(key=f"battery_share_{p}", data_key=f"battery_share_{p}", name=f"Hausverbrauch aus Speicher {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:battery-heart", group=g),
        SolarSensorDesc(key=f"solar_share_{p}", data_key=f"solar_share_{p}", name=f"Anteil Solar am Verbrauch {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:solar-panel", group=g),
        SolarSensorDesc(key=f"grid_cost_{p}", data_key=f"grid_cost_{p}", name=f"Netzkosten {lbl}", native_unit_of_measurement="€", device_class=None, state_class=SensorStateClass.MEASUREMENT, icon="mdi:cash", group=g),
        SolarSensorDesc(key=f"solar_savings_{p}", data_key=f"solar_savings_{p}", name=f"Ersparnis durch Solar {lbl}", native_unit_of_measurement="€", device_class=None, state_class=SensorStateClass.MEASUREMENT, icon="mdi:piggy-bank", group=g),
        # V4 FIX #8: Autarkiegrad ist kein Energiewert → kein device_class=ENERGY, state_class=MEASUREMENT
        SolarSensorDesc(key=f"autarky_{p}", data_key=f"autarky_{p}", name=f"Autarkiegrad {lbl}", native_unit_of_measurement=pct, device_class=None, state_class=m, icon="mdi:home-circle", group=g),
        SolarSensorDesc(key=f"self_consumption_ratio_{p}", data_key=f"self_consumption_ratio_{p}", name=f"Eigenverbrauchsquote {lbl}", native_unit_of_measurement=pct, device_class=None, state_class=m, icon="mdi:chart-donut", group=g),
        SolarSensorDesc(key=f"grid_charge_conversion_loss_{p}", data_key=f"grid_charge_conversion_loss_{p}", name=f"Verlust Netzladung {lbl}", native_unit_of_measurement=kwh, device_class=de, state_class=ti, icon="mdi:flash-alert", group=SENSOR_GROUP_EXPERT),
    ]


TODAY_SENSORS = _period_sensors("today", "heute", SENSOR_GROUP_BASIC)
WEEK_SENSORS = _period_sensors("week", "diese Woche", SENSOR_GROUP_BASIC)
MONTH_SENSORS = _period_sensors("month", "diesen Monat", SENSOR_GROUP_BASIC)
YEAR_SENSORS = _period_sensors("year", "dieses Jahr", SENSOR_GROUP_BASIC)


def _compare_sensors(suffix: str, label: str) -> list[SolarSensorDesc]:
    """Vergleichssensoren mit HA-kompatibler State-Class.

    Wichtig für Home Assistant 2026.x:
    - Energie-Snapshotwerte wie "gestern"/"letzte Woche" dürfen bei
      device_class=energy NICHT state_class=measurement verwenden.
      Korrekt ist hier state_class=total.
    - Energiedifferenzen können negativ sein. Damit HA keine Energy-Statistik-
      Warnungen wirft, bekommen sie KEINE device_class=energy, aber weiterhin
      Einheit kWh und state_class=measurement.
    - Prozentwerte und Prozentdifferenzen sind measurement.

    Dadurch verschwinden sowohl die alten Warnungen "energy + measurement ist
    ungültig" als auch die Reparaturmeldung "verfügt nicht mehr über eine
    Zustandsklasse", die durch das komplette Entfernen der state_class entstand.
    """
    su = suffix
    lb = label
    short = su.replace("last_", "") if su.startswith("last_") else su
    kwh = UnitOfEnergy.KILO_WATT_HOUR
    pct = PERCENTAGE
    g = SENSOR_GROUP_COMPARE
    de = SensorDeviceClass.ENERGY
    total = SensorStateClass.TOTAL
    measurement = SensorStateClass.MEASUREMENT

    def _snapshot_energy(key: str, dkey: str, name: str, icon: str) -> SolarSensorDesc:
        return SolarSensorDesc(
            key=key, data_key=dkey, name=name,
            native_unit_of_measurement=kwh, device_class=de,
            state_class=total, icon=icon, group=g,
        )

    def _diff_energy(key: str, dkey: str, name: str, icon: str) -> SolarSensorDesc:
        return SolarSensorDesc(
            key=key, data_key=dkey, name=name,
            native_unit_of_measurement=kwh, device_class=None,
            state_class=measurement, icon=icon, group=g,
        )

    def _percent(key: str, dkey: str, name: str, icon: str) -> SolarSensorDesc:
        return SolarSensorDesc(
            key=key, data_key=dkey, name=name,
            native_unit_of_measurement=pct, device_class=None,
            state_class=measurement, icon=icon, group=g,
        )

    return [
        # Solar
        _snapshot_energy(f"solar_energy_{su}",          f"solar_energy_{su}",          f"Solarenergie {lb}",                     "mdi:solar-panel"),
        _diff_energy(    f"solar_energy_diff_{short}",  f"solar_energy_diff_{short}",  f"Solarenergie Differenz zu {lb}",        "mdi:solar-panel"),
        _percent(        f"solar_energy_pct_{short}",   f"solar_energy_pct_{short}",   f"Solarenergie Veränderung zu {lb}",      "mdi:trending-up"),
        # Grid
        _snapshot_energy(f"grid_energy_{su}",           f"grid_energy_{su}",           f"Netzbezug {lb}",                         "mdi:transmission-tower-import"),
        _diff_energy(    f"grid_energy_diff_{short}",   f"grid_energy_diff_{short}",   f"Netzbezug Differenz zu {lb}",            "mdi:transmission-tower-import"),
        _percent(        f"grid_energy_pct_{short}",    f"grid_energy_pct_{short}",    f"Netzbezug Veränderung zu {lb}",          "mdi:trending-up"),
        # House
        _snapshot_energy(f"house_energy_{su}",          f"house_energy_{su}",          f"Hausverbrauch {lb}",                     "mdi:home-import-outline"),
        _diff_energy(    f"house_energy_diff_{short}",  f"house_energy_diff_{short}",  f"Hausverbrauch Differenz zu {lb}",        "mdi:home-import-outline"),
        _percent(        f"house_energy_pct_{short}",   f"house_energy_pct_{short}",   f"Hausverbrauch Veränderung zu {lb}",      "mdi:trending-up"),
        # Battery charge
        _snapshot_energy(f"battery_charge_{su}",         f"battery_charge_{su}",        f"Speicherladung {lb}",                    "mdi:battery-charging-outline"),
        _diff_energy(    f"battery_charge_diff_{short}", f"battery_charge_diff_{short}",f"Speicherladung Differenz zu {lb}",       "mdi:battery-charging-outline"),
        _percent(        f"battery_charge_pct_{short}",  f"battery_charge_pct_{short}", f"Speicherladung Veränderung zu {lb}",     "mdi:trending-up"),
        # Battery discharge
        _snapshot_energy(f"battery_discharge_{su}",          f"battery_discharge_{su}",          f"Speicherabgabe {lb}",              "mdi:battery-minus"),
        _diff_energy(    f"battery_discharge_diff_{short}",  f"battery_discharge_diff_{short}",  f"Speicherabgabe Differenz zu {lb}", "mdi:battery-minus"),
        _percent(        f"battery_discharge_pct_{short}",   f"battery_discharge_pct_{short}",   f"Speicherabgabe Veränderung zu {lb}", "mdi:trending-up"),
        # Solar direct
        _snapshot_energy(f"solar_direct_{su}",          f"solar_direct_{su}",          f"Direkte Solarenergie {lb}",              "mdi:solar-panel-large"),
        _diff_energy(    f"solar_direct_diff_{short}",  f"solar_direct_diff_{short}",  f"Direkte Solarenergie Differenz zu {lb}", "mdi:solar-panel-large"),
        _percent(        f"solar_direct_pct_{short}",   f"solar_direct_pct_{short}",   f"Direkte Solarenergie Veränderung zu {lb}", "mdi:trending-up"),
        # Autarky
        _percent(        f"autarky_{su}",               f"autarky_{su}",               f"Autarkiegrad {lb}",                      "mdi:home-circle"),
        _percent(        f"autarky_diff_{short}",       f"autarky_diff_{short}",       f"Autarkiegrad Veränderung zu {lb}",       "mdi:trending-up"),
    ]

COMPARE_YESTERDAY  = _compare_sensors("yesterday",  "gestern")
COMPARE_LAST_WEEK  = _compare_sensors("last_week",  "letzter Woche")
COMPARE_LAST_MONTH = _compare_sensors("last_month", "letztem Monat")
COMPARE_LAST_YEAR  = _compare_sensors("last_year",  "letztem Jahr")


def _audit_sensors(period: str, label: str) -> list[SolarSensorDesc]:
    """Bilanz-Prüfsensoren für langfristige Kontrolle.

    Diese Werte ändern keine Berechnung, sondern zeigen nur, ob die intern
    verwendeten Gleichungen aufgehen:
    - Hausbilanzfehler = Hausverbrauch - (Netz + Solar direkt + Speicher ins Haus)
    - Solarbilanz-Rest = Solar erzeugt - (Solar direkt + Speicherladung)
    - Speichersaldo = Speicherladung - Speicherabgabe ans Haus

    Nahe 0 bei Haus-/Solarbilanz bedeutet: Die Energieströme sind in sich
    konsistent. Ein positiver Speichersaldo ist normal, wenn der Akku im
    Zeitraum netto geladen wurde oder Verluste/SOC-Änderungen auftreten.
    """
    kwh = UnitOfEnergy.KILO_WATT_HOUR
    m = SensorStateClass.MEASUREMENT
    g = SENSOR_GROUP_BASIC
    return [
        SolarSensorDesc(
            key=f"audit_house_balance_error_{period}",
            data_key=f"audit_house_balance_error_{period}",
            name=f"Hausbilanzfehler {label}",
            native_unit_of_measurement=kwh,
            device_class=None,
            state_class=m,
            icon="mdi:scale-balance",
            group=g,
        ),
        SolarSensorDesc(
            key=f"audit_solar_balance_rest_{period}",
            data_key=f"audit_solar_balance_rest_{period}",
            name=f"Solar-/Umwandlungsverlust {label}",
            native_unit_of_measurement=kwh,
            device_class=None,
            state_class=m,
            icon="mdi:solar-panel",
            group=g,
        ),
        SolarSensorDesc(
            key=f"audit_battery_delta_{period}",
            data_key=f"audit_battery_delta_{period}",
            name=f"Speicher-/Wechselrichterverlust {label}",
            native_unit_of_measurement=kwh,
            device_class=None,
            state_class=m,
            icon="mdi:battery-sync",
            group=g,
        ),
    ]


AUDIT_SENSORS: list[SolarSensorDesc] = (
    _audit_sensors("today", "heute")
    + _audit_sensors("week", "diese Woche")
    + _audit_sensors("month", "diesen Monat")
    + _audit_sensors("year", "dieses Jahr")
)


DIAG_SENSORS: list[SolarSensorDesc] = [
    SolarSensorDesc(
        key="diagnostics_sensor", data_key="diagnostics",
        name="Solar Mix Balance Diagnose",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        icon="mdi:information-outline",
        group=SENSOR_GROUP_DIAGNOSTICS,
        entity_registry_enabled_default=False,
    ),
]

ALL_SENSORS: list[SolarSensorDesc] = (
    LIVE_SENSORS
    + TODAY_SENSORS + WEEK_SENSORS + MONTH_SENSORS + YEAR_SENSORS
    + COMPARE_YESTERDAY + COMPARE_LAST_WEEK + COMPARE_LAST_MONTH + COMPARE_LAST_YEAR
    + AUDIT_SENSORS
    + DIAG_SENSORS
)
