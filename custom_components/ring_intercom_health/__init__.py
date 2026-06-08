"""Ring Intercom Health custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    AUTO_RING_ENTRY_ID,
    CONF_RING_ENTRY_ID,
    CONF_ATTACH_TO_SOURCE_DEVICE,
    CONF_SOURCE_ENTITY_ID,
    PLATFORMS,
)
from .coordinator import RingIntercomHealthCoordinator
from .models import RingIntercomHealthConfigEntry, RuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingIntercomHealthConfigEntry,
) -> bool:
    """Set up Ring Intercom Health from a config entry."""

    coordinator = RingIntercomHealthCoordinator(hass, entry)
    entry.runtime_data = RuntimeData(coordinator=coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RingIntercomHealthConfigEntry,
) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data.coordinator
        if isinstance(coordinator, RingIntercomHealthCoordinator):
            await coordinator.async_shutdown()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries.

    Older 0.1.x/0.2.0 builds used entity-based configuration keys. Runtime
    health no longer uses entities as anchors, so stale keys are removed and the
    target Ring entry falls back to Auto unless the user already selected a
    Ring config entry explicitly.
    """

    old_entity_keys = {
        "reload_entity",
        "watch_entities",
        "stale_entities",
        "bad_states",
        "stale_after_seconds",
    }

    def clean_mapping(mapping: dict) -> dict:
        cleaned = dict(mapping)
        for key in old_entity_keys:
            cleaned.pop(key, None)
        cleaned.setdefault(CONF_RING_ENTRY_ID, AUTO_RING_ENTRY_ID)
        cleaned.setdefault(CONF_SOURCE_ENTITY_ID, "")
        cleaned.setdefault(CONF_ATTACH_TO_SOURCE_DEVICE, False)
        return cleaned

    new_data = clean_mapping(entry.data)
    new_options = clean_mapping(entry.options)

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options,
        minor_version=7,
    )
    return True
