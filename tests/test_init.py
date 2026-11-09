"""Setup, unload and entity tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.petnetizen_ble import connection
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import ADDRESS


async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.device is mock_device
    (feeder,) = dr.async_get(hass).async_get_devices(identifiers={("petnetizen_ble", ADDRESS)})
    assert feeder.sw_version == "110"  # firmware lives in device info, not a sensor
    mock_device.connect.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_device.disconnect.assert_awaited()


async def test_entities_follow_model_features(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    """A Du-W11B gets child lock, LED and power source, but no DND or auto lock."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    def entity_id(domain: str, key: str) -> str | None:
        return entity_registry.async_get_entity_id(domain, "petnetizen_ble", f"{ADDRESS}_{key}")

    assert entity_id("switch", "child_lock")
    assert entity_id("switch", "led")
    assert entity_id("sensor", "power_source")
    assert entity_id("switch", "do_not_disturb") is None
    assert entity_id("switch", "auto_lock") is None
    assert entity_id("time", "dnd_start") is None
    assert entity_id("sensor", "battery_level") is None
    # Removed in the core-readiness cleanup.
    assert entity_id("switch", "manual_feed") is None
    assert entity_id("button", "query_feed_plan") is None
    assert entity_id("button", "factory_reset") is None
    assert entity_id("sensor", "fault_status") is None
    assert entity_id("sensor", "firmware_version") is None

    assert hass.states.get(entity_id("switch", "child_lock")).state == "on"
    assert hass.states.get(entity_id("sensor", "power_source")).state == "mains"
    assert hass.states.get(entity_id("binary_sensor", "low_battery")).state == "off"
    assert hass.states.get(entity_id("sensor", "feeding_status")).state == "idle"

    entry = entity_registry.async_get(entity_id("switch", "child_lock"))
    assert entry.entity_category is er.EntityCategory.CONFIG
    assert entity_registry.async_get(entity_id("sensor", "power_source")).entity_category is (
        er.EntityCategory.DIAGNOSTIC
    )


async def test_orphaned_entities_are_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Entries no current entity claims (old versions, unsupported features) go away."""
    config_entry.add_to_hass(hass)
    old_child_lock_sensor = entity_registry.async_get_or_create(
        "binary_sensor", "petnetizen_ble", f"{ADDRESS}_child_lock", config_entry=config_entry
    )
    unsupported_dnd = entity_registry.async_get_or_create(
        "switch", "petnetizen_ble", f"{ADDRESS}_do_not_disturb", config_entry=config_entry
    )
    disabled = entity_registry.async_get_or_create(
        "switch",
        "petnetizen_ble",
        f"{ADDRESS}_long_ring",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(old_child_lock_sensor.entity_id) is None
    assert entity_registry.async_get(unsupported_dnd.entity_id) is None
    assert entity_registry.async_get(disabled.entity_id) is not None  # user's choice kept


async def test_retry_when_feeder_not_seen(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_ble_device.return_value = None
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.connect.assert_not_called()


async def test_retry_when_connect_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.connect.return_value = False
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.disconnect.assert_awaited()  # half-open link released


async def test_connection_factory(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    """The factory handed to the library connects through HA's Bluetooth stack."""
    config_entry.add_to_hass(hass)
    with patch.object(connection, "NetizenBLEDevice", return_value=mock_device) as ctor:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    kwargs = ctor.call_args.kwargs
    assert kwargs["ble_name"] == "Du-W11B_E6C00709A3D3"
    factory = kwargs["connection_factory"]

    client = MagicMock(backend_id="bluez_dbus")
    with patch.object(connection, "establish_connection", AsyncMock(return_value=client)) as est:
        assert await factory() is client
    args, kw = est.call_args
    assert args[1] is mock_ble_device.return_value
    assert kw["disconnected_callback"] is mock_device.disconnected_callback
    assert kw["ble_device_callback"]() is mock_ble_device.return_value

    mock_ble_device.return_value = None
    with pytest.raises(RuntimeError, match="not found"):
        await factory()


async def test_disconnects_on_home_assistant_stop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_device.disconnect.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_device.disconnect.assert_awaited()


async def test_legacy_address_without_colons(
    hass: HomeAssistant, mock_ble_device: MagicMock, mock_device: MagicMock
) -> None:
    """Entries from older versions may store the MAC without separators."""
    entry = MockConfigEntry(
        domain="petnetizen_ble", title="Feeder", unique_id=ADDRESS, data={"address": "e6c00709a3d3"}
    )
    entry.add_to_hass(hass)
    with patch.object(connection, "NetizenBLEDevice", return_value=mock_device) as ctor:
        await hass.config_entries.async_setup(entry.entry_id)
    assert ctor.call_args.args[0] == ADDRESS
