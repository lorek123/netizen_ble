"""Automatic Bluetooth discovery: the manifest matchers must catch real feeders."""

from __future__ import annotations

import pytest
from custom_components.petnetizen_ble.const import DOMAIN
from homeassistant.components.bluetooth.match import ble_device_matches
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_bluetooth

from .conftest import service_info

# Advertisement captured from a Du-W11B (2026-10-25): advertises service 0000af30, not the
# 0000ae30 GATT service it is controlled through, and manufacturer 10794.
W11B_ADVERTISED_UUID = "0000af30-0000-1000-8000-00805f9b34fb"


async def _matches(hass: HomeAssistant, info) -> bool:
    matchers = [m for m in await async_get_bluetooth(hass) if m["domain"] == DOMAIN]
    assert matchers
    return any(ble_device_matches(m, info) for m in matchers)


async def test_real_w11b_advertisement_is_discovered(hass: HomeAssistant) -> None:
    info = service_info(name="Du-W11B_E6C00709A3D3", uuids=[W11B_ADVERTISED_UUID])
    info.manufacturer_data[10794] = bytes.fromhex("0000000001")
    assert await _matches(hass, info)


@pytest.mark.parametrize(
    "name",
    # Every bleName in the app's ble-device-type.json (app 2.3.6).
    [
        "Du-W10B",
        "Du-W11B",
        "Du-W12B",
        "Du-W15B",
        "Du-F03B",
        "Du-F06",
        "Du-F08B",
        "Du-F09B",
        "Du-F16B",
        "Du-TC02",
        "DU-PD01",
        "DU-F14B",
        "DU-CP01B",
    ],
)
async def test_every_app_model_is_discovered_by_name(hass: HomeAssistant, name: str) -> None:
    assert await _matches(hass, service_info(name=f"{name}_AABBCCDDEEFF", uuids=[]))


async def test_unrelated_devices_are_not_discovered(hass: HomeAssistant) -> None:
    assert not await _matches(
        hass, service_info(name="Dummy-Lamp", uuids=["0000fe0d-0000-1000-8000-00805f9b34fb"])
    )
    # Must be connectable: passive-only advertisements are useless to us.
    info = service_info(name="Du-W11B_E6C00709A3D3", uuids=[])
    object.__setattr__(info, "connectable", False)
    assert not await _matches(hass, info)
