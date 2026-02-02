"""Netizen BLE button entities (feed now, refresh schedule)."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

_LOGGER = logging.getLogger(__name__)

BUTTONS: list[ButtonEntityDescription] = [
    ButtonEntityDescription(
        key="feed_now",
        translation_key="feed_now",
        icon="mdi:food",
    ),
    ButtonEntityDescription(
        key="query_feed_plan",
        translation_key="query_feed_plan",
        icon="mdi:calendar-refresh",
    ),
    ButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        icon="mdi:clock-sync",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE buttons."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    entities = [NetizenBLEButton(coordinator, device_info, desc) for desc in BUTTONS]
    async_add_entities(entities)


class NetizenBLEButton(CoordinatorEntity[NetizenBLECoordinator], ButtonEntity):
    """Netizen BLE button (feed now / refresh schedule)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: ButtonEntityDescription,
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

    async def async_press(self) -> None:
        if self.entity_description.key == "feed_now":
            portions = getattr(self.coordinator, "_feed_portions", 1) or 1
            await self._device.trigger_feed(portions=portions)
        elif self.entity_description.key == "query_feed_plan":
            await self._device.query_feed_plan()
        elif self.entity_description.key == "sync_time":
            await self._device.sync_time()
        await self.coordinator.async_request_refresh()
