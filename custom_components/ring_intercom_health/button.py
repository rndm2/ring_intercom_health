"""Buttons for Ring Intercom Health."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RingIntercomHealthCoordinator
from .entity import RingIntercomHealthEntity
from .models import RingIntercomHealthConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingIntercomHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""

    coordinator = entry.runtime_data.coordinator
    if isinstance(coordinator, RingIntercomHealthCoordinator):
        async_add_entities([RingIntercomReloadButton(entry, coordinator)])


class RingIntercomReloadButton(RingIntercomHealthEntity, ButtonEntity):
    """Manual Ring reload config button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reload_ring"

    def __init__(
        self,
        entry: RingIntercomHealthConfigEntry,
        coordinator: RingIntercomHealthCoordinator,
    ) -> None:
        """Initialize the button."""

        super().__init__(entry, coordinator, "reload_ring")

    async def async_press(self) -> None:
        """Reload the configured Ring config entry."""

        await self.coordinator.async_manual_reload()
