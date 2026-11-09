"""Netizen BLE time entities (Do Not Disturb start/end)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .entity import NetizenBLEEntity

TIME_ENTITIES: list[TimeEntityDescription] = [
    TimeEntityDescription(
        key="dnd_start",
        translation_key="dnd_start",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-sleep-outline",
    ),
    TimeEntityDescription(
        key="dnd_end",
        translation_key="dnd_end",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE time entities."""
    coordinator = entry.runtime_data
    device = coordinator.device
    async_add_entities(
        [NetizenBLETime(coordinator, desc) for desc in TIME_ENTITIES if device.supports(desc.key)]
    )


class NetizenBLETime(NetizenBLEEntity, TimeEntity):
    """Netizen BLE time entity for DND start/end time."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: TimeEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> time | None:
        data = self.coordinator.data or {}
        time_str = data.get(self.entity_description.key)
        if not time_str:
            return None
        try:
            hour, minute = (int(x) for x in time_str.split(":"))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return None

    async def async_set_value(self, value: time) -> None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        new_time = f"{value.hour:02d}:{value.minute:02d}"
        if key == "dnd_start":
            await self._device.set_do_not_disturb(
                enabled=data.get("dnd_enabled", False),
                start_time=new_time,
                end_time=data.get("dnd_end", "08:00"),
            )
        elif key == "dnd_end":
            await self._device.set_do_not_disturb(
                enabled=data.get("dnd_enabled", False),
                start_time=data.get("dnd_start", "22:00"),
                end_time=new_time,
            )
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())
