"""Constants for Ring Intercom Health."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ring_intercom_health"
RING_DOMAIN: Final = "ring"

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]

CONF_RING_ENTRY_ID: Final = "ring_entry_id"
CONF_SOURCE_ENTITY_ID: Final = "source_entity_id"
CONF_ATTACH_TO_SOURCE_DEVICE: Final = "attach_to_source_device"
AUTO_RING_ENTRY_ID: Final = "auto"
CONF_CHECK_INTERVAL_SECONDS: Final = "check_interval_seconds"
CONF_BAD_FOR_SECONDS: Final = "bad_for_seconds"
CONF_RELOAD_COOLDOWN_SECONDS: Final = "reload_cooldown_seconds"
CONF_STARTUP_GRACE_SECONDS: Final = "startup_grace_seconds"
CONF_POST_RELOAD_GRACE_SECONDS: Final = "post_reload_grace_seconds"
CONF_AUTO_RELOAD: Final = "auto_reload"
CONF_NOTIFY_ON_RELOAD: Final = "notify_on_reload"
CONF_MAX_RELOADS_PER_HOUR: Final = "max_reloads_per_hour"
CONF_ACTIVE_API_PROBE: Final = "active_api_probe"
CONF_ACTIVE_PROBE_INTERVAL_SECONDS: Final = "active_probe_interval_seconds"
CONF_API_MAX_AGE_SECONDS: Final = "api_max_age_seconds"
CONF_REQUIRE_LISTENER_STARTED: Final = "require_listener_started"

DEFAULT_CHECK_INTERVAL_SECONDS: Final = 60
DEFAULT_BAD_FOR_SECONDS: Final = 180
DEFAULT_RELOAD_COOLDOWN_SECONDS: Final = 1800
DEFAULT_STARTUP_GRACE_SECONDS: Final = 120
DEFAULT_POST_RELOAD_GRACE_SECONDS: Final = 180
DEFAULT_AUTO_RELOAD: Final = True
DEFAULT_NOTIFY_ON_RELOAD: Final = False
DEFAULT_MAX_RELOADS_PER_HOUR: Final = 2
DEFAULT_ACTIVE_API_PROBE: Final = True
DEFAULT_ACTIVE_PROBE_INTERVAL_SECONDS: Final = 300
DEFAULT_API_MAX_AGE_SECONDS: Final = 420
DEFAULT_REQUIRE_LISTENER_STARTED: Final = True
DEFAULT_ATTACH_TO_SOURCE_DEVICE: Final = False

MIN_CHECK_INTERVAL_SECONDS: Final = 30
MIN_BAD_FOR_SECONDS: Final = 60
MIN_RELOAD_COOLDOWN_SECONDS: Final = 300
MIN_GRACE_SECONDS: Final = 0
MIN_API_MAX_AGE_SECONDS: Final = 60
MIN_ACTIVE_PROBE_INTERVAL_SECONDS: Final = 60
MAX_SECONDS: Final = 86400
MIN_MAX_RELOADS_PER_HOUR: Final = 1
MAX_MAX_RELOADS_PER_HOUR: Final = 12

MAX_REASON_LENGTH: Final = 240

ATTR_REASON: Final = "reason"
ATTR_CONNECTION_SIGNALS: Final = "connection_signals"
ATTR_BAD_SINCE: Final = "bad_since"
ATTR_LAST_CHECK: Final = "last_check"
ATTR_LAST_RELOAD: Final = "last_reload"
ATTR_RELOAD_COUNT: Final = "reload_count"
ATTR_SUPPRESSED_RELOAD_COUNT: Final = "suppressed_reload_count"
ATTR_RING_ENTRY_ID: Final = "ring_entry_id"
ATTR_RING_ENTRY_STATE: Final = "ring_entry_state"
ATTR_SOURCE_ENTITY_ID: Final = "source_entity_id"
ATTR_SOURCE_DEVICE_ID: Final = "source_device_id"
ATTR_ATTACH_TO_SOURCE_DEVICE: Final = "attach_to_source_device"
ATTR_AUTO_RELOAD: Final = "auto_reload"
ATTR_ACTIVE_API_PROBE: Final = "active_api_probe"
ATTR_ACTIVE_PROBE_INTERVAL: Final = "active_probe_interval_seconds"
ATTR_API_LAST_PROBE: Final = "api_last_probe"
ATTR_API_LAST_SUCCESS: Final = "api_last_success"
ATTR_API_LAST_SUCCESS_AGE: Final = "api_last_success_age_seconds"
ATTR_LISTENER_STARTED: Final = "listener_started"
ATTR_LISTENER_EXPECTED: Final = "listener_expected"
ATTR_LISTENER_OWNED: Final = "listener_owned"
ATTR_LISTENER_COUNT: Final = "listener_count"
ATTR_RUNTIME_DATA_PRESENT: Final = "runtime_data_present"
