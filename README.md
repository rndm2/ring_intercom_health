# Ring Intercom Health

Home Assistant custom integration that watchdogs the existing Ring integration.

This is not a Ring API replacement and it does not open the door. It does not use Ring entities as health signals or anchors. It resolves the Ring config entry directly by namespace/domain. If there is exactly one Ring config entry, Auto is enough. If there are multiple Ring entries, choose the exact one.

Health is evaluated from the Ring integration runtime data:

- Ring config entry state
- Ring `runtime_data`
- Ring devices coordinator
- passive subscription to Ring devices coordinator updates
- throttled active API coordinator refresh, when enabled
- last successful API verification age
- watchdog-owned Ring realtime listener subscription
- Ring realtime listener coordinator
- Ring realtime listener `started` flag
- private Ring listener integrity flags, when available:
  - listener subscribed state
  - FCM token presence
  - FCM receiver presence/task state
  - session refresh task state
  - notification callback registration

If the Ring runtime/API/listener looks unhealthy for long enough, the watchdog
reloads only the selected Ring config entry. It does not soft-restart the Ring
listener. If private listener flags show a hard-bad state, the recovery action is
the normal full Ring config-entry reload, protected by grace periods, cooldowns,
and reload-budget limits.

## UI/device linking

This integration is a Ring runtime connection watchdog. It does not use Ring
entities as health signals. The optional source entity is only used for
Home Assistant UI/device linking via the source Ring device.


## Install

Copy this folder to:

```text
/config/custom_components/ring_intercom_health
```

Restart Home Assistant and add **Ring Intercom Health** from Devices & services.

## Recommended settings

Select `Auto` if there is exactly one Ring config entry. If there are multiple Ring accounts/config entries, select the exact Ring entry.

Suggested defaults:

```text
active_api_probe: true
active_probe_interval_seconds: 300
require_listener_started: true
check_interval_seconds: 60
api_max_age_seconds: 420
bad_for_seconds: 180
reload_cooldown_seconds: 1800
startup_grace_seconds: 120
post_reload_grace_seconds: 180
max_reloads_per_hour: 2
auto_reload: true
notify_on_reload: false
```

## Entities

The integration creates:

- `binary_sensor.*_connection_healthy`
- `sensor.*_reason`
- `sensor.*_api_last_success_age`
- `sensor.*_api_last_probe`
- `sensor.*_listener_state`
- `sensor.*_listener_owned`
- `sensor.*_listener_count`
- `sensor.*_listener_private_health`
- `sensor.*_listener_subscribed`
- `sensor.*_listener_fcm_token`
- `sensor.*_listener_receiver`
- `sensor.*_listener_receiver_task`
- `sensor.*_listener_session_task`
- `sensor.*_listener_callback`
- `sensor.*_reload_count`
- `sensor.*_suppressed_reload_count`
- `sensor.*_last_check`
- `sensor.*_last_reload`
- `sensor.*_bad_since`
- `button.*_reload_ring`

## Important limitation

This integration checks Ring runtime connection health. It intentionally reads
some private Home Assistant Ring/python-ring-doorbell listener internals because
Ring does not expose a public listener heartbeat. Missing private attributes are
treated as unknown, not bad. Present-but-inconsistent private state is treated
as degraded and can trigger the normal full Ring reload policy.

It does not prove that a door-open command physically opened the door. A separate
safe-open proxy button would be needed for command-level retry/verification.

## Brand assets

Brand assets are stored in the Home Assistant custom integration brand folder:

```text
custom_components/ring_intercom_health/brand/icon.png
custom_components/ring_intercom_health/brand/logo.png
```


## Device linking

`source_entity_id` is used only for UI/device linking. Health checks still use Ring runtime/coordinators. If `attach_to_source_device` is enabled, the watchdog entities report the same device identifiers/connections as the selected Ring source entity, so Home Assistant should place them under the existing Ring device. If disabled, the integration creates its own service device and links it via the source device.

## Timing defaults

The default `api_max_age_seconds` is 420 seconds so it does not conflict with the default 300 second active probe interval and 60 second check interval.
