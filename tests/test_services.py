"""Action (service) tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from custom_components.petnetizen_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import ADDRESS

SCHEDULE = [{"weekdays": ["mon", "fri"], "time": "07:30", "portions": 2}]


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


def feeder_device_id(device_registry: dr.DeviceRegistry) -> str:
    (device,) = device_registry.async_get_devices(identifiers={(DOMAIN, ADDRESS)})
    return device.id


async def test_set_feed_plan(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    loaded_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_feed_plan",
        {"device_id": feeder_device_id(device_registry), "schedule": SCHEDULE},
        blocking=True,
    )
    mock_device.set_feed_plan.assert_awaited_once_with(
        [{"weekdays": ["mon", "fri"], "time": "07:30", "portions": 2, "enabled": True}]
    )


async def test_set_feed_plan_unknown_device(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_feed_plan",
            {"device_id": "nope", "schedule": SCHEDULE},
            blocking=True,
        )
    assert err.value.translation_key == "device_not_found"


async def test_set_feed_plan_device_of_other_integration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, loaded_entry: MockConfigEntry
) -> None:
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "x")}
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "set_feed_plan", {"device_id": other.id, "schedule": SCHEDULE}, blocking=True
        )
    assert err.value.translation_key == "device_not_found"


async def test_set_feed_plan_entry_not_loaded(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, loaded_entry: MockConfigEntry
) -> None:
    device_id = feeder_device_id(device_registry)
    await hass.config_entries.async_unload(loaded_entry.entry_id)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "set_feed_plan", {"device_id": device_id, "schedule": SCHEDULE}, blocking=True
        )
    assert err.value.translation_key == "entry_not_loaded"


async def test_set_feed_plan_write_fails(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    loaded_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    mock_device.set_feed_plan.return_value = False
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_feed_plan",
            {"device_id": feeder_device_id(device_registry), "schedule": SCHEDULE},
            blocking=True,
        )
    assert err.value.translation_key == "set_feed_plan_failed"
