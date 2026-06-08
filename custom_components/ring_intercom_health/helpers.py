"""Shared helpers for Ring Intercom Health."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

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
    DEFAULT_STARTUP_GRACE_SECONDS,
    RING_DOMAIN,
)


def option(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Return an option value, falling back to entry data and finally a default."""

    if key in entry.options:
        return entry.options[key]
    if key in entry.data:
        return entry.data[key]
    return default


def config_values(entry: ConfigEntry) -> dict[str, Any]:
    """Return the effective user configuration."""

    return {
        CONF_RING_ENTRY_ID: option(entry, CONF_RING_ENTRY_ID, AUTO_RING_ENTRY_ID),
        CONF_SOURCE_ENTITY_ID: option(entry, CONF_SOURCE_ENTITY_ID, ""),
        CONF_ATTACH_TO_SOURCE_DEVICE: bool(
            option(
                entry,
                CONF_ATTACH_TO_SOURCE_DEVICE,
                DEFAULT_ATTACH_TO_SOURCE_DEVICE,
            )
        ),
        CONF_CHECK_INTERVAL_SECONDS: int(
            option(entry, CONF_CHECK_INTERVAL_SECONDS, DEFAULT_CHECK_INTERVAL_SECONDS)
        ),
        CONF_BAD_FOR_SECONDS: int(
            option(entry, CONF_BAD_FOR_SECONDS, DEFAULT_BAD_FOR_SECONDS)
        ),
        CONF_RELOAD_COOLDOWN_SECONDS: int(
            option(entry, CONF_RELOAD_COOLDOWN_SECONDS, DEFAULT_RELOAD_COOLDOWN_SECONDS)
        ),
        CONF_STARTUP_GRACE_SECONDS: int(
            option(entry, CONF_STARTUP_GRACE_SECONDS, DEFAULT_STARTUP_GRACE_SECONDS)
        ),
        CONF_POST_RELOAD_GRACE_SECONDS: int(
            option(
                entry,
                CONF_POST_RELOAD_GRACE_SECONDS,
                DEFAULT_POST_RELOAD_GRACE_SECONDS,
            )
        ),
        CONF_MAX_RELOADS_PER_HOUR: int(
            option(entry, CONF_MAX_RELOADS_PER_HOUR, DEFAULT_MAX_RELOADS_PER_HOUR)
        ),
        CONF_AUTO_RELOAD: bool(option(entry, CONF_AUTO_RELOAD, DEFAULT_AUTO_RELOAD)),
        CONF_NOTIFY_ON_RELOAD: bool(
            option(entry, CONF_NOTIFY_ON_RELOAD, DEFAULT_NOTIFY_ON_RELOAD)
        ),
        CONF_ACTIVE_API_PROBE: bool(
            option(entry, CONF_ACTIVE_API_PROBE, DEFAULT_ACTIVE_API_PROBE)
        ),
        CONF_ACTIVE_PROBE_INTERVAL_SECONDS: int(
            option(
                entry,
                CONF_ACTIVE_PROBE_INTERVAL_SECONDS,
                DEFAULT_ACTIVE_PROBE_INTERVAL_SECONDS,
            )
        ),
        CONF_API_MAX_AGE_SECONDS: int(
            option(entry, CONF_API_MAX_AGE_SECONDS, DEFAULT_API_MAX_AGE_SECONDS)
        ),
        CONF_REQUIRE_LISTENER_STARTED: bool(
            option(
                entry,
                CONF_REQUIRE_LISTENER_STARTED,
                DEFAULT_REQUIRE_LISTENER_STARTED,
            )
        ),
    }


def ring_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return all Ring config entries."""

    return list(hass.config_entries.async_entries(RING_DOMAIN))


def find_config_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry | None:
    """Return a config entry by id."""

    if entry_id is None:
        return None

    for entry in hass.config_entries.async_entries():
        if entry.entry_id == entry_id:
            return entry
    return None


def resolve_ring_entry_id(
    hass: HomeAssistant,
    configured_entry_id: str | None,
) -> str | None:
    """Resolve configured Ring entry id.

    "auto" is valid only when Home Assistant has exactly one Ring config entry.
    With multiple Ring accounts, the user must pick one explicitly. This avoids
    surprising reloads of the wrong Ring account.
    """

    entries = ring_entries(hass)
    if configured_entry_id in (None, "", AUTO_RING_ENTRY_ID):
        return entries[0].entry_id if len(entries) == 1 else None

    entry = find_config_entry(hass, configured_entry_id)
    if entry is None or entry.domain != RING_DOMAIN:
        return None
    return entry.entry_id


def ring_entry_label(entry: ConfigEntry) -> str:
    """Return a readable label for a Ring config entry."""

    title = entry.title or "Ring"
    return f"{title} ({entry.entry_id[:8]})"



def source_entity_device_entry(
    hass: HomeAssistant,
    source_entity_id: str | None,
) -> dr.DeviceEntry | None:
    """Return the device for a source entity, if one exists."""

    if not source_entity_id:
        return None

    entity_entry = er.async_get(hass).async_get(source_entity_id)
    if entity_entry is None or entity_entry.device_id is None:
        return None

    return dr.async_get(hass).async_get(entity_entry.device_id)


def source_entity_belongs_to_ring_entry(
    hass: HomeAssistant,
    source_entity_id: str | None,
    ring_entry_id: str | None,
) -> bool:
    """Return whether the source entity belongs to the selected Ring entry."""

    if not source_entity_id:
        return True
    if ring_entry_id is None:
        return False

    entity_entry = er.async_get(hass).async_get(source_entity_id)
    if entity_entry is None:
        return False

    if entity_entry.config_entry_id == ring_entry_id:
        return True

    if entity_entry.device_id is None:
        return False

    device_entry = dr.async_get(hass).async_get(entity_entry.device_id)
    if device_entry is None:
        return False

    return ring_entry_id in device_entry.config_entries


def source_device_via_identifier(
    hass: HomeAssistant,
    source_entity_id: str | None,
) -> tuple[str, str] | None:
    """Return a stable via_device identifier for the source entity device."""

    device_entry = source_entity_device_entry(hass, source_entity_id)
    if device_entry is None or not device_entry.identifiers:
        return None

    identifiers = sorted(device_entry.identifiers, key=lambda item: (item[0], item[1]))
    domain, identifier = identifiers[0]
    return (str(domain), str(identifier))
