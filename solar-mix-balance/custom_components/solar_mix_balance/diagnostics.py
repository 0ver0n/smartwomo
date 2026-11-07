"""Diagnostics-Unterstützung V2 für Solar Mix Balance."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, COORDINATOR, VERSION
from .coordinator import SolarMixBalanceCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Gibt vollständige Diagnosedaten zurück.

    Abrufbar unter: Einstellungen → Integrationen → Solar Mix Balance → Diagnose
    """
    coordinator: SolarMixBalanceCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    return {
        "integration": {
            "domain": DOMAIN,
            "version": VERSION,
            "entry_id": entry.entry_id,
            "entry_title": entry.title,
        },
        "configuration": {
            k: v for k, v in entry.data.items()
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": getattr(coordinator, "last_update_success_time", None) and
                                getattr(coordinator, "last_update_success_time").isoformat(),
            "update_interval_s": coordinator.update_interval.total_seconds()
                                 if coordinator.update_interval else None,
            "state_listeners": len(coordinator._unsub_state_listeners),
            "debounce_active": (
                coordinator._debounce_task is not None
                and not coordinator._debounce_task.done()
            ),
        },
        "diagnostics": coordinator.diag,
        "accumulators": {k: round(v, 5) for k, v in coordinator._acc.items()},
        "compare_values": {
            k: (round(v, 5) if v is not None else None)
            for k, v in coordinator._cmp.items()
        },
        "energy_snapshots": {
            k: (round(v, 5) if v is not None else None)
            for k, v in coordinator._energy_snapshot.items()
        },
        "period_timestamps": coordinator._period,
        "current_data_snapshot": {
            k: v for k, v in (coordinator.data or {}).items()
            if k != "diagnostics"
        },
    }
