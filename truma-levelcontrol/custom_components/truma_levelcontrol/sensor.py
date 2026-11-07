from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfLength,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER, MODEL
from .coordinator import TrumaLevelControlCoordinator


@dataclass(frozen=True, kw_only=True)
class LevelControlSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]


SENSORS: tuple[LevelControlSensorDescription, ...] = (
    LevelControlSensorDescription(
        key="fill_percent",
        translation_key="fill_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fill_percent"),
    ),
    LevelControlSensorDescription(
        key="gas_kg",
        translation_key="gas_kg",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("gas_kg"),
    ),
    LevelControlSensorDescription(
        key="temperature_c",
        translation_key="temperature_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("temperature_c"),
    ),
    LevelControlSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("battery"),
    ),
    LevelControlSensorDescription(
        key="measurement_status",
        translation_key="measurement_status",
        value_fn=lambda data: "OK" if data.get("measurement_valid") else "Ungültig",
    ),
    LevelControlSensorDescription(
        key="liquid_volume_l",
        translation_key="liquid_volume_l",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("liquid_volume_l"),
    ),
    LevelControlSensorDescription(
        key="liquid_height_mm",
        translation_key="liquid_height_mm",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("liquid_height_mm"),
    ),
    LevelControlSensorDescription(
        key="transit_time_us",
        translation_key="transit_time_us",
        native_unit_of_measurement="µs",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("transit_time_us"),
    ),
    LevelControlSensorDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("rssi"),
    ),
    LevelControlSensorDescription(
        key="measurement_raw",
        translation_key="measurement_raw",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("measurement_raw"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TrumaLevelControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LevelControlSensor(coordinator, entry, description)
        for description in SENSORS
    )


class LevelControlSensor(CoordinatorEntity[TrumaLevelControlCoordinator], SensorEntity):
    entity_description: LevelControlSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrumaLevelControlCoordinator,
        entry: ConfigEntry,
        description: LevelControlSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        address = entry.data[CONF_ADDRESS]
        safe_address = address.replace(":", "").lower()
        self._attr_unique_id = f"{safe_address}_{description.key}"

        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=f"Truma LevelControl – {entry.title}",
            manufacturer=data.get("manufacturer") or MANUFACTURER,
            model=data.get("model") or MODEL,
            sw_version=data.get("firmware"),
            hw_version=data.get("hardware"),
            serial_number=data.get("serial"),
        )

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return None
        if self.entity_description.key == "fill_percent":
            return {
                "Flaschenprofil": self.coordinator.data.get("bottle_profile"),
                "Messung gültig": self.coordinator.data.get("measurement_valid"),
                "Füllstand intern": self.coordinator.data.get("fill_percent_exact"),
                "Kalibrierung": "289 mm = 84 % / 9,2 kg gegen offizielle Truma-LevelControl-App am 15.09.2026",
            }
        if self.entity_description.key == "measurement_raw":
            return {
                "status_10_roh": self.coordinator.data.get("status_10"),
                "status_14_roh": self.coordinator.data.get("status_14"),
            }
        return None
