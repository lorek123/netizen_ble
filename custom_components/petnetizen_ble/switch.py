"""Netizen BLE switch entities (feeder settings)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetizenBLEConfigEntry
from .entity import NetizenBLEEntity

SWITCHES: list[SwitchEntityDescription] = [
    SwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="prompt_sound",
        translation_key="prompt_sound",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="led",
        translation_key="led",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="atmosphere_light",
        translation_key="atmosphere_light",
        icon="mdi:lightbulb",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="auto_lock",
        translation_key="auto_lock",
        icon="mdi:lock-clock",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="do_not_disturb",
        translation_key="do_not_disturb",
        icon="mdi:bell-sleep",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="long_ring",
        translation_key="long_ring",
        icon="mdi:bell-ring",
        entity_category=EntityCategory.CONFIG,
    ),
]

CP01B_SWITCHES: list[SwitchEntityDescription] = [
    SwitchEntityDescription(
        key="cp01b_sound",
        translation_key="cp01b_sound",
        icon="mdi:volume-medium",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE switches."""
    coordinator = entry.runtime_data
    device = coordinator.device
    active = [desc for desc in SWITCHES if device.supports(desc.key)]
    if device.device_type == "cp01b":
        active += CP01B_SWITCHES
    async_add_entities(NetizenBLESwitch(coordinator, desc) for desc in active)


class NetizenBLESwitch(NetizenBLEEntity, SwitchEntity):
    """A feeder on/off setting."""

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        if key == "do_not_disturb":
            return data.get("dnd_enabled")
        if key == "cp01b_sound":
            return data.get("cp01b_prompt_sound")
        return data.get(key)

    async def _set_state(self, enabled: bool) -> None:
        key = self.entity_description.key
        if key == "child_lock":
            await self._device.set_child_lock(enabled)
        elif key == "prompt_sound":
            await self._device.set_prompt_sound(enabled)
        elif key == "led":
            await self._device.set_led(enabled)
        elif key == "atmosphere_light":
            await self._device.set_atmosphere_light(enabled)
        elif key == "auto_lock":
            await self._device.set_auto_lock(enabled)
        elif key == "do_not_disturb":
            data = self.coordinator.data or {}
            await self._device.set_do_not_disturb(
                enabled,
                start_time=data.get("dnd_start", "22:00"),
                end_time=data.get("dnd_end", "08:00"),
            )
        elif key == "long_ring":
            await self._device.set_long_ring(enabled)
        elif key == "cp01b_sound":
            await self._device.set_cp01b_prompt_sound(enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_state(True)
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_state(False)
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())
