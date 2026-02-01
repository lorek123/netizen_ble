"""Netizen BLE sensor entities (feed plan)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="feed_plan",
        translation_key="feed_plan",
        icon="mdi:calendar-clock",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE sensors."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    entities = [NetizenBLESensor(coordinator, device_info, desc) for desc in SENSORS]
    async_add_entities(entities)


class NetizenBLESensor(CoordinatorEntity[NetizenBLECoordinator], SensorEntity):
    """Netizen BLE sensor (feed plan slot count)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> str | int | None:
        data = self.coordinator.data or {}
        if self.entity_description.key == "feed_plan":
            slots = data.get("feed_plan_slots") or []
            return len(slots)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose schedule slots in attributes."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        if self.entity_description.key == "feed_plan" and "feed_plan_slots" in data:
            attrs["slots"] = data["feed_plan_slots"]
        return attrs
