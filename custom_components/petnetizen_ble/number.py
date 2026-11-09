"""Netizen BLE number entities (portions + CP01B/TC02 device DPs)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .entity import NetizenBLEEntity

PORTIONS_DESC = NumberEntityDescription(
    key="portions",
    translation_key="portions",
    icon="mdi:numeric",
    native_min_value=1,
    native_max_value=15,
    native_step=1,
    entity_category=EntityCategory.CONFIG,
)

CP01B_NUMBERS: list[NumberEntityDescription] = [
    NumberEntityDescription(
        key="operation_mode",
        translation_key="operation_mode",
        icon="mdi:sine-wave",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="rotation_mode",
        translation_key="rotation_mode",
        icon="mdi:rotate-3d-variant",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="volume",
        translation_key="volume",
        icon="mdi:volume-high",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key="playback_frequency",
        translation_key="playback_frequency",
        icon="mdi:metronome",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="sound_effect",
        translation_key="sound_effect",
        icon="mdi:music-note",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="auto_mode_countdown",
        translation_key="auto_mode_countdown",
        icon="mdi:timer",
        native_min_value=0,
        native_max_value=60,
        native_step=1,
    ),
    NumberEntityDescription(
        key="fun_mode",
        translation_key="fun_mode",
        icon="mdi:star",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
]


TC02_NUMBERS: list[NumberEntityDescription] = [
    NumberEntityDescription(
        key="tc02_operation_mode",
        translation_key="tc02_operation_mode",
        icon="mdi:sine-wave",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_rotation_mode",
        translation_key="tc02_rotation_mode",
        icon="mdi:rotate-3d-variant",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_mood_light_mode",
        translation_key="tc02_mood_light_mode",
        icon="mdi:lightbulb-on",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_led_color",
        translation_key="tc02_led_color",
        icon="mdi:palette",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_sound_effect",
        translation_key="tc02_sound_effect",
        icon="mdi:music-note",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_playback_frequency",
        translation_key="tc02_playback_frequency",
        icon="mdi:metronome",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_volume",
        translation_key="tc02_volume",
        icon="mdi:volume-high",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key="tc02_auto_countdown_total",
        translation_key="tc02_auto_mode_countdown",
        icon="mdi:timer",
        native_min_value=0,
        native_max_value=60,
        native_step=1,
    ),
    NumberEntityDescription(
        key="tc02_color_r",
        translation_key="tc02_color_r",
        icon="mdi:circle",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_color_g",
        translation_key="tc02_color_g",
        icon="mdi:circle",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="tc02_color_b",
        translation_key="tc02_color_b",
        icon="mdi:circle",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE number entities."""
    coordinator = entry.runtime_data
    device = coordinator.device
    entities: list[NumberEntity] = (
        [] if device.device_type == "tc02" else [NetizenBLENumber(coordinator, PORTIONS_DESC)]
    )

    if device.device_type == "cp01b":
        entities += [NetizenBLEDeviceNumber(coordinator, desc) for desc in CP01B_NUMBERS]

    if device.device_type == "tc02":
        entities += [NetizenBLEDeviceNumber(coordinator, desc) for desc in TC02_NUMBERS]

    async_add_entities(entities)


class NetizenBLENumber(NetizenBLEEntity, NumberEntity):
    """Portions to use for manual feed (1–15)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._portions = 1

    @property
    def native_value(self) -> float | None:
        return float(self._portions)

    async def async_set_native_value(self, value: float) -> None:
        self._portions = int(min(15, max(1, round(value))))
        self.coordinator._feed_portions = self._portions  # noqa: SLF001
        self.async_write_ha_state()


class NetizenBLEDeviceNumber(NetizenBLEEntity, NumberEntity):
    """CP01B data-point number: reads from coordinator data, writes via device setter."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        v = data.get(self.entity_description.key)
        return float(v) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        key = self.entity_description.key
        int_val = int(round(value))
        setter_map: dict[str, Any] = {
            "operation_mode": self._device.set_cp01b_operation_mode,
            "rotation_mode": self._device.set_cp01b_rotation_mode,
            "volume": self._device.set_cp01b_volume,
            "playback_frequency": self._device.set_cp01b_playback_frequency,
            "sound_effect": self._device.set_cp01b_sound_effect,
            "auto_mode_countdown": self._device.set_cp01b_auto_mode_countdown,
            "fun_mode": self._device.set_cp01b_fun_mode,
            "tc02_operation_mode": self._device.set_tc02_operation_mode,
            "tc02_rotation_mode": self._device.set_tc02_rotation_mode,
            "tc02_mood_light_mode": self._device.set_tc02_mood_light_mode,
            "tc02_led_color": self._device.set_tc02_led_color,
            "tc02_sound_effect": self._device.set_tc02_sound_effect,
            "tc02_playback_frequency": self._device.set_tc02_playback_frequency,
            "tc02_volume": self._device.set_tc02_volume,
            "tc02_auto_countdown_total": self._device.set_tc02_auto_mode_countdown,
        }
        if key in ("tc02_color_r", "tc02_color_g", "tc02_color_b"):
            data = self.coordinator.data or {}
            r = int(data.get("tc02_color_r", 0))
            g = int(data.get("tc02_color_g", 0))
            b = int(data.get("tc02_color_b", 0))
            if key == "tc02_color_r":
                r = int_val
            elif key == "tc02_color_g":
                g = int_val
            else:
                b = int_val
            await self._device.set_tc02_color_rgb(r, g, b)
        else:
            setter = setter_map.get(key)
            if setter:
                await setter(int_val)
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())
