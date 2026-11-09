"""Fixtures for Pet Netizen BLE tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from custom_components.petnetizen_ble.const import DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from pytest_homeassistant_custom_component.common import MockConfigEntry

ADDRESS = "E6:C0:07:09:A3:D3"
NAME = "Du-W11B_E6C00709A3D3"
FEEDER_SERVICE_UUID = "0000ae30-0000-1000-8000-00805f9b34fb"


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations: None, mock_bluetooth: None) -> None:
    """Load custom_components and stub out real Bluetooth adapters."""


def service_info(name: str = NAME, address: str = ADDRESS, uuids=None) -> BluetoothServiceInfoBleak:
    """A connectable advertisement from a feeder."""
    uuids = [FEEDER_SERVICE_UUID] if uuids is None else uuids
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        tx_power=None,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        source="local",
        device=BLEDevice(address, name, {}),
        advertisement=adv,
        connectable=True,
        time=0,
        tx_power=None,
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A configured feeder."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS, "device_type": "standard"},
    )


@pytest.fixture
def mock_ble_device() -> Generator[MagicMock]:
    """The feeder as seen by HA's Bluetooth stack."""
    with patch(
        "custom_components.petnetizen_ble.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(ADDRESS, NAME, {}),
    ) as lookup:
        yield lookup


@pytest.fixture
def mock_device() -> Generator[MagicMock]:
    """NetizenBLEDevice with the BLE side replaced; real model-feature logic."""
    from custom_components.petnetizen_ble.device import NetizenBLEDevice

    real = NetizenBLEDevice(ADDRESS, ble_name=NAME)
    device = MagicMock(spec=NetizenBLEDevice)
    device.address = ADDRESS
    device.name = NAME
    device.device_type = "standard"
    device.is_connected = True
    device.features = real.features
    device.supports.side_effect = real.supports
    device.snapshot.return_value = {
        "child_lock": True,
        "prompt_sound": False,
        "led": False,
        "fault_code": 0,
        "feeding_status": "idle",
        "power_mode": "DC Power",
        "device_version": "110",
        "feed_plan_slots": [{"weekdays": ["mon"], "time": "08:00", "portions": 1, "enabled": True}],
    }
    device.get_state.side_effect = lambda key, default=None: device.snapshot.return_value.get(
        key, default
    )
    device.subscribe.return_value = lambda: None
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    device.query_status = AsyncMock()
    device.async_ensure_connected = AsyncMock(return_value=True)
    device.set_feed_plan = AsyncMock(return_value=True)
    with patch("custom_components.petnetizen_ble.connection.NetizenBLEDevice", return_value=device):
        yield device
