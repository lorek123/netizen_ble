"""Netizen BLE number entity (portions for manual feed)."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

_LOGGER = logging.getLogger(__name__)

PORTIONS_DESC = NumberEntityDescription(
    key="portions",
    translation_key="portions",
    icon="mdi:numeric",
    native_min_value=1,
    native_max_value=15,
    native_step=1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE number (portions)."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    entity = NetizenBLENumber(coordinator, device_info, PORTIONS_DESC)
    async_add_entities([entity])


class NetizenBLENumber(CoordinatorEntity[NetizenBLECoordinator], NumberEntity):
    """Portions to use for manual feed (1–15)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_has_entity_name = True
        self._portions = 1

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    @property
    def native_value(self) -> float | None:
        return float(self._portions)

    async def async_set_native_value(self, value: float) -> None:
        self._portions = int(min(15, max(1, round(value))))
        self.coordinator._feed_portions = self._portions  # noqa: SLF001
        self.async_write_ha_state()
