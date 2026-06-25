"""Diagnostics for Ring Intercom Health."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import RingIntercomHealthCoordinator
from .helpers import config_values
from .models import RingIntercomHealthConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: RingIntercomHealthConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data.coordinator
    data = (
        coordinator.data
        if isinstance(coordinator, RingIntercomHealthCoordinator)
        else None
    )

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
        },
        "config": config_values(entry),
        "runtime": None
        if data is None
        else {
            "healthy": data.healthy,
            "reason": data.reason,
            "connection_signals": data.connection_signals,
            "bad_since": data.bad_since.isoformat() if data.bad_since else None,
            "last_check": data.last_check.isoformat() if data.last_check else None,
            "last_reload": data.last_reload.isoformat() if data.last_reload else None,
            "reload_count": data.reload_count,
            "suppressed_reload_count": data.suppressed_reload_count,
            "ring_entry_id": data.ring_entry_id,
            "ring_entry_state": data.ring_entry_state,
            "runtime_data_present": data.runtime_data_present,
            "api_last_probe": (
                data.api_last_probe.isoformat() if data.api_last_probe else None
            ),
            "api_last_success": (
                data.api_last_success.isoformat() if data.api_last_success else None
            ),
            "api_last_success_age_seconds": data.api_last_success_age_seconds,
            "listener_expected": data.listener_expected,
            "listener_owned": data.listener_owned,
            "listener_started": data.listener_started,
            "listener_count": data.listener_count,
            "listener_private_health": data.listener_private_health,
            "listener_subscribed": data.listener_subscribed,
            "listener_fcm_token_present": data.listener_fcm_token_present,
            "listener_receiver_present": data.listener_receiver_present,
            "listener_receiver_task_state": data.listener_receiver_task_state,
            "listener_session_task_state": data.listener_session_task_state,
            "listener_callback_registered": data.listener_callback_registered,
            "scheduled_reload": data.scheduled_reload,
            "scheduled_reload_interval_seconds": data.scheduled_reload_interval_seconds,
            "next_scheduled_reload": (
                data.next_scheduled_reload.isoformat()
                if data.next_scheduled_reload
                else None
            ),
        },
    }
