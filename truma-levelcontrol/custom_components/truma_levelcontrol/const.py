"""Constants for the local Truma LevelControl Bluetooth integration."""
from datetime import timedelta

DOMAIN = "truma_levelcontrol"
CONF_ADDRESS = "address"
UPDATE_INTERVAL = timedelta(minutes=30)

SERVICE_UUID = "00000a00-0000-1000-8000-00805f9b34fb"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
MODEL_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
SERIAL_UUID = "00002a25-0000-1000-8000-00805f9b34fb"
FIRMWARE_UUID = "00002a26-0000-1000-8000-00805f9b34fb"
HARDWARE_UUID = "00002a27-0000-1000-8000-00805f9b34fb"
MANUFACTURER_UUID = "00002a29-0000-1000-8000-00805f9b34fb"

TRUMA_UUIDS = {
    "710": "22bfa710-6afe-4cc5-b3ff-3e140baedeb6",
    "711": "22bfa711-6afe-4cc5-b3ff-3e140baedeb6",
    "712": "22bfa712-6afe-4cc5-b3ff-3e140baedeb6",
    "713": "22bfa713-6afe-4cc5-b3ff-3e140baedeb6",
    "714": "22bfa714-6afe-4cc5-b3ff-3e140baedeb6",
    "715": "22bfa715-6afe-4cc5-b3ff-3e140baedeb6",
}
MEASUREMENT_UUID = TRUMA_UUIDS["710"]

MANUFACTURER = "Truma"
MODEL = "LevelControl"

# Vehicle bottle profile: German grey 11 kg steel ownership bottle.
# Known public base data: 11 kg nominal LPG, 27.2 l water capacity,
# about 300 mm outer diameter. The effective internal profile below is a
# cylinder with spherical end caps. Radius is based on ~296 mm inner diameter.
# Effective body height/cap depth are calibrated against the official Truma
# LevelControl app on THIS bottle profile: 289 mm measured liquid height =
# 84 % = 9.2 kg (15.09.2026, app timestamp 10:05:52). Total water volume stays
# constrained to 27.2 l. This preserves a non-linear height->volume curve.
BOTTLE_PROFILE = "Deutschland – 11 kg Eigentumsflasche Stahl"
BOTTLE_NOMINAL_GAS_KG = 11.0
BOTTLE_WATER_VOLUME_L = 27.2
BOTTLE_INNER_RADIUS_MM = 148.0
BOTTLE_EFFECTIVE_INNER_HEIGHT_MM = 446.69871064
BOTTLE_EFFECTIVE_CAP_DEPTH_MM = 53.79639190
PROPANE_LITERS_PER_KG = 1.96
PROPANE_DENSITY_KG_L = 1.0 / PROPANE_LITERS_PER_KG
# 11 kg nominal fill corresponds to roughly 21.56 l liquid propane. The
# calibrated curve reaches this point near 340 mm. 360 mm gives generous
# headroom while rejecting the previously observed doubled/stale 581 mm echo.
MAX_VALID_LIQUID_HEIGHT_MM = 360.0
