"""Models for Ring Intercom Health."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.config_entries import ConfigEntry


@dataclass(slots=True)
class HealthData:
    """Runtime health snapshot exposed by the coordinator."""

    healthy: bool
    reason: str
    connection_signals: list[str] = field(default_factory=list)
    bad_since: datetime | None = None
    last_check: datetime | None = None
    last_reload: datetime | None = None
    reload_count: int = 0
    suppressed_reload_count: int = 0
    ring_entry_id: str | None = None
    ring_entry_state: str | None = None
    runtime_data_present: bool = False
    active_api_probe: bool = True
    active_probe_interval_seconds: int | None = None
    api_last_probe: datetime | None = None
    api_last_success: datetime | None = None
    api_last_success_age_seconds: int | None = None
    listener_expected: bool = False
    listener_owned: bool = False
    listener_started: bool | None = None
    listener_count: int | None = None
    listener_private_health: str | None = None
    listener_subscribed: bool | None = None
    listener_fcm_token_present: bool | None = None
    listener_receiver_present: bool | None = None
    listener_receiver_task_state: str | None = None
    listener_session_task_state: str | None = None
    listener_callback_registered: bool | None = None
    scheduled_reload: bool = False
    scheduled_reload_interval_seconds: int | None = None
    next_scheduled_reload: datetime | None = None


@dataclass(slots=True)
class RuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: object


type RingIntercomHealthConfigEntry = ConfigEntry[RuntimeData]
