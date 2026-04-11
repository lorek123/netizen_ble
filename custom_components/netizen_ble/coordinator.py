"""Data coordinator for Netizen BLE."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import NetizenBLEDevice

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)
PROXY_RESTART_FAILURE_THRESHOLD = 10
PROXY_RESTART_COOLDOWN_S = 900


class NetizenBLECoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Netizen BLE device state."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: NetizenBLEDevice,
        *,
        proxy_source_mac: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="netizen_ble",
            update_interval=POLL_INTERVAL,
        )
        self._device = device
        self._unsub: CALLBACK_TYPE | None = None
        self._unsub = device.subscribe(self._on_device_state)
        self._feed_portions = 1

        self._proxy_source_mac = proxy_source_mac
        self._consecutive_failures = 0
        self._last_proxy_restart: float | None = None

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
        """Poll device for status, reconnecting first if needed."""
        if not self._device.is_connected:
            await self._device.async_ensure_connected()

            if self._device.is_connected:
                if self._consecutive_failures > 0:
                    _LOGGER.warning(
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
                if self._consecutive_failures >= PROXY_RESTART_FAILURE_THRESHOLD:
                    await self._try_restart_proxy()
        else:
            self._consecutive_failures = 0

        if self._device.is_connected:
            try:
                await self._device.query_status()
            except Exception as e:
                _LOGGER.debug("Netizen query_status failed: %s", e)

        state = getattr(self._device, "_state", {})
        optimistic = getattr(self._device, "_optimistic", {})
        return {**state, **optimistic}

    # ------------------------------------------------------------------
    # BLE proxy auto-recovery
    # ------------------------------------------------------------------

    def _find_proxy_restart_entity(self) -> str | None:
        """Look up the ESPHome restart button for the BLE proxy by MAC.

        ``device_source()`` returns the ESP32's **BLE** MAC, but the HA device
        registry stores the **WiFi** MAC.  On ESP32 the standard allocation is:
        WiFi STA = base, WiFi AP = base+1, BLE = base+2.  We try the reported
        MAC and the two lower offsets so the lookup succeeds regardless of
        which interface MAC the registry recorded.
        """
        if not self._proxy_source_mac:
            return None

        ble_mac = self._proxy_source_mac.lower().replace("-", ":")
        candidates = {ble_mac}
        try:
            parts = ble_mac.split(":")
            last_octet = int(parts[-1], 16)
            for offset in (1, 2):
                derived = parts[:-1] + [f"{(last_octet - offset) & 0xFF:02x}"]
                candidates.add(":".join(derived))
        except (ValueError, IndexError):
            pass

        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        for device in dev_reg.devices.values():
            for _conn_type, conn_id in device.connections:
                if conn_id.lower().replace("-", ":") in candidates:
                    for entity in er.async_entries_for_device(ent_reg, device.id):
                        if (
                            entity.domain == "button"
                            and entity.entity_id.endswith("_restart")
                            and "safe_mode" not in entity.entity_id
                        ):
                            return entity.entity_id
        return None

    async def _try_restart_proxy(self) -> None:
        """Restart the ESP32 BLE proxy when the feeder is persistently unreachable."""
        if not self._proxy_source_mac:
            return
        now = time.monotonic()
        if self._last_proxy_restart and (now - self._last_proxy_restart) < PROXY_RESTART_COOLDOWN_S:
            return

        restart_entity = self._find_proxy_restart_entity()
        if restart_entity:
            _LOGGER.warning(
                "Restarting BLE proxy (%s) via %s to recover feeder %s",
                self._proxy_source_mac,
                restart_entity,
                self._device.address,
            )
            try:
                await self.hass.services.async_call(
                    "button",
                    "press",
                    {"entity_id": restart_entity},
                    blocking=True,
                )
                self._last_proxy_restart = now
            except Exception as exc:
                _LOGGER.warning("Failed to restart BLE proxy: %s", exc)
        else:
            _LOGGER.warning(
                "Feeder %s unreachable — could not find restart button for "
                "proxy %s; add a local Bluetooth adapter or restart the proxy manually",
                self._device.address,
                self._proxy_source_mac,
            )
            self._last_proxy_restart = now

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._device.disconnect()
