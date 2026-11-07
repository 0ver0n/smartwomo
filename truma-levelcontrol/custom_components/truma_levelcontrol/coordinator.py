from __future__ import annotations

import asyncio
import logging
import math

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BATTERY_UUID,
    BOTTLE_EFFECTIVE_CAP_DEPTH_MM,
    BOTTLE_EFFECTIVE_INNER_HEIGHT_MM,
    BOTTLE_INNER_RADIUS_MM,
    BOTTLE_NOMINAL_GAS_KG,
    BOTTLE_PROFILE,
    BOTTLE_WATER_VOLUME_L,
    CONF_ADDRESS,
    DOMAIN,
    FIRMWARE_UUID,
    HARDWARE_UUID,
    MANUFACTURER_UUID,
    MAX_VALID_LIQUID_HEIGHT_MM,
    MEASUREMENT_UUID,
    MODEL_UUID,
    PROPANE_DENSITY_KG_L,
    SERIAL_UUID,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _decode_text(value: bytes) -> str | None:
    if not value:
        return None
    text = value.decode("utf-8", errors="ignore").strip("\x00 ")
    return text or None


def _spherical_cap_volume_mm3(height_mm: float) -> float:
    """Effective volume of one dished bottle end from its pole to height."""
    r = BOTTLE_INNER_RADIUS_MM
    d = BOTTLE_EFFECTIVE_CAP_DEPTH_MM
    sphere_radius = (r * r + d * d) / (2.0 * d)
    h = max(0.0, min(d, height_mm))
    return math.pi * h * h * (3.0 * sphere_radius - h) / 3.0


def _volume_from_height_l(height_mm: float) -> float:
    """Convert LevelControl liquid height to calibrated 11 kg bottle volume."""
    r = BOTTLE_INNER_RADIUS_MM
    d = BOTTLE_EFFECTIVE_CAP_DEPTH_MM
    total_h = BOTTLE_EFFECTIVE_INNER_HEIGHT_MM
    area = math.pi * r * r
    cap_volume = _spherical_cap_volume_mm3(d)

    y = max(0.0, min(total_h, height_mm))
    if y <= d:
        volume_mm3 = _spherical_cap_volume_mm3(y)
    elif y <= total_h - d:
        volume_mm3 = cap_volume + area * (y - d)
    else:
        remaining_top = total_h - y
        volume_mm3 = (
            BOTTLE_WATER_VOLUME_L * 1_000_000.0
            - _spherical_cap_volume_mm3(remaining_top)
        )
    return max(0.0, min(BOTTLE_WATER_VOLUME_L, volume_mm3 / 1_000_000.0))


class TrumaLevelControlCoordinator(DataUpdateCoordinator[dict]):
    """Read one Truma LevelControl directly through Home Assistant Bluetooth."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.address = entry.data[CONF_ADDRESS]
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.address}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"LevelControl {self.address} ist derzeit nicht per Bluetooth erreichbar"
            )

        client = None
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                f"Truma LevelControl {self.address}",
                max_attempts=3,
            )
            # Proven on the local BlueZ adapter: GATT values become reliable only
            # after a short settling period following connect.
            await asyncio.sleep(3.0)

            measurement = bytes(await client.read_gatt_char(MEASUREMENT_UUID))
            battery_raw = bytes(await client.read_gatt_char(BATTERY_UUID))

            async def read_optional(uuid: str) -> bytes:
                try:
                    return bytes(await client.read_gatt_char(uuid))
                except Exception:
                    return b""

            model_raw = await read_optional(MODEL_UUID)
            serial_raw = await read_optional(SERIAL_UUID)
            firmware_raw = await read_optional(FIRMWARE_UUID)
            hardware_raw = await read_optional(HARDWARE_UUID)
            manufacturer_raw = await read_optional(MANUFACTURER_UUID)
        except Exception as err:
            raise UpdateFailed(f"BLE-Verbindung fehlgeschlagen: {err}") from err
        finally:
            if client is not None and client.is_connected:
                await client.disconnect()

        if len(measurement) < 16:
            raise UpdateFailed("Truma-Messcharacteristic 710 ist kürzer als 16 Byte")

        # Characteristic 710, verified against the official Truma app:
        # bytes 2..3: liquid height in mm; bytes 6..7: ultrasound transit time
        # in us; byte 9: signed temperature in degC. On 15.09.2026 the app
        # showed 17 degC while this byte was 0x11.
        raw_height_mm = int.from_bytes(measurement[2:4], "little")
        transit_time_us = int.from_bytes(measurement[6:8], "little")
        temperature_c = int.from_bytes(measurement[9:10], "little", signed=True)

        physical_height_valid = 0 < raw_height_mm <= MAX_VALID_LIQUID_HEIGHT_MM
        transit_relation_valid = (
            transit_time_us > 0
            and 0.35 <= (raw_height_mm / transit_time_us) <= 0.45
        )
        temperature_valid = -40 <= temperature_c <= 85
        measurement_valid = (
            physical_height_valid and transit_relation_valid and temperature_valid
        )

        liquid_volume_l: float | None = None
        gas_kg_exact: float | None = None
        fill_percent_exact: float | None = None
        if measurement_valid:
            liquid_volume_l = _volume_from_height_l(float(raw_height_mm))
            gas_kg_exact = min(
                BOTTLE_NOMINAL_GAS_KG,
                liquid_volume_l * PROPANE_DENSITY_KG_L,
            )
            fill_percent_exact = min(
                100.0, gas_kg_exact / BOTTLE_NOMINAL_GAS_KG * 100.0
            )

        service_info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=True
        )
        rssi = service_info.rssi if service_info is not None else None

        return {
            "battery": battery_raw[0] if battery_raw else None,
            "rssi": rssi,
            "measurement_valid": measurement_valid,
            "liquid_height_mm": raw_height_mm if measurement_valid else None,
            "transit_time_us": transit_time_us if transit_time_us > 0 else None,
            "temperature_c": temperature_c if temperature_valid else None,
            # Match the official LevelControl app presentation: whole percent
            # and one decimal kilogram. Internal curve remains continuous.
            "liquid_volume_l": round(liquid_volume_l, 2) if liquid_volume_l is not None else None,
            "gas_kg": round(gas_kg_exact, 1) if gas_kg_exact is not None else None,
            "fill_percent": int(round(fill_percent_exact)) if fill_percent_exact is not None else None,
            "fill_percent_exact": round(fill_percent_exact, 2) if fill_percent_exact is not None else None,
            "measurement_raw": measurement.hex(" "),
            "status_10": measurement[10],
            "status_14": measurement[14],
            "bottle_profile": BOTTLE_PROFILE,
            "model": _decode_text(model_raw),
            "serial": _decode_text(serial_raw),
            "firmware": _decode_text(firmware_raw),
            "hardware": _decode_text(hardware_raw),
            "manufacturer": _decode_text(manufacturer_raw),
        }
