"""Binary sensors for Ring Intercom Health."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up binary sensors."""

    coordinator = entry.runtime_data.coordinator
    if isinstance(coordinator, RingIntercomHealthCoordinator):
        async_add_entities([RingIntercomHealthyBinarySensor(entry, coordinator)])


class RingIntercomHealthyBinarySensor(RingIntercomHealthEntity, BinarySensorEntity):
    """Health diagnostic binary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "healthy"

    def __init__(
        self,
        entry: RingIntercomHealthConfigEntry,
        coordinator: RingIntercomHealthCoordinator,
    ) -> None:
        """Initialize the binary sensor."""

        super().__init__(entry, coordinator, "healthy")

    @property
    def is_on(self) -> bool | None:
        """Return whether the watched Ring entities look healthy."""

        if self.coordinator.data is None:
            return None
        return self.coordinator.data.healthy
