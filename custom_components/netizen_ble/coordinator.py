"""Data coordinator for Netizen BLE."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import NetizenBLEDevice

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)


class NetizenBLECoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Netizen BLE device state."""

    def __init__(self, hass: HomeAssistant, device: NetizenBLEDevice) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="netizen_ble",
            update_interval=POLL_INTERVAL,
        )
        self._device = device
        self._unsub: CALLBACK_TYPE | None = None
        self._unsub = device.subscribe(self._on_device_state)
        self._feed_portions = 1  # default portions for Feed now button

    @property
    def device(self) -> NetizenBLEDevice:
        return self._device

    @property
    def connected(self) -> bool:
        return self._device.is_connected

    @callback
    def _on_device_state(self, state: dict[str, Any]) -> None:
        self.async_set_updated_data(state)

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll device for status."""
        try:
            await self._device.query_status()
        except Exception as e:
            _LOGGER.debug("Netizen query_status failed: %s", e)
        await asyncio.sleep(1.0)
        return dict(getattr(self._device, "_state", {}))

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._device.disconnect()
