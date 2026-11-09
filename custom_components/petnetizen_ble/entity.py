"""Base entity for Pet Netizen BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator


class NetizenBLEEntity(CoordinatorEntity[NetizenBLECoordinator]):
    """Entity bound to one feeder, keyed by address and description key."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetizenBLECoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=coordinator.config_entry.title or self._device.name,
            manufacturer="Pet Netizen",
            model=self._device.get_state("device_name") or "Feeder",
            sw_version=self._device.get_state("device_version"),
        )

    @property
    def available(self) -> bool:
        """Stay available through short outages; see coordinator.reachable."""
        return self.coordinator.reachable
