"""Data coordinator for Netizen BLE."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import NetizenBLEDevice

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)

type NetizenBLEConfigEntry = ConfigEntry[NetizenBLECoordinator]


class NetizenBLECoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Netizen BLE device state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NetizenBLEConfigEntry,
        device: NetizenBLEDevice,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="petnetizen_ble",
            update_interval=POLL_INTERVAL,
        )
        self._device = device
        self._unsub: CALLBACK_TYPE | None = None
        self._unsub = device.subscribe(self._on_device_state)
        self._feed_portions = 1
        self._consecutive_failures = 0

    @property
    def device(self) -> NetizenBLEDevice:
        return self._device

    @property
    def reachable(self) -> bool:
        """True until the feeder has been consistently unreachable across multiple polls."""
        return self._consecutive_failures < 10

    @callback
    def _on_device_state(self, state: dict[str, Any]) -> None:
        self.async_set_updated_data(state)

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll device for status, reconnecting first if needed."""
        if not self._device.is_connected:
            await self._device.async_ensure_connected()

            if self._device.is_connected:
                if self._consecutive_failures > 0:
                    _LOGGER.info(
                        "Feeder %s reconnected after %d failed poll(s)",
                        self._device.address,
                        self._consecutive_failures,
                    )
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures % 5 == 0:
                    _LOGGER.warning(
                        "Feeder %s unreachable for %d consecutive polls (~%d min)",
                        self._device.address,
                        self._consecutive_failures,
                        self._consecutive_failures,
                    )
        else:
            self._consecutive_failures = 0

        if self._device.is_connected:
            try:
                await self._device.query_status()
            except Exception as e:
                _LOGGER.debug("Netizen query_status failed: %s", e)

        return self._device.snapshot()

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._device.disconnect()
