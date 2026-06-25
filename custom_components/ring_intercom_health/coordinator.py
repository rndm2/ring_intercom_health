"""Coordinator for Ring Intercom Health."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.components.persistent_notification import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTIVE_API_PROBE,
    CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
    CONF_API_MAX_AGE_SECONDS,
    CONF_AUTO_RELOAD,
    CONF_BAD_FOR_SECONDS,
    CONF_CHECK_INTERVAL_SECONDS,
    CONF_MAX_RELOADS_PER_HOUR,
    CONF_NOTIFY_ON_RELOAD,
    CONF_POST_RELOAD_GRACE_SECONDS,
    CONF_RELOAD_COOLDOWN_SECONDS,
    CONF_REQUIRE_LISTENER_STARTED,
    CONF_RING_ENTRY_ID,
    CONF_SCHEDULED_RELOAD,
    CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS,
    CONF_STARTUP_GRACE_SECONDS,
    DOMAIN,
    MAX_REASON_LENGTH,
)
from .helpers import config_values, find_config_entry, resolve_ring_entry_id
from .models import HealthData

_LOGGER = logging.getLogger(__name__)

_MISSING = object()

ISSUE_RING_ENTRY = "ring_entry_missing_or_ambiguous"
ISSUE_RELOAD_LOOP = "reload_loop_detected"
ISSUE_RING_RUNTIME = "ring_runtime_unhealthy"

BUSY_STATE_NAMES = {"setup_in_progress", "unload_in_progress", "migration_in_progress"}


class RingIntercomHealthCoordinator(DataUpdateCoordinator[HealthData]):
    """Watch Ring runtime/coordinator connection and reload when it degrades."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.entry = entry
        self._setup_time = dt_util.utcnow()
        self._bad_since: datetime | None = None
        self._last_reload: datetime | None = None
        self._reload_count = 0
        self._suppressed_reload_count = 0
        self._recent_reloads: deque[datetime] = deque()
        self._last_logged_reason: str | None = None

        self._api_last_success: datetime | None = None
        self._api_last_probe: datetime | None = None

        self._subscribed_ring_entry_id: str | None = None
        self._subscribed_runtime_data: Any | None = None
        self._subscribed_devices_coordinator: Any | None = None
        self._subscribed_listen_coordinator: Any | None = None
        self._remove_api_listener: CALLBACK_TYPE | None = None
        self._remove_listen_listeners: list[CALLBACK_TYPE] = []
        self._listener_contexts: tuple[object | None, ...] = ()

        values = config_values(entry)
        update_interval = timedelta(seconds=int(values[CONF_CHECK_INTERVAL_SECONDS]))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            always_update=False,
            config_entry=entry,
        )

    async def async_shutdown(self) -> None:
        """Clear listeners and transient repair issues on unload."""

        self._clear_ring_subscriptions()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RING_ENTRY))
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RELOAD_LOOP))
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RING_RUNTIME))

    def _reset_api_probe_state(self) -> None:
        """Force the next health cycle to probe Ring API after a reload."""

        self._api_last_success = None
        self._api_last_probe = None

    async def _async_update_data(self) -> HealthData:
        """Evaluate Ring connection health and maybe reload Ring."""

        try:
            return await self._async_evaluate_health()
        except Exception as err:  # noqa: BLE001 - preserve watchdog visibility
            raise UpdateFailed(f"Ring Intercom Health check failed: {err}") from err

    async def _async_evaluate_health(self) -> HealthData:
        """Evaluate health and run reload policy."""

        now = dt_util.utcnow()
        values = config_values(self.entry)
        configured_ring_entry_id = values[CONF_RING_ENTRY_ID]
        auto_reload: bool = values[CONF_AUTO_RELOAD]
        notify_on_reload: bool = values[CONF_NOTIFY_ON_RELOAD]
        startup_grace = int(values[CONF_STARTUP_GRACE_SECONDS])
        post_reload_grace = int(values[CONF_POST_RELOAD_GRACE_SECONDS])
        bad_for = int(values[CONF_BAD_FOR_SECONDS])
        cooldown = int(values[CONF_RELOAD_COOLDOWN_SECONDS])
        max_reloads_per_hour = int(values[CONF_MAX_RELOADS_PER_HOUR])
        scheduled_reload = bool(values[CONF_SCHEDULED_RELOAD])
        scheduled_reload_interval = int(values[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS])

        ring_entry_id = resolve_ring_entry_id(self.hass, configured_ring_entry_id)
        ring_entry = (
            find_config_entry(self.hass, ring_entry_id) if ring_entry_id else None
        )
        ring_entry_state = self._entry_state_name(ring_entry)

        result = await self._evaluate_ring_runtime(now, ring_entry, values)
        healthy = result["healthy"]
        reason = result["reason"]
        signals = result["signals"]

        in_startup_grace = self._seconds_since(self._setup_time, now) < startup_grace
        in_post_reload_grace = (
            self._last_reload is not None
            and self._seconds_since(self._last_reload, now) < post_reload_grace
        )
        self._update_issues(
            reason,
            configured_ring_entry_id,
            ring_entry_id,
            healthy,
            in_startup_grace or in_post_reload_grace,
        )

        if healthy:
            self._bad_since = None
            self._clear_runtime_issues()
            scheduled_snapshot = await self._maybe_run_scheduled_reload(
                now,
                scheduled_reload,
                scheduled_reload_interval,
                cooldown,
                max_reloads_per_hour,
                ring_entry_id,
                ring_entry,
                ring_entry_state,
                signals,
                result,
                in_startup_grace,
                in_post_reload_grace,
                notify_on_reload,
            )
            if scheduled_snapshot is not None:
                return scheduled_snapshot
            if self._last_logged_reason != reason:
                _LOGGER.info("Ring Intercom Health recovered")
                self._last_logged_reason = reason
            return self._snapshot(
                now,
                True,
                reason,
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        if self._bad_since is None:
            self._bad_since = now
            self._log_reason_once(reason, signals)

        if not auto_reload:
            return self._snapshot(
                now,
                False,
                f"{reason}; auto reload disabled",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        if ring_entry_id is None:
            return self._snapshot(
                now,
                False,
                "Ring config entry is missing or ambiguous",
                signals,
                None,
                None,
                result,
            )

        if ring_entry is None:
            return self._snapshot(
                now,
                False,
                "Ring config entry not found",
                signals,
                ring_entry_id,
                None,
                result,
            )

        if ring_entry_state in BUSY_STATE_NAMES:
            return self._snapshot(
                now,
                False,
                f"{reason}; Ring entry busy",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        if in_startup_grace:
            return self._snapshot(
                now,
                False,
                f"{reason}; startup grace active",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        if in_post_reload_grace:
            return self._snapshot(
                now,
                False,
                f"{reason}; post reload grace active",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        if self._bad_since is not None:
            if self._seconds_since(self._bad_since, now) < bad_for:
                return self._snapshot(
                    now,
                    False,
                    reason,
                    signals,
                    ring_entry_id,
                    ring_entry_state,
                    result,
                )

        if self._last_reload is not None:
            if self._seconds_since(self._last_reload, now) < cooldown:
                self._suppressed_reload_count += 1
                _LOGGER.debug("Ring reload suppressed by cooldown; reason=%s", reason)
                return self._snapshot(
                    now,
                    False,
                    f"{reason}; reload cooldown active",
                    signals,
                    ring_entry_id,
                    ring_entry_state,
                    result,
                )

        if not self._reload_budget_available(now, max_reloads_per_hour):
            self._suppressed_reload_count += 1
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_RELOAD_LOOP),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_RELOAD_LOOP,
                translation_placeholders={"max_reloads": str(max_reloads_per_hour)},
            )
            _LOGGER.warning(
                "Ring reload suppressed because max_reloads_per_hour=%s was reached",
                max_reloads_per_hour,
            )
            return self._snapshot(
                now,
                False,
                f"{reason}; reload budget exhausted",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        try:
            await self._reload_ring_entry(
                ring_entry_id,
                reason,
                signals,
                notify_on_reload,
            )
        except Exception as err:  # noqa: BLE001 - expose reload failure as state
            self._suppressed_reload_count += 1
            _LOGGER.exception("Ring config entry reload failed")
            return self._snapshot(
                now,
                False,
                f"{reason}; reload failed: {type(err).__name__}",
                signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        self._last_reload = now
        self._reload_count += 1
        self._recent_reloads.append(now)
        self._bad_since = None
        self._clear_ring_subscriptions()
        self._reset_api_probe_state()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RELOAD_LOOP))

        ring_entry_after = find_config_entry(self.hass, ring_entry_id)
        ring_entry_state_after = self._entry_state_name(ring_entry_after)
        return self._snapshot(
            now,
            False,
            f"{reason}; Ring config entry reloaded",
            signals,
            ring_entry_id,
            ring_entry_state_after,
            result,
        )

    async def _evaluate_ring_runtime(
        self,
        now: datetime,
        ring_entry: ConfigEntry | None,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Return runtime connection health for the selected Ring config entry."""

        result: dict[str, Any] = {
            "healthy": False,
            "reason": "Ring config entry not found",
            "signals": [],
            "runtime_data_present": False,
            "active_api_probe": bool(values[CONF_ACTIVE_API_PROBE]),
            "active_probe_interval_seconds": int(
                values[CONF_ACTIVE_PROBE_INTERVAL_SECONDS]
            ),
            "scheduled_reload": bool(values[CONF_SCHEDULED_RELOAD]),
            "scheduled_reload_interval_seconds": int(
                values[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS]
            ),
            "listener_expected": False,
            "listener_owned": False,
            "listener_started": None,
            "listener_count": None,
        }

        if ring_entry is None:
            result["signals"].append("ring_entry=missing")
            self._clear_ring_subscriptions()
            return result

        entry_state_name = self._entry_state_name(ring_entry)
        result["signals"].append(f"ring_entry_state={entry_state_name}")
        if ring_entry.state is not ConfigEntryState.LOADED:
            result["reason"] = f"Ring config entry is {entry_state_name}"
            self._clear_ring_subscriptions()
            return result

        runtime_data = getattr(ring_entry, "runtime_data", None)
        result["runtime_data_present"] = runtime_data is not None
        if runtime_data is None:
            result["reason"] = "Ring runtime_data missing"
            result["signals"].append("runtime_data=missing")
            self._clear_ring_subscriptions()
            return result

        devices_coordinator = getattr(runtime_data, "devices_coordinator", None)
        if devices_coordinator is None:
            result["reason"] = "Ring devices coordinator missing"
            result["signals"].append("devices_coordinator=missing")
            self._clear_ring_subscriptions()
            return result

        listen_coordinator = getattr(runtime_data, "listen_coordinator", None)
        self._ensure_ring_subscriptions(
            ring_entry.entry_id,
            runtime_data,
            devices_coordinator,
            listen_coordinator,
            bool(values[CONF_REQUIRE_LISTENER_STARTED]),
        )

        probe_error = await self._maybe_probe_api(devices_coordinator, values, now)
        if probe_error is not None:
            result["reason"] = f"Ring API probe failed: {probe_error}"
            result["signals"].append(f"api_probe_error={probe_error}")
            return result

        last_update_success = getattr(devices_coordinator, "last_update_success", None)
        result["signals"].append(f"api_last_update_success={last_update_success}")
        if last_update_success is False:
            result["reason"] = "Ring devices coordinator last update failed"
            return result

        if last_update_success is True and self._api_last_success is None:
            self._api_last_success = now

        if self._api_last_success is None:
            result["reason"] = "Ring API has not reported a successful update yet"
            result["signals"].append("api_last_success=never")
            return result

        api_age = int(self._seconds_since(self._api_last_success, now))
        result["api_last_success_age_seconds"] = api_age
        result["signals"].append(f"api_last_success_age={api_age}s")
        if api_age > int(values[CONF_API_MAX_AGE_SECONDS]):
            result["reason"] = f"Ring API last success is stale: {api_age}s"
            return result

        listen_result = self._evaluate_listener(listen_coordinator, values)
        result.update(listen_result)
        result["signals"].extend(listen_result["signals"])
        if not listen_result["healthy"]:
            result["reason"] = listen_result["reason"]
            return result

        result["healthy"] = True
        result["reason"] = "healthy"
        return result

    async def _maybe_probe_api(
        self,
        devices_coordinator: Any,
        values: dict[str, Any],
        now: datetime,
    ) -> str | None:
        """Actively ask Ring's devices coordinator to refresh when due."""

        if not values[CONF_ACTIVE_API_PROBE]:
            return None

        interval = int(values[CONF_ACTIVE_PROBE_INTERVAL_SECONDS])
        if self._api_last_probe is not None:
            if self._seconds_since(self._api_last_probe, now) < interval:
                return None

        request_refresh = getattr(devices_coordinator, "async_request_refresh", None)
        if request_refresh is None:
            return "async_request_refresh_missing"

        self._api_last_probe = now
        try:
            await request_refresh()
        except Exception as err:  # noqa: BLE001 - expose external coordinator failure
            return type(err).__name__

        if getattr(devices_coordinator, "last_update_success", None) is True:
            self._api_last_success = now
        return None

    def _evaluate_listener(
        self,
        listen_coordinator: Any,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate Ring realtime listener state from our own subscription."""

        result: dict[str, Any] = {
            "healthy": True,
            "reason": "listener not required",
            "signals": [],
            "listener_expected": False,
            "listener_owned": False,
            "listener_started": None,
            "listener_count": None,
            "listener_private_health": None,
            "listener_subscribed": None,
            "listener_fcm_token_present": None,
            "listener_receiver_present": None,
            "listener_receiver_task_state": None,
            "listener_session_task_state": None,
            "listener_callback_registered": None,
        }

        listener_expected = bool(values[CONF_REQUIRE_LISTENER_STARTED])
        result["listener_expected"] = listener_expected

        if listen_coordinator is None:
            if listener_expected:
                result["healthy"] = False
                result["reason"] = "Ring listen coordinator missing"
            result["signals"].append("listen_coordinator=missing")
            return result

        listener_count = self._safe_len(getattr(listen_coordinator, "_listeners", None))
        event_listener = getattr(listen_coordinator, "event_listener", None)
        listener_started = (
            bool(getattr(event_listener, "started", False))
            if event_listener is not None
            else None
        )
        listener_owned = (
            self._subscribed_listen_coordinator is listen_coordinator
            and bool(self._remove_listen_listeners)
        )
        result["listener_owned"] = listener_owned
        result["listener_started"] = listener_started
        result["listener_count"] = listener_count
        result["signals"].append(f"listener_required={listener_expected}")
        result["signals"].append(f"listener_owned={listener_owned}")
        result["signals"].append(f"listener_started={listener_started}")
        if listener_count is not None:
            result["signals"].append(f"listener_count={listener_count}")
        result["signals"].append(
            f"watchdog_listener_contexts={len(self._listener_contexts)}"
        )

        private_state = self._inspect_private_listener_state(
            listen_coordinator,
            event_listener,
            listener_started,
        )
        result.update(private_state)
        result["signals"].extend(private_state["signals"])

        if listener_expected and private_state["bad_reasons"]:
            result["healthy"] = False
            result["reason"] = (
                "Ring realtime listener private state unhealthy: "
                + "; ".join(private_state["bad_reasons"][:3])
            )
            return result

        if listener_expected and not listener_owned:
            result["healthy"] = False
            result["reason"] = "Ring realtime listener is not owned by watchdog"
            return result

        if listener_expected and not listener_started:
            result["healthy"] = False
            result["reason"] = "Ring realtime listener is not started"
            return result

        result["healthy"] = True
        result["reason"] = "listener healthy"
        return result

    def _inspect_private_listener_state(
        self,
        listen_coordinator: Any,
        event_listener: Any | None,
        listener_started: bool | None,
    ) -> dict[str, Any]:
        """Inspect private Ring listener internals for hard-dead states.

        This intentionally piggybacks on Home Assistant Ring/python-ring-doorbell
        internals. Missing private attributes are reported as unknown, not bad.
        Present-but-inconsistent private state is treated as unhealthy and can
        trigger the normal full Ring config-entry reload policy.
        """

        result: dict[str, Any] = {
            "signals": [],
            "bad_reasons": [],
            "listener_private_health": "unknown",
            "listener_subscribed": None,
            "listener_fcm_token_present": None,
            "listener_receiver_present": None,
            "listener_receiver_task_state": None,
            "listener_session_task_state": None,
            "listener_callback_registered": None,
        }

        if event_listener is None:
            result["signals"].append("event_listener=missing")
            result["listener_private_health"] = "bad"
            result["bad_reasons"].append("event_listener_missing")
            return result

        bad_reasons: list[str] = []
        listener_is_started = bool(listener_started)

        subscribed = getattr(event_listener, "subscribed", _MISSING)
        if subscribed is not _MISSING:
            result["listener_subscribed"] = bool(subscribed)
            result["signals"].append(f"listener_subscribed={bool(subscribed)}")
            if listener_is_started and not subscribed:
                bad_reasons.append("listener_not_subscribed")
        else:
            result["signals"].append("listener_subscribed=unknown")

        fcm_token = getattr(event_listener, "fcm_token", _MISSING)
        if fcm_token is not _MISSING:
            token_present = bool(fcm_token)
            result["listener_fcm_token_present"] = token_present
            result["signals"].append(f"listener_fcm_token_present={token_present}")
            if listener_is_started and not token_present:
                bad_reasons.append("fcm_token_missing")
        else:
            result["signals"].append("listener_fcm_token_present=unknown")

        receiver = getattr(event_listener, "_receiver", _MISSING)
        if receiver is not _MISSING:
            receiver_present = receiver is not None
            result["listener_receiver_present"] = receiver_present
            result["signals"].append(f"listener_receiver_present={receiver_present}")
            if listener_is_started and not receiver_present:
                bad_reasons.append("fcm_receiver_missing")
            if receiver_present:
                receiver_state = self._receiver_task_state(receiver)
                result["listener_receiver_task_state"] = receiver_state
                result["signals"].append(
                    f"listener_receiver_task_state={receiver_state}"
                )
                if listener_is_started and receiver_state in {
                    "done",
                    "cancelled",
                    "not_running",
                    "stopped",
                }:
                    bad_reasons.append(f"fcm_receiver_{receiver_state}")
        else:
            result["signals"].append("listener_receiver_present=unknown")

        session_task = getattr(event_listener, "session_refresh_task", _MISSING)
        if session_task is not _MISSING:
            session_state = self._task_state(session_task)
            result["listener_session_task_state"] = session_state
            result["signals"].append(f"listener_session_task_state={session_state}")
            if listener_is_started and session_state in {
                "missing",
                "done",
                "cancelled",
            }:
                bad_reasons.append(f"session_refresh_task_{session_state}")
        else:
            result["signals"].append("listener_session_task_state=unknown")

        callback_registered = self._listener_callback_registered(
            listen_coordinator,
            event_listener,
        )
        result["listener_callback_registered"] = callback_registered
        result["signals"].append(f"listener_callback_registered={callback_registered}")
        if listener_is_started and callback_registered is False:
            bad_reasons.append("notification_callback_missing")

        result["bad_reasons"] = bad_reasons
        result["listener_private_health"] = "bad" if bad_reasons else "ok"
        return result

    @staticmethod
    def _listener_callback_registered(
        listen_coordinator: Any,
        event_listener: Any,
    ) -> bool | None:
        """Return whether HA's Ring listener callback appears registered."""

        listen_callback_id = getattr(
            listen_coordinator,
            "_listen_callback_id",
            _MISSING,
        )
        if listen_callback_id is not _MISSING:
            return listen_callback_id is not None

        callbacks = getattr(event_listener, "_callbacks", _MISSING)
        if callbacks is _MISSING:
            return None

        try:
            return len(callbacks) > 0
        except TypeError:
            return None

    @classmethod
    def _receiver_task_state(cls, receiver: Any) -> str:
        """Return best-effort private FCM receiver task/running state."""

        run_state = getattr(receiver, "run_state", _MISSING)
        if run_state is not _MISSING:
            state_name = getattr(run_state, "name", str(run_state)).lower()
            if "stopped" in state_name or "stopping" in state_name:
                return "stopped"
            if "started" in state_name:
                return "running"

        do_listen = getattr(receiver, "do_listen", _MISSING)
        if isinstance(do_listen, bool) and not do_listen:
            return "stopped"

        tasks = getattr(receiver, "tasks", _MISSING)
        if tasks is not _MISSING:
            try:
                task_states = [cls._task_state(task) for task in tasks]
            except TypeError:
                task_states = []
            if task_states and all(
                state in {"done", "cancelled"} for state in task_states
            ):
                return "done"
            if any(state == "running" for state in task_states):
                return "running"

        for attr_name in (
            "_listen_task",
            "_task",
            "_reader_task",
            "_read_task",
            "_receiver_task",
            "_run_task",
            "_process_task",
            "_connection_task",
        ):
            task = getattr(receiver, attr_name, _MISSING)
            if task is not _MISSING:
                return cls._task_state(task)

        for attr_name in (
            "running",
            "_running",
            "started",
            "_started",
            "is_running",
            "is_started",
            "is_alive",
        ):
            value = getattr(receiver, attr_name, _MISSING)
            if value is _MISSING:
                continue
            try:
                value = value() if callable(value) else value
            except TypeError:
                continue
            if isinstance(value, bool):
                return "running" if value else "not_running"

        return "unknown"

    @staticmethod
    def _task_state(task: Any) -> str:
        """Return a compact state for asyncio-like tasks."""

        if task is None:
            return "missing"

        cancelled = getattr(task, "cancelled", None)
        if callable(cancelled):
            try:
                if cancelled():
                    return "cancelled"
            except Exception:  # noqa: BLE001 - private introspection only
                return "unknown"

        done = getattr(task, "done", None)
        if callable(done):
            try:
                return "done" if done() else "running"
            except Exception:  # noqa: BLE001 - private introspection only
                return "unknown"

        return "unknown"

    def _ensure_ring_subscriptions(
        self,
        ring_entry_id: str,
        runtime_data: Any,
        devices_coordinator: Any,
        listen_coordinator: Any | None,
        subscribe_listener: bool,
    ) -> None:
        """Subscribe to Ring coordinators so this watchdog owns liveness signals."""

        listener_contexts = (
            self._listener_contexts_from_runtime(runtime_data)
            if subscribe_listener and listen_coordinator is not None
            else ()
        )

        if (
            self._subscribed_ring_entry_id == ring_entry_id
            and self._subscribed_runtime_data is runtime_data
            and self._subscribed_devices_coordinator is devices_coordinator
            and self._subscribed_listen_coordinator is (
                listen_coordinator if subscribe_listener else None
            )
            and self._listener_contexts == listener_contexts
        ):
            return

        self._clear_ring_subscriptions()
        self._subscribed_ring_entry_id = ring_entry_id
        self._subscribed_runtime_data = runtime_data
        self._subscribed_devices_coordinator = devices_coordinator
        self._subscribed_listen_coordinator = (
            listen_coordinator if subscribe_listener else None
        )
        self._listener_contexts = listener_contexts

        add_api_listener = getattr(devices_coordinator, "async_add_listener", None)
        if isinstance(add_api_listener, Callable):
            self._remove_api_listener = add_api_listener(
                self._on_ring_api_update,
                context=None,
            )

        if not subscribe_listener or listen_coordinator is None:
            return

        add_listen_listener = getattr(listen_coordinator, "async_add_listener", None)
        if isinstance(add_listen_listener, Callable):
            for context in listener_contexts:
                self._remove_listen_listeners.append(
                    add_listen_listener(
                        self._on_ring_listener_update,
                        context=context,
                    )
                )

    def _clear_ring_subscriptions(self) -> None:
        """Remove subscriptions from Ring coordinators if they exist."""

        removers: list[CALLBACK_TYPE] = []
        removers.extend(self._remove_listen_listeners)
        if self._remove_api_listener is not None:
            removers.append(self._remove_api_listener)

        for remove in removers:
            try:
                remove()
            except Exception:  # noqa: BLE001 - unloading must be best effort
                _LOGGER.debug(
                    "Failed to remove Ring coordinator listener",
                    exc_info=True,
                )

        self._remove_api_listener = None
        self._remove_listen_listeners = []
        self._listener_contexts = ()
        self._subscribed_ring_entry_id = None
        self._subscribed_runtime_data = None
        self._subscribed_devices_coordinator = None
        self._subscribed_listen_coordinator = None

    @callback
    def _on_ring_api_update(self) -> None:
        """Record successful updates emitted by Ring's devices coordinator."""

        coordinator = self._subscribed_devices_coordinator
        if coordinator is None:
            return
        if getattr(coordinator, "last_update_success", None) is True:
            self._api_last_success = dt_util.utcnow()

    @callback
    def _on_ring_listener_update(self) -> None:
        """Receive updates from Ring's listener to keep it owned by this watchdog."""

        _LOGGER.debug("Ring listener callback received by watchdog")

    @staticmethod
    def _listener_contexts_from_runtime(runtime_data: Any) -> tuple[object | None, ...]:
        """Return Ring listener contexts for known devices.

        Ring's listener coordinator routes updates by device_api_id. Subscribing
        per device makes callbacks meaningful for real Ring events, while a
        fallback None context still lets the watchdog own/start the listener when
        devices cannot be introspected.
        """

        devices = getattr(runtime_data, "devices", None)
        all_devices = getattr(devices, "all_devices", None)
        if callable(all_devices):
            try:
                all_devices = all_devices()
            except Exception:  # noqa: BLE001 - best-effort introspection
                all_devices = None

        contexts: list[object] = []
        for device in all_devices or ():
            device_api_id = getattr(device, "device_api_id", None)
            if device_api_id is not None and device_api_id not in contexts:
                contexts.append(device_api_id)

        return tuple(contexts) if contexts else (None,)

    def _snapshot(
        self,
        now: datetime,
        healthy: bool,
        reason: str,
        signals: list[str],
        ring_entry_id: str | None,
        ring_entry_state: str | None,
        result: dict[str, Any] | None = None,
    ) -> HealthData:
        """Build a data snapshot."""

        result = result or {}
        scheduled_reload = bool(result.get("scheduled_reload", False))
        scheduled_reload_interval = result.get("scheduled_reload_interval_seconds")
        next_scheduled_reload = None
        if scheduled_reload and scheduled_reload_interval is not None:
            anchor = self._last_reload or self._setup_time
            next_scheduled_reload = anchor + timedelta(
                seconds=int(scheduled_reload_interval)
            )
        return HealthData(
            healthy=healthy,
            reason=self._truncate_reason(reason),
            connection_signals=signals,
            bad_since=self._bad_since,
            last_check=now,
            last_reload=self._last_reload,
            reload_count=self._reload_count,
            suppressed_reload_count=self._suppressed_reload_count,
            ring_entry_id=ring_entry_id,
            ring_entry_state=ring_entry_state,
            runtime_data_present=bool(result.get("runtime_data_present", False)),
            active_api_probe=bool(result.get("active_api_probe", True)),
            active_probe_interval_seconds=result.get("active_probe_interval_seconds"),
            api_last_probe=self._api_last_probe,
            api_last_success=self._api_last_success,
            api_last_success_age_seconds=result.get("api_last_success_age_seconds"),
            listener_expected=bool(result.get("listener_expected", False)),
            listener_owned=bool(result.get("listener_owned", False)),
            listener_started=result.get("listener_started"),
            listener_count=result.get("listener_count"),
            listener_private_health=result.get("listener_private_health"),
            listener_subscribed=result.get("listener_subscribed"),
            listener_fcm_token_present=result.get("listener_fcm_token_present"),
            listener_receiver_present=result.get("listener_receiver_present"),
            listener_receiver_task_state=result.get("listener_receiver_task_state"),
            listener_session_task_state=result.get("listener_session_task_state"),
            listener_callback_registered=result.get("listener_callback_registered"),
            scheduled_reload=scheduled_reload,
            scheduled_reload_interval_seconds=scheduled_reload_interval,
            next_scheduled_reload=next_scheduled_reload,
        )

    async def _maybe_run_scheduled_reload(
        self,
        now: datetime,
        scheduled_reload: bool,
        scheduled_reload_interval: int,
        cooldown: int,
        max_reloads_per_hour: int,
        ring_entry_id: str | None,
        ring_entry: ConfigEntry | None,
        ring_entry_state: str | None,
        signals: list[str],
        result: dict[str, Any],
        in_startup_grace: bool,
        in_post_reload_grace: bool,
        notify_on_reload: bool,
    ) -> HealthData | None:
        """Reload Ring on a user-configured schedule when the runtime is healthy."""

        if not scheduled_reload:
            return None

        anchor = self._last_reload or self._setup_time
        if self._seconds_since(anchor, now) < scheduled_reload_interval:
            return None

        scheduled_signals = [
            *signals,
            "scheduled_reload=true",
            f"scheduled_reload_interval={scheduled_reload_interval}s",
        ]
        reason = f"scheduled reload interval elapsed: {scheduled_reload_interval}s"

        if ring_entry_id is None or ring_entry is None:
            return None

        if ring_entry_state in BUSY_STATE_NAMES:
            _LOGGER.debug(
                "Scheduled Ring reload skipped because Ring entry is busy: %s",
                ring_entry_state,
            )
            return None

        if in_startup_grace or in_post_reload_grace:
            return None

        if self._last_reload is not None:
            if self._seconds_since(self._last_reload, now) < cooldown:
                return None

        if not self._reload_budget_available(now, max_reloads_per_hour):
            self._suppressed_reload_count += 1
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_RELOAD_LOOP),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_RELOAD_LOOP,
                translation_placeholders={"max_reloads": str(max_reloads_per_hour)},
            )
            _LOGGER.warning(
                "Scheduled Ring reload suppressed because max_reloads_per_hour=%s was reached",
                max_reloads_per_hour,
            )
            return self._snapshot(
                now,
                True,
                "healthy; scheduled reload budget exhausted",
                scheduled_signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        try:
            await self._reload_ring_entry(
                ring_entry_id,
                reason,
                scheduled_signals,
                notify_on_reload,
            )
        except Exception as err:  # noqa: BLE001 - expose reload failure as state
            self._suppressed_reload_count += 1
            _LOGGER.exception("Scheduled Ring config entry reload failed")
            return self._snapshot(
                now,
                True,
                f"healthy; scheduled reload failed: {type(err).__name__}",
                scheduled_signals,
                ring_entry_id,
                ring_entry_state,
                result,
            )

        self._last_reload = now
        self._reload_count += 1
        self._recent_reloads.append(now)
        self._bad_since = None
        self._clear_ring_subscriptions()
        self._reset_api_probe_state()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RELOAD_LOOP))

        ring_entry_after = find_config_entry(self.hass, ring_entry_id)
        ring_entry_state_after = self._entry_state_name(ring_entry_after)
        return self._snapshot(
            now,
            True,
            "healthy; scheduled Ring config entry reloaded",
            scheduled_signals,
            ring_entry_id,
            ring_entry_state_after,
            result,
        )

    def _issue_id(self, base: str) -> str:
        """Return a per-config-entry repair issue id."""

        return f"{base}_{self.entry.entry_id}"

    def _update_issues(
        self,
        reason: str,
        configured_ring_entry_id: str,
        ring_entry_id: str | None,
        healthy: bool,
        suppress_runtime_issue: bool,
    ) -> None:
        """Create or clear repair issues for structural problems.

        Runtime/API/listener degradation is intentionally logged and exposed via
        diagnostic entities only. It is not a Repairs issue, because transient
        Ring/FCM failures are handled by the reload policy and should not spam
        the Home Assistant Repairs UI.
        """

        if ring_entry_id is None:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(ISSUE_RING_ENTRY),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_RING_ENTRY,
                translation_placeholders={"ring_entry_id": configured_ring_entry_id},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RING_ENTRY))

        # Older versions created a warning Repair issue for runtime degradation.
        # Keep deleting it so upgrading clears any already-created issue.
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RING_RUNTIME))

    def _clear_runtime_issues(self) -> None:
        """Clear issues that should disappear after recovery."""

        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RELOAD_LOOP))
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(ISSUE_RING_RUNTIME))

    async def _reload_ring_entry(
        self,
        ring_entry_id: str,
        reason: str,
        signals: list[str],
        notify_on_reload: bool,
    ) -> None:
        """Reload the selected Ring config entry."""

        _LOGGER.warning(
            "Reloading Ring config entry %s due to connection failure: %s",
            ring_entry_id,
            reason,
        )
        self._clear_ring_subscriptions()
        await self.hass.config_entries.async_reload(ring_entry_id)

        if notify_on_reload:
            await self.hass.services.async_call(
                NOTIFY_DOMAIN,
                "create",
                {
                    "title": "Ring Intercom Health",
                    "message": (
                        "Reloaded Ring config entry because the watchdog detected: "
                        + ", ".join(signals)
                    ),
                },
                blocking=False,
            )

    async def async_manual_reload(self) -> None:
        """Manually reload the configured Ring config entry."""

        values = config_values(self.entry)
        configured_ring_entry_id = values[CONF_RING_ENTRY_ID]
        ring_entry_id = resolve_ring_entry_id(self.hass, configured_ring_entry_id)
        if ring_entry_id is None:
            raise HomeAssistantError(
                f"Ring config entry is missing or ambiguous: {configured_ring_entry_id}"
            )

        ring_entry = find_config_entry(self.hass, ring_entry_id)
        ring_entry_state = self._entry_state_name(ring_entry)
        if ring_entry is None:
            raise HomeAssistantError(f"Ring config entry not found: {ring_entry_id}")
        if ring_entry_state in BUSY_STATE_NAMES:
            raise HomeAssistantError(f"Ring config entry is busy: {ring_entry_state}")

        await self._reload_ring_entry(
            ring_entry_id,
            "manual reload requested",
            [f"ring_entry={ring_entry_id}"],
            bool(values[CONF_NOTIFY_ON_RELOAD]),
        )
        now = dt_util.utcnow()
        self._last_reload = now
        self._reload_count += 1
        self._recent_reloads.append(now)
        self._bad_since = None
        self._clear_ring_subscriptions()
        self._reset_api_probe_state()
        await self.async_request_refresh()

    def _reload_budget_available(
        self,
        now: datetime,
        max_reloads_per_hour: int,
    ) -> bool:
        """Return whether another reload is allowed in the rolling hour."""

        cutoff = now - timedelta(hours=1)
        while self._recent_reloads and self._recent_reloads[0] < cutoff:
            self._recent_reloads.popleft()
        return len(self._recent_reloads) < max_reloads_per_hour

    def _log_reason_once(self, reason: str, signals: list[str]) -> None:
        """Log a transition to an unhealthy reason once."""

        if self._last_logged_reason == reason:
            return
        _LOGGER.warning(
            "Ring Intercom Health degraded: %s; signals=%s",
            reason,
            ", ".join(signals) if signals else "none",
        )
        self._last_logged_reason = reason

    @staticmethod
    def _truncate_reason(reason: str) -> str:
        """Keep sensor state values safely below Home Assistant's state limit."""

        if len(reason) <= MAX_REASON_LENGTH:
            return reason
        return f"{reason[: MAX_REASON_LENGTH - 1]}…"

    @staticmethod
    def _seconds_since(start: datetime, end: datetime) -> float:
        """Return seconds between two datetimes."""

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return (end - start).total_seconds()

    @staticmethod
    def _entry_state_name(entry: ConfigEntry | None) -> str | None:
        """Return a safe config entry state name."""

        if entry is None:
            return None
        state = getattr(entry, "state", None)
        if isinstance(state, ConfigEntryState):
            return state.name.lower()
        return str(state) if state is not None else None

    @staticmethod
    def _safe_len(value: Any) -> int | None:
        """Return len(value) when possible."""

        try:
            return len(value) if value is not None else None
        except TypeError:
            return None
