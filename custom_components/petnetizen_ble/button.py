"""Netizen BLE button entities (feed now, sync time)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .entity import NetizenBLEEntity

BUTTONS: list[ButtonEntityDescription] = [
    ButtonEntityDescription(
        key="feed_now",
        translation_key="feed_now",
        icon="mdi:food",
    ),
    ButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        icon="mdi:clock-sync",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE buttons."""
    coordinator = entry.runtime_data
    device = coordinator.device
    is_tc02 = device.device_type == "tc02"
    feeder_only = {"feed_now"}
    active = [desc for desc in BUTTONS if not (is_tc02 and desc.key in feeder_only)]
    entities = [NetizenBLEButton(coordinator, desc) for desc in active]
    async_add_entities(entities)


class NetizenBLEButton(NetizenBLEEntity, ButtonEntity):
    """Netizen BLE button (feed now / refresh schedule)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)

    async def async_press(self) -> None:
        if self.entity_description.key == "feed_now":
            portions = getattr(self.coordinator, "_feed_portions", 1) or 1
            await self._device.trigger_feed(portions=portions)
        elif self.entity_description.key == "sync_time":
            await self._device.sync_time()
        # Refresh in background so the button returns immediately; state will update shortly
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())
