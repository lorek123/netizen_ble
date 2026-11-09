"""Netizen BLE binary sensor entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from petnetizen_feeder import decode_fault_flags

from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .entity import NetizenBLEEntity

BINARY_SENSORS: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key="fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
]

# Individual FAULT (0A) bits; feeders only.
FEEDER_PROBLEM_SENSORS: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key="stuck_grain",
        translation_key="stuck_grain",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="food_blocked",
        translation_key="food_blocked",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="out_of_food",
        translation_key="out_of_food",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE binary sensors."""
    coordinator = entry.runtime_data
    device = coordinator.device
    active = list(BINARY_SENSORS)
    if device.device_type not in ("tc02", "cp01b"):
        active += FEEDER_PROBLEM_SENSORS
    entities = [
        NetizenBLEBinarySensor(coordinator, desc) for desc in active if device.supports(desc.key)
    ]
    async_add_entities(entities)


class NetizenBLEBinarySensor(NetizenBLEEntity, BinarySensorEntity):
    """Netizen BLE binary sensor."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        code = data.get("fault_code")
        if code is None:
            return None
        if key == "fault":
            return code != 0
        flags = decode_fault_flags(code)
        if key == "low_battery":
            # The app only trusts this bit while the feeder runs on batteries.
            return flags["low_battery"] and data.get("power_mode") != "DC Power"
        return flags.get(key)
