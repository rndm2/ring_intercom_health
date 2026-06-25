"""Config flow for Ring Intercom Health."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    AUTO_RING_ENTRY_ID,
    CONF_ACTIVE_API_PROBE,
    CONF_ATTACH_TO_SOURCE_DEVICE,
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
    CONF_SOURCE_ENTITY_ID,
    CONF_STARTUP_GRACE_SECONDS,
    DEFAULT_ACTIVE_API_PROBE,
    DEFAULT_ATTACH_TO_SOURCE_DEVICE,
    DEFAULT_ACTIVE_PROBE_INTERVAL_SECONDS,
    DEFAULT_API_MAX_AGE_SECONDS,
    DEFAULT_AUTO_RELOAD,
    DEFAULT_BAD_FOR_SECONDS,
    DEFAULT_CHECK_INTERVAL_SECONDS,
    DEFAULT_MAX_RELOADS_PER_HOUR,
    DEFAULT_NOTIFY_ON_RELOAD,
    DEFAULT_POST_RELOAD_GRACE_SECONDS,
    DEFAULT_RELOAD_COOLDOWN_SECONDS,
    DEFAULT_REQUIRE_LISTENER_STARTED,
    DEFAULT_SCHEDULED_RELOAD,
    DEFAULT_SCHEDULED_RELOAD_INTERVAL_SECONDS,
    DEFAULT_STARTUP_GRACE_SECONDS,
    DOMAIN,
    MAX_MAX_RELOADS_PER_HOUR,
    MAX_SECONDS,
    MIN_API_MAX_AGE_SECONDS,
    MIN_ACTIVE_PROBE_INTERVAL_SECONDS,
    MIN_BAD_FOR_SECONDS,
    MIN_CHECK_INTERVAL_SECONDS,
    MIN_GRACE_SECONDS,
    MIN_MAX_RELOADS_PER_HOUR,
    MIN_RELOAD_COOLDOWN_SECONDS,
    MIN_SCHEDULED_RELOAD_INTERVAL_SECONDS,
    MAX_SCHEDULED_RELOAD_INTERVAL_SECONDS,
)
from .helpers import (
    ring_entries,
    ring_entry_label,
    resolve_ring_entry_id,
    source_entity_belongs_to_ring_entry,
)


def _number_selector(
    min_value: int,
    max_value: int,
    step: int = 1,
) -> selector.NumberSelector:
    """Build a boxed integer selector."""

    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _ring_entry_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Build a Ring config-entry selector.

    Auto is only offered when there is exactly one Ring entry. With multiple Ring
    accounts the user must pick the exact entry, otherwise the watchdog could
    reload the wrong account.
    """

    entries = ring_entries(hass)
    options: list[dict[str, str]] = []

    if len(entries) == 1:
        options.append(
            {
                "value": AUTO_RING_ENTRY_ID,
                "label": "Auto: only Ring config entry",
            }
        )

    options.extend(
        {"value": entry.entry_id, "label": ring_entry_label(entry)}
        for entry in entries
    )

    if not options:
        options.append(
            {
                "value": AUTO_RING_ENTRY_ID,
                "label": "Auto: no Ring config entry found yet",
            }
        )

    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )

def _schema(
    hass: HomeAssistant,
    defaults: dict[str, Any] | None = None,
    include_name: bool = False,
) -> vol.Schema:
    """Build config/options schema."""

    defaults = defaults or {}
    fields: dict[Any, Any] = {}
    entries = ring_entries(hass)
    default_ring_entry_id = defaults.get(CONF_RING_ENTRY_ID)
    if not default_ring_entry_id:
        default_ring_entry_id = (
            AUTO_RING_ENTRY_ID if len(entries) <= 1 else entries[0].entry_id
        )

    if include_name:
        fields[
            vol.Optional(
                CONF_NAME,
                default=defaults.get(CONF_NAME, "Ring Intercom Health"),
            )
        ] = str

    fields.update(
        {
            vol.Required(
                CONF_RING_ENTRY_ID,
                default=default_ring_entry_id,
            ): _ring_entry_selector(hass),
            vol.Optional(
                CONF_SOURCE_ENTITY_ID,
                default=defaults.get(CONF_SOURCE_ENTITY_ID, ""),
            ): selector.EntitySelector(),
            vol.Optional(
                CONF_ATTACH_TO_SOURCE_DEVICE,
                default=defaults.get(
                    CONF_ATTACH_TO_SOURCE_DEVICE,
                    DEFAULT_ATTACH_TO_SOURCE_DEVICE,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ACTIVE_API_PROBE,
                default=defaults.get(CONF_ACTIVE_API_PROBE, DEFAULT_ACTIVE_API_PROBE),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
                default=defaults.get(
                    CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
                    DEFAULT_ACTIVE_PROBE_INTERVAL_SECONDS,
                ),
            ): _number_selector(
                MIN_ACTIVE_PROBE_INTERVAL_SECONDS,
                MAX_SECONDS,
                10,
            ),
            vol.Optional(
                CONF_API_MAX_AGE_SECONDS,
                default=defaults.get(
                    CONF_API_MAX_AGE_SECONDS,
                    DEFAULT_API_MAX_AGE_SECONDS,
                ),
            ): _number_selector(MIN_API_MAX_AGE_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_REQUIRE_LISTENER_STARTED,
                default=defaults.get(
                    CONF_REQUIRE_LISTENER_STARTED,
                    DEFAULT_REQUIRE_LISTENER_STARTED,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CHECK_INTERVAL_SECONDS,
                default=defaults.get(
                    CONF_CHECK_INTERVAL_SECONDS,
                    DEFAULT_CHECK_INTERVAL_SECONDS,
                ),
            ): _number_selector(MIN_CHECK_INTERVAL_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_BAD_FOR_SECONDS,
                default=defaults.get(CONF_BAD_FOR_SECONDS, DEFAULT_BAD_FOR_SECONDS),
            ): _number_selector(MIN_BAD_FOR_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_RELOAD_COOLDOWN_SECONDS,
                default=defaults.get(
                    CONF_RELOAD_COOLDOWN_SECONDS,
                    DEFAULT_RELOAD_COOLDOWN_SECONDS,
                ),
            ): _number_selector(MIN_RELOAD_COOLDOWN_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_STARTUP_GRACE_SECONDS,
                default=defaults.get(
                    CONF_STARTUP_GRACE_SECONDS,
                    DEFAULT_STARTUP_GRACE_SECONDS,
                ),
            ): _number_selector(MIN_GRACE_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_POST_RELOAD_GRACE_SECONDS,
                default=defaults.get(
                    CONF_POST_RELOAD_GRACE_SECONDS,
                    DEFAULT_POST_RELOAD_GRACE_SECONDS,
                ),
            ): _number_selector(MIN_GRACE_SECONDS, MAX_SECONDS, 10),
            vol.Optional(
                CONF_MAX_RELOADS_PER_HOUR,
                default=defaults.get(
                    CONF_MAX_RELOADS_PER_HOUR,
                    DEFAULT_MAX_RELOADS_PER_HOUR,
                ),
            ): _number_selector(MIN_MAX_RELOADS_PER_HOUR, MAX_MAX_RELOADS_PER_HOUR),
            vol.Optional(
                CONF_AUTO_RELOAD,
                default=defaults.get(CONF_AUTO_RELOAD, DEFAULT_AUTO_RELOAD),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_RELOAD,
                default=defaults.get(CONF_NOTIFY_ON_RELOAD, DEFAULT_NOTIFY_ON_RELOAD),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SCHEDULED_RELOAD,
                default=defaults.get(
                    CONF_SCHEDULED_RELOAD,
                    DEFAULT_SCHEDULED_RELOAD,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS,
                default=defaults.get(
                    CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS,
                    DEFAULT_SCHEDULED_RELOAD_INTERVAL_SECONDS,
                ),
            ): _number_selector(
                MIN_SCHEDULED_RELOAD_INTERVAL_SECONDS,
                MAX_SCHEDULED_RELOAD_INTERVAL_SECONDS,
                300,
            ),
        }
    )

    return vol.Schema(fields)


def _coerce_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize data returned by the selectors."""

    data = dict(user_input)

    for key in (
        CONF_CHECK_INTERVAL_SECONDS,
        CONF_BAD_FOR_SECONDS,
        CONF_RELOAD_COOLDOWN_SECONDS,
        CONF_STARTUP_GRACE_SECONDS,
        CONF_POST_RELOAD_GRACE_SECONDS,
        CONF_MAX_RELOADS_PER_HOUR,
        CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
        CONF_API_MAX_AGE_SECONDS,
        CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS,
    ):
        data[key] = int(data[key])

    data[CONF_AUTO_RELOAD] = bool(data.get(CONF_AUTO_RELOAD, DEFAULT_AUTO_RELOAD))
    data[CONF_NOTIFY_ON_RELOAD] = bool(
        data.get(CONF_NOTIFY_ON_RELOAD, DEFAULT_NOTIFY_ON_RELOAD)
    )
    data[CONF_SCHEDULED_RELOAD] = bool(
        data.get(CONF_SCHEDULED_RELOAD, DEFAULT_SCHEDULED_RELOAD)
    )
    data[CONF_ATTACH_TO_SOURCE_DEVICE] = bool(
        data.get(CONF_ATTACH_TO_SOURCE_DEVICE, DEFAULT_ATTACH_TO_SOURCE_DEVICE)
    )
    data[CONF_ACTIVE_API_PROBE] = bool(
        data.get(CONF_ACTIVE_API_PROBE, DEFAULT_ACTIVE_API_PROBE)
    )
    data[CONF_REQUIRE_LISTENER_STARTED] = bool(
        data.get(CONF_REQUIRE_LISTENER_STARTED, DEFAULT_REQUIRE_LISTENER_STARTED)
    )
    data[CONF_RING_ENTRY_ID] = str(data.get(CONF_RING_ENTRY_ID, AUTO_RING_ENTRY_ID))
    data[CONF_SOURCE_ENTITY_ID] = str(data.get(CONF_SOURCE_ENTITY_ID) or "")
    return data


def _target_unique_id(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Return a stable unique id for the selected Ring config entry."""

    ring_entry_id = resolve_ring_entry_id(hass, data.get(CONF_RING_ENTRY_ID))
    return f"ring:{ring_entry_id}" if ring_entry_id is not None else None


def _is_duplicate_target(
    hass: HomeAssistant,
    data: dict[str, Any],
    current_entry_id: str | None = None,
) -> bool:
    """Return whether another watchdog already targets the same Ring entry."""

    target = _target_unique_id(hass, data)
    if target is None:
        return False

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == current_entry_id:
            continue
        other_data = {**entry.data, **entry.options}
        other_target = _target_unique_id(hass, other_data)
        if other_target == target or entry.unique_id == target:
            return True
    return False


def _validate_user_input(
    hass: HomeAssistant,
    data: dict[str, Any],
    current_entry_id: str | None = None,
) -> dict[str, str]:
    """Validate config/options input and return field errors."""

    errors: dict[str, str] = {}

    ring_entry_id = resolve_ring_entry_id(hass, data.get(CONF_RING_ENTRY_ID))
    if not ring_entries(hass):
        errors[CONF_RING_ENTRY_ID] = "no_ring_entries"
    elif ring_entry_id is None:
        errors[CONF_RING_ENTRY_ID] = "ambiguous_or_invalid_ring_entry"
    elif _is_duplicate_target(hass, data, current_entry_id):
        errors[CONF_RING_ENTRY_ID] = "already_configured"

    source_entity_id = data.get(CONF_SOURCE_ENTITY_ID)
    if source_entity_id and not source_entity_belongs_to_ring_entry(
        hass, source_entity_id, ring_entry_id
    ):
        errors[CONF_SOURCE_ENTITY_ID] = "source_entity_not_ring"
    if data[CONF_ATTACH_TO_SOURCE_DEVICE] and not source_entity_id:
        errors[CONF_SOURCE_ENTITY_ID] = "source_entity_required_for_attach"

    if data[CONF_CHECK_INTERVAL_SECONDS] < MIN_CHECK_INTERVAL_SECONDS:
        errors[CONF_CHECK_INTERVAL_SECONDS] = "too_low"
    if data[CONF_BAD_FOR_SECONDS] < MIN_BAD_FOR_SECONDS:
        errors[CONF_BAD_FOR_SECONDS] = "too_low"
    if data[CONF_RELOAD_COOLDOWN_SECONDS] < MIN_RELOAD_COOLDOWN_SECONDS:
        errors[CONF_RELOAD_COOLDOWN_SECONDS] = "too_low"
    if data[CONF_API_MAX_AGE_SECONDS] < MIN_API_MAX_AGE_SECONDS:
        errors[CONF_API_MAX_AGE_SECONDS] = "too_low"
    if data[CONF_ACTIVE_PROBE_INTERVAL_SECONDS] < MIN_ACTIVE_PROBE_INTERVAL_SECONDS:
        errors[CONF_ACTIVE_PROBE_INTERVAL_SECONDS] = "too_low"
    if data[CONF_SCHEDULED_RELOAD]:
        if (
            data[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS]
            < MIN_SCHEDULED_RELOAD_INTERVAL_SECONDS
        ):
            errors[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS] = "too_low"
        elif (
            data[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS]
            > MAX_SCHEDULED_RELOAD_INTERVAL_SECONDS
        ):
            errors[CONF_SCHEDULED_RELOAD_INTERVAL_SECONDS] = "too_high"
    if data[CONF_RELOAD_COOLDOWN_SECONDS] < data[CONF_BAD_FOR_SECONDS]:
        errors[CONF_RELOAD_COOLDOWN_SECONDS] = "cooldown_less_than_bad_for"

    min_api_age_for_probe = (
        data[CONF_ACTIVE_PROBE_INTERVAL_SECONDS]
        + data[CONF_CHECK_INTERVAL_SECONDS]
        + 60
    )
    if (
        data[CONF_ACTIVE_API_PROBE]
        and data[CONF_API_MAX_AGE_SECONDS] < min_api_age_for_probe
    ):
        errors[CONF_API_MAX_AGE_SECONDS] = "api_max_age_too_low_for_probe"

    return errors


class RingIntercomHealthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring Intercom Health."""

    VERSION = 1
    MINOR_VERSION = 9

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Create the options flow."""

        return RingIntercomHealthOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        defaults = user_input

        if user_input is not None:
            data = _coerce_user_input(user_input)
            errors = _validate_user_input(self.hass, data)
            if not errors:
                target_unique_id = _target_unique_id(self.hass, data)
                if target_unique_id is not None:
                    await self.async_set_unique_id(target_unique_id)
                    self._abort_if_unique_id_configured()
                title = data.pop(CONF_NAME, "Ring Intercom Health")
                return self.async_create_entry(title=title, data=data)
            defaults = data

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, defaults, include_name=True),
            errors=errors,
        )


class RingIntercomHealthOptionsFlow(OptionsFlowWithReload):
    """Handle options for Ring Intercom Health."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage options."""

        errors: dict[str, str] = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            data = _coerce_user_input(user_input)
            errors = _validate_user_input(
                self.hass,
                data,
                current_entry_id=self.config_entry.entry_id,
            )
            if not errors:
                return self.async_create_entry(data=data)
            defaults = data

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, defaults, include_name=False),
            errors=errors,
        )
