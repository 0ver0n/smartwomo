"""Sensor-Plattform V4 – Stabile Entity IDs, korrekte DeviceInfo.

Änderungen seit V5.2:
- Config Entry Version aus __init__.py konsistent
- DeviceInfo sw_version nutzt die Integrationsversion
- Entity IDs stabil: unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"
  (unverändert seit V2 – bestehende Entity-Registrierungen bleiben erhalten)
- Korrekte Filterung nach Sensorgruppen
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, VERSION, COORDINATOR,
    SENSOR_GROUP_BASIC, SENSOR_GROUP_COMPARE,
    SENSOR_GROUP_DIAGNOSTICS, SENSOR_GROUP_EXPERT,
    CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS,
)
from .coordinator import SolarMixBalanceCoordinator
from .entity_descriptions import ALL_SENSORS, SolarSensorDesc

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren einrichten – nur konfigurierte Gruppen."""
    coordinator: SolarMixBalanceCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    active_groups: list[str] = entry.data.get(CONF_SENSOR_GROUPS, ALL_SENSOR_GROUPS)
    if isinstance(active_groups, str):
        active_groups = [active_groups]
    if not active_groups:
        active_groups = ALL_SENSOR_GROUPS

    entities: list[SolarMixSensor] = []
    skipped = 0

    for desc in ALL_SENSORS:
        if desc.group not in active_groups:
            skipped += 1
            continue
        if desc.key == "diagnostics_sensor":
            entities.append(SolarMixDiagSensor(coordinator, entry, desc))
        else:
            entities.append(SolarMixSensor(coordinator, entry, desc))

    async_add_entities(entities)
    _LOGGER.info(
        "Solar Mix Balance V%s: %d Sensoren erstellt, %d übersprungen (Gruppen: %s)",
        VERSION, len(entities), skipped, active_groups,
    )


class SolarMixSensor(CoordinatorEntity[SolarMixBalanceCoordinator], SensorEntity):
    """Solar Mix Balance Sensor.

    unique_id ist stabil seit V2: f"{DOMAIN}_{entry.entry_id}_{description.key}"
    Bestehende Entity-Registrierungen in HA bleiben erhalten.
    """

    entity_description: SolarSensorDesc
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SolarMixBalanceCoordinator,
        entry: ConfigEntry,
        description: SolarSensorDesc,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        # STABILE unique_id – unverändert seit V2
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"
        # DeviceInfo: ein zentrales virtuelles Gerät pro Config Entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Solar Mix Balance",
            manufacturer="Solar Mix Balance",
            model="Virtuelle Energie-Zentrale",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Optional[float]:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(self.entity_description.data_key)
        if val is None or isinstance(val, dict):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "group": self.entity_description.group,
            "data_key": self.entity_description.data_key,
            "integration": DOMAIN,
            "version": VERSION,
        }


class SolarMixDiagSensor(SolarMixSensor):
    """Diagnostik-Sensor."""

    @property
    def native_value(self) -> Optional[str]:
        if self.coordinator.data is None:
            return None
        diag = self.coordinator.data.get("diagnostics", {})
        return diag.get("last_calc")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        diag = self.coordinator.data.get("diagnostics", {})
        return {
            "source_mapping": diag.get("source_mapping", {}),
            "fallback_flags": diag.get("fallback_flags", {}),
            "data_quality_issues": diag.get("data_quality_issues", [])[-10:],
            "unavailable_sources": diag.get("unavailable_sources", []),
            "last_csv_write": diag.get("last_csv_write", {}),
            "last_backup": diag.get("last_backup"),
            "last_restore": diag.get("last_restore"),
            "restore_log": diag.get("restore_log", [])[-5:],
            "archive_errors": diag.get("archive_errors", [])[-5:],
            "meter_mode": diag.get("meter_mode", {}),
            "integration": DOMAIN,
            "version": VERSION,
        }
