"""Build a feeder device that connects through Home Assistant's Bluetooth stack."""

from __future__ import annotations

import logging

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .device import NetizenBLEDevice

_LOGGER = logging.getLogger(__name__)


def create_device(
    hass: HomeAssistant,
    address: str,
    *,
    name: str,
    verification_code: str,
    device_type: str | None,
    ble_name: str | None,
) -> NetizenBLEDevice:
    """Return a NetizenBLEDevice whose connections go through HA's Bluetooth.

    HA picks the connection path itself (by RSSI and slot availability across
    all connectable scanners); the BLEDevice passed here does not pin it to an
    adapter, and there is no supported API that does.
    """

    async def _connect() -> BleakClient:
        ble_device = bluetooth.async_ble_device_from_address(hass, address, True)
        if ble_device is None:
            raise RuntimeError(f"BLE device {address} not found by any scanner")
        client = await establish_connection(
            BleakClient,
            ble_device,
            name,
            disconnected_callback=device.disconnected_callback,
            ble_device_callback=lambda: (
                bluetooth.async_ble_device_from_address(hass, address, True) or ble_device
            ),
        )
        _LOGGER.debug("Connected to feeder %s via %s", address, getattr(client, "backend_id", "?"))
        return client

    device = NetizenBLEDevice(
        address,
        verification_code=verification_code,
        device_type=device_type,
        connection_factory=_connect,
        ble_name=ble_name,
    )
    return device
