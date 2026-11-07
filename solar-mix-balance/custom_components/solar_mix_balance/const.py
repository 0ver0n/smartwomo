"""Konstanten für Solar Mix Balance V5.7."""
from __future__ import annotations

DOMAIN = "solar_mix_balance"
VERSION = "5.8.2"
COORDINATOR = "coordinator"
PLATFORMS = ["sensor"]

# ── Datenpfade ────────────────────────────────────────────────────────────────
DATA_ROOT = "solar_mix_balance_data"
DATA_DIR_TAG = "tag"
DATA_DIR_WOCHE = "woche"
DATA_DIR_MONAT = "monat"
DATA_DIR_JAHR = "jahr"
DATA_DIR_BACKUP = "backup"

CSV_DAILY = "daily_values.csv"
CSV_WEEKLY = "weekly_values.csv"
CSV_MONTHLY = "monthly_values.csv"
CSV_YEARLY = "yearly_values.csv"
BACKUP_FILENAME = "solar_mix_balance_backup.json"

# ── Konfigurationsschlüssel – Quellentitäten ─────────────────────────────────
CONF_ZENDURE_SOLAR = "zendure_solar_entity"
CONF_ZENDURE_SOLAR_ENERGY = "zendure_solar_energy_entity"
CONF_ECOFLOW_SOLAR = "ecoflow_solar_entity"
CONF_ECOFLOW_SOLAR_2 = "ecoflow_solar_2_entity"
CONF_ECOFLOW_SOLAR_ENERGY = "ecoflow_solar_energy_entity"
CONF_ECOFLOW_SOLAR_2_ENERGY = "ecoflow_solar_2_energy_entity"
CONF_BATTERY_CHARGE = "battery_charge_entity"
CONF_BATTERY_CHARGE_ENERGY = "battery_charge_energy_entity"
CONF_BATTERY_DISCHARGE = "battery_discharge_entity"
CONF_BATTERY_DISCHARGE_ENERGY = "battery_discharge_energy_entity"
CONF_BATTERY_SOC = "battery_soc_entity"
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"
DEFAULT_BATTERY_CAPACITY_KWH = 1.92
CONF_HOUSE_POWER = "house_power_entity"
CONF_HOUSE_ENERGY = "house_energy_entity"
CONF_GRID_POWER = "grid_power_entity"
CONF_GRID_ENERGY = "grid_energy_entity"
CONF_PHASE1_POWER = "phase1_power_entity"
CONF_PHASE2_POWER = "phase2_power_entity"
CONF_PHASE3_POWER = "phase3_power_entity"
CONF_GRID_PRICE = "grid_price_per_kwh"
CONF_MONTHLY_PRICES = "monthly_prices"  # Mapping YYYY-MM -> €/kWh
CONF_MONTHLY_GRID_KWH = "monthly_grid_kwh"  # Mapping YYYY-MM -> belegter Netzbezug in kWh
DEFAULT_GRID_PRICE = 0.30

# ── Konfigurationsschlüssel – Sensorgruppen ───────────────────────────────────
CONF_SENSOR_GROUPS = "sensor_groups"
SENSOR_GROUP_BASIC = "basic"
SENSOR_GROUP_COMPARE = "compare"
SENSOR_GROUP_DIAGNOSTICS = "diagnostics"
SENSOR_GROUP_EXPERT = "expert"
ALL_SENSOR_GROUPS = [
    SENSOR_GROUP_BASIC,
    SENSOR_GROUP_COMPARE,
    SENSOR_GROUP_DIAGNOSTICS,
    SENSOR_GROUP_EXPERT,
]

# ── Optionale Startwerte ──────────────────────────────────────────────────────
CONF_INIT_SOLAR_WEEK = "init_solar_week"
CONF_INIT_SOLAR_MONTH = "init_solar_month"
CONF_INIT_SOLAR_YEAR = "init_solar_year"
CONF_INIT_GRID_WEEK = "init_grid_week"
CONF_INIT_GRID_MONTH = "init_grid_month"
CONF_INIT_GRID_YEAR = "init_grid_year"
CONF_INIT_BAT_CHARGE_WEEK = "init_bat_charge_week"
CONF_INIT_BAT_CHARGE_MONTH = "init_bat_charge_month"
CONF_INIT_BAT_CHARGE_YEAR = "init_bat_charge_year"
CONF_INIT_BAT_DISCHARGE_WEEK = "init_bat_discharge_week"
CONF_INIT_BAT_DISCHARGE_MONTH = "init_bat_discharge_month"
CONF_INIT_BAT_DISCHARGE_YEAR = "init_bat_discharge_year"
CONF_INIT_HOUSE_WEEK = "init_house_week"
CONF_INIT_HOUSE_MONTH = "init_house_month"
CONF_INIT_HOUSE_YEAR = "init_house_year"
CONF_INIT_SOLAR_DIRECT_WEEK = "init_solar_direct_week"
CONF_INIT_SOLAR_DIRECT_MONTH = "init_solar_direct_month"
CONF_INIT_SOLAR_DIRECT_YEAR = "init_solar_direct_year"

ALL_INIT_KEYS = [
    CONF_INIT_SOLAR_WEEK, CONF_INIT_SOLAR_MONTH, CONF_INIT_SOLAR_YEAR,
    CONF_INIT_GRID_WEEK, CONF_INIT_GRID_MONTH, CONF_INIT_GRID_YEAR,
    CONF_INIT_BAT_CHARGE_WEEK, CONF_INIT_BAT_CHARGE_MONTH, CONF_INIT_BAT_CHARGE_YEAR,
    CONF_INIT_BAT_DISCHARGE_WEEK, CONF_INIT_BAT_DISCHARGE_MONTH, CONF_INIT_BAT_DISCHARGE_YEAR,
    CONF_INIT_HOUSE_WEEK, CONF_INIT_HOUSE_MONTH, CONF_INIT_HOUSE_YEAR,
    CONF_INIT_SOLAR_DIRECT_WEEK, CONF_INIT_SOLAR_DIRECT_MONTH, CONF_INIT_SOLAR_DIRECT_YEAR,
]

# ── Timing ────────────────────────────────────────────────────────────────────
DEBOUNCE_SECONDS = 1.0          # Sammelzeitfenster für state-changes
SAFETY_REFRESH_MINUTES = 5      # Sicherheits-Refresh-Intervall
MAX_ACCUMULATION_GAP_SECONDS = 300  # Lücken > 5 min: keine Akkumulation

# ── Plausibilitätsgrenzen (Watt) ──────────────────────────────────────────────
MAX_SOLAR_POWER_W = 30_000
MAX_HOUSE_POWER_W = 50_000
MAX_BATTERY_POWER_W = 2_000
MAX_GRID_POWER_W = 50_000

# ── Einheiten ─────────────────────────────────────────────────────────────────
POWER_UNITS = {"W", "kW"}
ENERGY_UNITS = {"Wh", "kWh", "MWh"}

# ── Heuristik-Keywords ────────────────────────────────────────────────────────
KW_ZENDURE = ["zendure", "solarflow", "hyper2000", "hub1200", "hub2000", "aio2400"]
KW_ECOFLOW = ["ecoflow", "delta", "river", "powerocean", "power_ocean"]
KW_SOLAR = ["solar", "pv", "photovoltaic", "generation", "produced", "production", "inverter", "ertrag", "erzeug", "aggr_solar_total", "solar_total"]
KW_BAT_CHARGE = ["charge", "charging", "laden", "battery_in", "bat_in", "speicher_laden", "eingehend", "aggr_charge_total", "charge_total", "akku_geladen"]
KW_BAT_DISCHARGE = ["discharge", "discharging", "entladen", "battery_out", "bat_out", "speicher_abgabe", "output", "ausgehend", "aggr_discharge_total", "discharge_total", "akku_entladen"]
KW_HOUSE = ["house", "home", "load", "verbrauch", "hausverbrauch", "consumption", "haushalt"]
KW_GRID = ["grid", "meter", "import", "netz", "netzbezug", "stromzähler", "zaehler", "strom"]
KW_PHASE = ["phase", "l1", "l2", "l3", "p1", "p2", "p3", "phase_1", "phase_2", "phase_3"]

# ── Sensor-Schlüssel ──────────────────────────────────────────────────────────
# Live
SK_SOLAR_Z = "solar_power_zendure"
SK_SOLAR_E = "solar_power_ecoflow"
SK_SOLAR_TOTAL = "solar_power_total"
SK_BAT_CHARGE = "battery_charge_power"
SK_BAT_DISCHARGE = "battery_discharge_power"
SK_HOUSE_POWER = "house_power"
SK_GRID_POWER = "grid_power"

# Tageswerte
SK_SOLAR_TODAY = "solar_energy_today"
SK_BAT_CH_TODAY = "battery_charge_today"
SK_BAT_DIS_TODAY = "battery_discharge_today"
SK_HOUSE_TODAY = "house_energy_today"
SK_GRID_TODAY = "grid_energy_today"
SK_SOL_DIRECT_TODAY = "solar_direct_today"
SK_BAT_SHARE_TODAY = "battery_share_today"
SK_SOL_SHARE_TODAY = "solar_share_today"
SK_AUTARKY_TODAY = "autarky_today"

# Wochenwerte
SK_SOLAR_WEEK = "solar_energy_week"
SK_BAT_CH_WEEK = "battery_charge_week"
SK_BAT_DIS_WEEK = "battery_discharge_week"
SK_HOUSE_WEEK = "house_energy_week"
SK_GRID_WEEK = "grid_energy_week"
SK_SOL_DIRECT_WEEK = "solar_direct_week"
SK_BAT_SHARE_WEEK = "battery_share_week"
SK_SOL_SHARE_WEEK = "solar_share_week"
SK_AUTARKY_WEEK = "autarky_week"

# Monatswerte
SK_SOLAR_MONTH = "solar_energy_month"
SK_BAT_CH_MONTH = "battery_charge_month"
SK_BAT_DIS_MONTH = "battery_discharge_month"
SK_HOUSE_MONTH = "house_energy_month"
SK_GRID_MONTH = "grid_energy_month"
SK_SOL_DIRECT_MONTH = "solar_direct_month"
SK_BAT_SHARE_MONTH = "battery_share_month"
SK_SOL_SHARE_MONTH = "solar_share_month"
SK_AUTARKY_MONTH = "autarky_month"

# Jahreswerte
SK_SOLAR_YEAR = "solar_energy_year"
SK_BAT_CH_YEAR = "battery_charge_year"
SK_BAT_DIS_YEAR = "battery_discharge_year"
SK_HOUSE_YEAR = "house_energy_year"
SK_GRID_YEAR = "grid_energy_year"
SK_SOL_DIRECT_YEAR = "solar_direct_year"
SK_BAT_SHARE_YEAR = "battery_share_year"
SK_SOL_SHARE_YEAR = "solar_share_year"
SK_AUTARKY_YEAR = "autarky_year"

# Vergleich – Gestern
SK_SOLAR_YEST = "solar_energy_yesterday"
SK_SOLAR_DIFF_YEST = "solar_energy_diff_yesterday"
SK_SOLAR_PCT_YEST = "solar_energy_pct_yesterday"
SK_GRID_YEST = "grid_energy_yesterday"
SK_GRID_DIFF_YEST = "grid_energy_diff_yesterday"
SK_GRID_PCT_YEST = "grid_energy_pct_yesterday"
SK_HOUSE_YEST = "house_energy_yesterday"
SK_HOUSE_DIFF_YEST = "house_energy_diff_yesterday"
SK_BAT_CH_YEST = "battery_charge_yesterday"
SK_BAT_CH_DIFF_YEST = "battery_charge_diff_yesterday"
SK_BAT_DIS_YEST = "battery_discharge_yesterday"
SK_BAT_DIS_DIFF_YEST = "battery_discharge_diff_yesterday"
SK_SOL_DIRECT_YEST = "solar_direct_yesterday"
SK_SOL_DIRECT_DIFF_YEST = "solar_direct_diff_yesterday"
SK_AUTARKY_YEST = "autarky_yesterday"
SK_AUTARKY_DIFF_YEST = "autarky_diff_yesterday"

# Vergleich – Letzte Woche
SK_SOLAR_LWEK = "solar_energy_last_week"
SK_SOLAR_DIFF_LWEK = "solar_energy_diff_week"
SK_SOLAR_PCT_LWEK = "solar_energy_pct_week"
SK_GRID_LWEK = "grid_energy_last_week"
SK_GRID_DIFF_LWEK = "grid_energy_diff_week"
SK_GRID_PCT_LWEK = "grid_energy_pct_week"
SK_HOUSE_LWEK = "house_energy_last_week"
SK_HOUSE_DIFF_LWEK = "house_energy_diff_week"
SK_BAT_CH_LWEK = "battery_charge_last_week"
SK_BAT_CH_DIFF_LWEK = "battery_charge_diff_week"
SK_BAT_DIS_LWEK = "battery_discharge_last_week"
SK_BAT_DIS_DIFF_LWEK = "battery_discharge_diff_week"
SK_SOL_DIRECT_LWEK = "solar_direct_last_week"
SK_SOL_DIRECT_DIFF_LWEK = "solar_direct_diff_week"
SK_AUTARKY_LWEK = "autarky_last_week"
SK_AUTARKY_DIFF_LWEK = "autarky_diff_week"

# Vergleich – Letzter Monat
SK_SOLAR_LMON = "solar_energy_last_month"
SK_SOLAR_DIFF_LMON = "solar_energy_diff_month"
SK_SOLAR_PCT_LMON = "solar_energy_pct_month"
SK_GRID_LMON = "grid_energy_last_month"
SK_GRID_DIFF_LMON = "grid_energy_diff_month"
SK_GRID_PCT_LMON = "grid_energy_pct_month"
SK_HOUSE_LMON = "house_energy_last_month"
SK_HOUSE_DIFF_LMON = "house_energy_diff_month"
SK_BAT_CH_LMON = "battery_charge_last_month"
SK_BAT_CH_DIFF_LMON = "battery_charge_diff_month"
SK_BAT_DIS_LMON = "battery_discharge_last_month"
SK_BAT_DIS_DIFF_LMON = "battery_discharge_diff_month"
SK_SOL_DIRECT_LMON = "solar_direct_last_month"
SK_SOL_DIRECT_DIFF_LMON = "solar_direct_diff_month"
SK_AUTARKY_LMON = "autarky_last_month"
SK_AUTARKY_DIFF_LMON = "autarky_diff_month"

# Vergleich – Letztes Jahr
SK_SOLAR_LYEAR = "solar_energy_last_year"
SK_SOLAR_DIFF_LYEAR = "solar_energy_diff_year"
SK_SOLAR_PCT_LYEAR = "solar_energy_pct_year"
SK_GRID_LYEAR = "grid_energy_last_year"
SK_GRID_DIFF_LYEAR = "grid_energy_diff_year"
SK_GRID_PCT_LYEAR = "grid_energy_pct_year"
SK_HOUSE_LYEAR = "house_energy_last_year"
SK_HOUSE_DIFF_LYEAR = "house_energy_diff_year"
SK_BAT_CH_LYEAR = "battery_charge_last_year"
SK_BAT_CH_DIFF_LYEAR = "battery_charge_diff_year"
SK_BAT_DIS_LYEAR = "battery_discharge_last_year"
SK_BAT_DIS_DIFF_LYEAR = "battery_discharge_diff_year"
SK_SOL_DIRECT_LYEAR = "solar_direct_last_year"
SK_SOL_DIRECT_DIFF_LYEAR = "solar_direct_diff_year"
SK_AUTARKY_LYEAR = "autarky_last_year"
SK_AUTARKY_DIFF_LYEAR = "autarky_diff_year"

# Diagnostik
SK_DIAG = "diagnostics_sensor"

# CSV-Spalten
CSV_COLUMNS = [
    "period_id",
    "solar_energy_generated_kwh",
    "battery_energy_charged_kwh",
    "battery_energy_to_house_kwh",
    "grid_energy_imported_kwh",
    "solar_energy_directly_consumed_kwh",
    "house_energy_total_kwh",
    "battery_share_of_consumption_kwh",
    "solar_share_of_consumption_kwh",
    "autarky_percent",
    "grid_cost_eur",
    "solar_savings_eur",
    "saved_at",
    "source_info",
]

# HA Storage Key
STORAGE_KEY = f"{DOMAIN}_state_v2"
STORAGE_VERSION = 2
