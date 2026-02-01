"""Netizen BLE switch entities (child lock, prompt sound, manual feed)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

_LOGGER = logging.getLogger(__name__)

SWITCHES: list[SwitchEntityDescription] = [
    SwitchEntityDescription(key="manual_feed", translation_key="manual_feed", icon="mdi:food"),
    SwitchEntityDescription(key="child_lock", translation_key="child_lock", icon="mdi:lock"),
    SwitchEntityDescription(
        key="prompt_sound", translation_key="prompt_sound", icon="mdi:volume-high"
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE switches."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    entities = [
        NetizenBLESwitch(coordinator, device_info, desc, is_feed=(desc.key == "manual_feed"))
        for desc in SWITCHES
    ]
    async_add_entities(entities)


class NetizenBLESwitch(CoordinatorEntity[NetizenBLECoordinator], SwitchEntity):
    """Netizen BLE switch (child lock, prompt sound, or manual feed trigger)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: SwitchEntityDescription,
        *,
        is_feed: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_has_entity_name = True
        self._is_feed = is_feed

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    def _state_key(self) -> str:
        key = self.entity_description.key
        if key == "child_lock":
            return "child_lock"
        if key == "prompt_sound":
            return "prompt_sound"
        return key

    @property
    def is_on(self) -> bool | None:
        if self._is_feed:
            return None  # momentary action
        data = self.coordinator.data or {}
        return data.get(self._state_key())

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._is_feed:
            portions = getattr(self.coordinator, "_feed_portions", 1) or 1
            await self._device.trigger_feed(portions=portions)
            return
        key = self._state_key()
        if key == "child_lock":
            await self._device.set_child_lock(True)
        elif key == "prompt_sound":
            await self._device.set_prompt_sound(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._is_feed:
            return
        key = self._state_key()
        if key == "child_lock":
            await self._device.set_child_lock(False)
        elif key == "prompt_sound":
            await self._device.set_prompt_sound(False)
        await self.coordinator.async_request_refresh()
