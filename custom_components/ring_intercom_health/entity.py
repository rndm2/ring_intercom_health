"""Base entities for Ring Intercom Health."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACTIVE_API_PROBE,
    ATTR_ATTACH_TO_SOURCE_DEVICE,
    ATTR_ACTIVE_PROBE_INTERVAL,
    ATTR_API_LAST_PROBE,
    ATTR_API_LAST_SUCCESS,
    ATTR_API_LAST_SUCCESS_AGE,
    ATTR_AUTO_RELOAD,
    ATTR_BAD_SINCE,
    ATTR_CONNECTION_SIGNALS,
    ATTR_LAST_CHECK,
    ATTR_LAST_RELOAD,
    ATTR_LISTENER_COUNT,
    ATTR_LISTENER_EXPECTED,
    ATTR_LISTENER_OWNED,
    ATTR_LISTENER_STARTED,
    ATTR_REASON,
    ATTR_RELOAD_COUNT,
    ATTR_RING_ENTRY_ID,
    ATTR_RING_ENTRY_STATE,
    ATTR_SOURCE_DEVICE_ID,
    ATTR_SOURCE_ENTITY_ID,
    ATTR_RUNTIME_DATA_PRESENT,
    ATTR_SUPPRESSED_RELOAD_COUNT,
    CONF_ACTIVE_API_PROBE,
    CONF_ATTACH_TO_SOURCE_DEVICE,
    CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
    CONF_AUTO_RELOAD,
    CONF_SOURCE_ENTITY_ID,
    DOMAIN,
)
from .coordinator import RingIntercomHealthCoordinator
from .helpers import (
    config_values,
    source_entity_device_entry,
    source_device_via_identifier,
)
from .models import RingIntercomHealthConfigEntry


class RingIntercomHealthEntity(CoordinatorEntity[RingIntercomHealthCoordinator]):
    """Base entity for Ring Intercom Health."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: RingIntercomHealthConfigEntry,
        coordinator: RingIntercomHealthCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        values = config_values(entry)
        source_entity_id = values.get(CONF_SOURCE_ENTITY_ID) or None
        attach_to_source = bool(values.get(CONF_ATTACH_TO_SOURCE_DEVICE))
        source_device = source_entity_device_entry(
            coordinator.hass, source_entity_id
        )

        if attach_to_source and source_device is not None:
            device_info: DeviceInfo = {}
            if source_device.identifiers:
                device_info["identifiers"] = set(source_device.identifiers)
            if source_device.connections:
                device_info["connections"] = set(source_device.connections)
            if source_device.name_by_user or source_device.name:
                device_info["name"] = source_device.name_by_user or source_device.name
            if source_device.manufacturer:
                device_info["manufacturer"] = source_device.manufacturer
            if source_device.model:
                device_info["model"] = source_device.model
            if (
                not device_info.get("identifiers")
                and not device_info.get("connections")
            ):
                device_info = self._own_device_info(entry, source_entity_id)
        else:
            device_info = self._own_device_info(entry, source_entity_id)

        self._attr_device_info = device_info

    def _own_device_info(
        self,
        entry: RingIntercomHealthConfigEntry,
        source_entity_id: str | None,
    ) -> DeviceInfo:
        """Return device info for the standalone watchdog device."""

        via_device = source_device_via_identifier(
            self.coordinator.hass, source_entity_id
        )
        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Home Assistant",
            "model": "Ring Connection Watchdog",
            "entry_type": DeviceEntryType.SERVICE,
        }
        if via_device is not None:
            device_info["via_device"] = via_device
        return device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return common attributes for debugging."""

        data = self.coordinator.data
        if data is None:
            return {}

        values = config_values(self.entry)
        source_device = source_entity_device_entry(
            self.coordinator.hass,
            values.get(CONF_SOURCE_ENTITY_ID),
        )
        return {
            ATTR_REASON: data.reason,
            ATTR_CONNECTION_SIGNALS: data.connection_signals,
            ATTR_BAD_SINCE: data.bad_since.isoformat() if data.bad_since else None,
            ATTR_LAST_CHECK: data.last_check.isoformat() if data.last_check else None,
            ATTR_LAST_RELOAD: (
                data.last_reload.isoformat() if data.last_reload else None
            ),
            ATTR_RELOAD_COUNT: data.reload_count,
            ATTR_SUPPRESSED_RELOAD_COUNT: data.suppressed_reload_count,
            ATTR_RING_ENTRY_ID: data.ring_entry_id,
            ATTR_RING_ENTRY_STATE: data.ring_entry_state,
            ATTR_SOURCE_ENTITY_ID: values.get(CONF_SOURCE_ENTITY_ID) or None,
            ATTR_ATTACH_TO_SOURCE_DEVICE: values[CONF_ATTACH_TO_SOURCE_DEVICE],
            ATTR_SOURCE_DEVICE_ID: source_device.id if source_device else None,
            ATTR_RUNTIME_DATA_PRESENT: data.runtime_data_present,
            ATTR_API_LAST_PROBE: (
                data.api_last_probe.isoformat() if data.api_last_probe else None
            ),
            ATTR_API_LAST_SUCCESS: (
                data.api_last_success.isoformat() if data.api_last_success else None
            ),
            ATTR_API_LAST_SUCCESS_AGE: data.api_last_success_age_seconds,
            ATTR_LISTENER_EXPECTED: data.listener_expected,
            ATTR_LISTENER_OWNED: data.listener_owned,
            ATTR_LISTENER_STARTED: data.listener_started,
            ATTR_LISTENER_COUNT: data.listener_count,
            ATTR_AUTO_RELOAD: values[CONF_AUTO_RELOAD],
            ATTR_ACTIVE_API_PROBE: values[CONF_ACTIVE_API_PROBE],
            ATTR_ACTIVE_PROBE_INTERVAL: values[CONF_ACTIVE_PROBE_INTERVAL_SECONDS],
        }
