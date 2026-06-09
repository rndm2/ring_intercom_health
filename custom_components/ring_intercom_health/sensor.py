"""Sensors for Ring Intercom Health."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RingIntercomHealthCoordinator
from .entity import RingIntercomHealthEntity
from .models import HealthData, RingIntercomHealthConfigEntry


@dataclass(frozen=True, kw_only=True)
class RingIntercomHealthSensorDescription(SensorEntityDescription):
    """Sensor description for Ring Intercom Health."""

    value_fn: Callable[[HealthData], Any]


SENSOR_DESCRIPTIONS: tuple[RingIntercomHealthSensorDescription, ...] = (
    RingIntercomHealthSensorDescription(
        key="reason",
        translation_key="reason",
        value_fn=lambda data: data.reason,
    ),
    RingIntercomHealthSensorDescription(
        key="api_last_success_age",
        translation_key="api_last_success_age",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.api_last_success_age_seconds,
    ),
    RingIntercomHealthSensorDescription(
        key="listener_state",
        translation_key="listener_state",
        value_fn=lambda data: (
            "not_required"
            if not data.listener_expected
            else "started"
            if data.listener_started
            else "stopped"
        ),
    ),
    RingIntercomHealthSensorDescription(
        key="listener_owned",
        translation_key="listener_owned",
        value_fn=lambda data: "owned" if data.listener_owned else "not_owned",
    ),
    RingIntercomHealthSensorDescription(
        key="listener_count",
        translation_key="listener_count",
        native_unit_of_measurement="listeners",
        value_fn=lambda data: data.listener_count,
    ),
    RingIntercomHealthSensorDescription(
        key="listener_private_health",
        translation_key="listener_private_health",
        value_fn=lambda data: data.listener_private_health,
    ),
    RingIntercomHealthSensorDescription(
        key="listener_subscribed",
        translation_key="listener_subscribed",
        value_fn=lambda data: (
            None
            if data.listener_subscribed is None
            else "subscribed"
            if data.listener_subscribed
            else "not_subscribed"
        ),
    ),
    RingIntercomHealthSensorDescription(
        key="listener_fcm_token",
        translation_key="listener_fcm_token",
        value_fn=lambda data: (
            None
            if data.listener_fcm_token_present is None
            else "present"
            if data.listener_fcm_token_present
            else "missing"
        ),
    ),
    RingIntercomHealthSensorDescription(
        key="listener_receiver",
        translation_key="listener_receiver",
        value_fn=lambda data: (
            None
            if data.listener_receiver_present is None
            else "present"
            if data.listener_receiver_present
            else "missing"
        ),
    ),
    RingIntercomHealthSensorDescription(
        key="listener_receiver_task",
        translation_key="listener_receiver_task",
        value_fn=lambda data: data.listener_receiver_task_state,
    ),
    RingIntercomHealthSensorDescription(
        key="listener_session_task",
        translation_key="listener_session_task",
        value_fn=lambda data: data.listener_session_task_state,
    ),
    RingIntercomHealthSensorDescription(
        key="listener_callback",
        translation_key="listener_callback",
        value_fn=lambda data: (
            None
            if data.listener_callback_registered is None
            else "registered"
            if data.listener_callback_registered
            else "missing"
        ),
    ),
    RingIntercomHealthSensorDescription(
        key="api_last_probe",
        translation_key="api_last_probe",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.api_last_probe,
    ),
    RingIntercomHealthSensorDescription(
        key="reload_count",
        translation_key="reload_count",
        native_unit_of_measurement="reloads",
        value_fn=lambda data: data.reload_count,
    ),
    RingIntercomHealthSensorDescription(
        key="suppressed_reload_count",
        translation_key="suppressed_reload_count",
        native_unit_of_measurement="reloads",
        value_fn=lambda data: data.suppressed_reload_count,
    ),
    RingIntercomHealthSensorDescription(
        key="last_check",
        translation_key="last_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_check,
    ),
    RingIntercomHealthSensorDescription(
        key="last_reload",
        translation_key="last_reload",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_reload,
    ),
    RingIntercomHealthSensorDescription(
        key="bad_since",
        translation_key="bad_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.bad_since,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingIntercomHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    coordinator = entry.runtime_data.coordinator
    if isinstance(coordinator, RingIntercomHealthCoordinator):
        async_add_entities(
            RingIntercomHealthSensor(entry, coordinator, description)
            for description in SENSOR_DESCRIPTIONS
        )


class RingIntercomHealthSensor(RingIntercomHealthEntity, SensorEntity):
    """Ring Intercom Health diagnostic sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    entity_description: RingIntercomHealthSensorDescription

    def __init__(
        self,
        entry: RingIntercomHealthConfigEntry,
        coordinator: RingIntercomHealthCoordinator,
        description: RingIntercomHealthSensorDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(entry, coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the sensor value."""

        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.value_fn(data)
