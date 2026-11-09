"""Coordinator: polling, reconnects and reachability."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from custom_components.petnetizen_ble.coordinator import NetizenBLECoordinator
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> NetizenBLECoordinator:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


async def test_poll_when_connected(
    coordinator: NetizenBLECoordinator, mock_device: MagicMock
) -> None:
    mock_device.query_status.reset_mock()
    await coordinator.async_refresh()
    mock_device.async_ensure_connected.assert_not_called()
    mock_device.query_status.assert_awaited_once()
    assert coordinator.data == mock_device.snapshot.return_value


async def test_reconnect_and_reachability(
    coordinator: NetizenBLECoordinator,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_device.is_connected = False
    mock_device.query_status.reset_mock()

    for _ in range(10):
        await coordinator.async_refresh()
    assert mock_device.async_ensure_connected.await_count == 10
    mock_device.query_status.assert_not_called()
    assert not coordinator.reachable  # after 10 failed polls
    assert caplog.text.count("unreachable for") == 2  # every 5th failure

    async def reconnect() -> bool:
        mock_device.is_connected = True
        return True

    mock_device.async_ensure_connected.side_effect = reconnect
    await coordinator.async_refresh()
    assert coordinator.reachable
    assert "reconnected after 10 failed poll(s)" in caplog.text
    mock_device.query_status.assert_awaited_once()


async def test_reconnect_after_clean_drop(
    coordinator: NetizenBLECoordinator, mock_device: MagicMock
) -> None:
    """A drop that reconnects on the first try leaves the failure count at zero."""
    mock_device.is_connected = False

    async def reconnect() -> bool:
        mock_device.is_connected = True
        return True

    mock_device.async_ensure_connected.side_effect = reconnect
    await coordinator.async_refresh()
    assert coordinator.reachable


async def test_query_failure_keeps_last_state(
    coordinator: NetizenBLECoordinator, mock_device: MagicMock
) -> None:
    mock_device.query_status.side_effect = RuntimeError("link lost")
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == mock_device.snapshot.return_value


async def test_push_updates_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    coordinator: NetizenBLECoordinator,
    mock_device: MagicMock,
) -> None:
    (listener,) = mock_device.subscribe.call_args.args
    listener({"led": True})
    assert coordinator.data == {"led": True}

    unsubscribe = MagicMock()
    coordinator._unsub = unsubscribe
    await hass.config_entries.async_unload(config_entry.entry_id)
    unsubscribe.assert_called_once()
    await coordinator.async_unload()  # second unload is a no-op for the listener
