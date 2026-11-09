"""Schedule actions."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from custom_components.petnetizen_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import ADDRESS

EVERY_DAY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
CURRENT = [
    {"weekdays": EVERY_DAY, "time": "08:00", "portions": 1, "enabled": True},
    {"weekdays": ["sat", "sun"], "time": "18:30", "portions": 2, "enabled": True},
]


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> MockConfigEntry:
    mock_device.snapshot.return_value["feed_plan_slots"] = [dict(s) for s in CURRENT]
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def device_id(device_registry: dr.DeviceRegistry, loaded_entry: MockConfigEntry) -> str:
    (device,) = device_registry.async_get_devices(identifiers={(DOMAIN, ADDRESS)})
    return device.id


async def call(hass: HomeAssistant, service: str, **data: Any) -> None:
    await hass.services.async_call(DOMAIN, service, data, blocking=True)


def written(mock_device: MagicMock) -> list[dict]:
    (slots,) = mock_device.set_feed_plan.await_args.args
    return slots


# --- set_feeding ----------------------------------------------------------------


async def test_set_feeding_adds_slot(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock
) -> None:
    await call(
        hass,
        "set_feeding",
        device_id=device_id,
        time="12:15:00",  # what the time selector sends
        weekdays=["FRI", "mon"],
        portions=3,
    )
    assert written(mock_device) == [
        CURRENT[0],
        {"weekdays": ["mon", "fri"], "time": "12:15", "portions": 3, "enabled": True},
        CURRENT[1],
    ]  # sorted by time, weekdays in calendar order


async def test_set_feeding_updates_slot_at_same_time(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock
) -> None:
    await call(hass, "set_feeding", device_id=device_id, time="18:30", enabled=False)
    assert written(mock_device) == [
        CURRENT[0],
        {"weekdays": EVERY_DAY, "time": "18:30", "portions": 1, "enabled": False},
    ]


async def test_set_feeding_limit(
    hass: HomeAssistant, device_id: str, loaded_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    full = [
        {"weekdays": EVERY_DAY, "time": f"{h:02d}:00", "portions": 1, "enabled": True}
        for h in range(10)
    ]
    loaded_entry.runtime_data.async_set_updated_data({"feed_plan_slots": full})
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "set_feeding", device_id=device_id, time="23:00")
    assert err.value.translation_key == "too_many_feedings"
    mock_device.set_feed_plan.assert_not_awaited()

    # Updating an existing slot of a full schedule is fine.
    await call(hass, "set_feeding", device_id=device_id, time="05:00", portions=2)
    assert len(written(mock_device)) == 10


@pytest.mark.parametrize(
    "bad",
    [
        {"portions": 0},
        {"portions": 16},
        {"weekdays": []},
        {"weekdays": ["someday"]},
        {"time": "25:00"},
    ],
)
async def test_set_feeding_validation(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock, bad: dict
) -> None:
    with pytest.raises(vol.Invalid):
        await call(hass, "set_feeding", **{"device_id": device_id, "time": "09:00", **bad})
    mock_device.set_feed_plan.assert_not_awaited()


# --- remove_feeding -------------------------------------------------------------


async def test_remove_feeding(hass: HomeAssistant, device_id: str, mock_device: MagicMock) -> None:
    await call(hass, "remove_feeding", device_id=device_id, time="08:00:00")
    assert written(mock_device) == [CURRENT[1]]


async def test_remove_feeding_not_found(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "remove_feeding", device_id=device_id, time="09:00")
    assert err.value.translation_key == "feeding_not_found"
    assert err.value.translation_placeholders["time"] == "09:00"
    mock_device.set_feed_plan.assert_not_awaited()


# --- set_feeding_schedule / set_feed_plan -----------------------------------------


async def test_set_feeding_schedule(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock
) -> None:
    await call(
        hass,
        "set_feeding_schedule",
        device_id=device_id,
        schedule=[
            {"time": "19:00", "weekdays": ["sun"], "portions": 2},
            {"time": "07:30"},
        ],
    )
    assert written(mock_device) == [
        {"weekdays": EVERY_DAY, "time": "07:30", "portions": 1, "enabled": True},
        {"weekdays": ["sun"], "time": "19:00", "portions": 2, "enabled": True},
    ]


async def test_set_feeding_schedule_rejects_duplicates_and_too_many(
    hass: HomeAssistant, device_id: str, mock_device: MagicMock
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await call(
            hass,
            "set_feeding_schedule",
            device_id=device_id,
            schedule=[{"time": "07:30"}, {"time": "07:30:00", "portions": 2}],
        )
    assert err.value.translation_key == "duplicate_feeding_time"

    with pytest.raises(ServiceValidationError) as err:
        await call(
            hass,
            "set_feeding_schedule",
            device_id=device_id,
            schedule=[{"time": f"{h:02d}:00"} for h in range(11)],
        )
    assert err.value.translation_key == "too_many_feedings"
    mock_device.set_feed_plan.assert_not_awaited()


async def test_set_feed_plan_is_deprecated_alias(
    hass: HomeAssistant,
    device_id: str,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await call(
        hass,
        "set_feed_plan",
        device_id=device_id,
        schedule=[{"weekdays": ["mon", "fri"], "time": "07:30", "portions": 2}],
    )
    assert written(mock_device) == [
        {"weekdays": ["mon", "fri"], "time": "07:30", "portions": 2, "enabled": True}
    ]
    assert "set_feed_plan is deprecated" in caplog.text


# --- shared failure paths -------------------------------------------------------


async def test_write_fails(hass: HomeAssistant, device_id: str, mock_device: MagicMock) -> None:
    mock_device.set_feed_plan.return_value = False
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "set_feeding", device_id=device_id, time="09:00")
    assert err.value.translation_key == "set_feed_plan_failed"


async def test_schedule_read_before_editing(
    hass: HomeAssistant, device_id: str, loaded_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """If the plan was never read, it is refreshed first; edits never start from nothing."""
    coordinator = loaded_entry.runtime_data
    coordinator.async_set_updated_data({})
    mock_device.snapshot.return_value = {"feed_plan_slots": [dict(CURRENT[0])]}
    await call(hass, "set_feeding", device_id=device_id, time="20:00")
    assert [s["time"] for s in written(mock_device)] == ["08:00", "20:00"]

    coordinator.async_set_updated_data({})
    mock_device.snapshot.return_value = {}
    mock_device.set_feed_plan.reset_mock()
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "remove_feeding", device_id=device_id, time="08:00")
    assert err.value.translation_key == "schedule_unknown"
    mock_device.set_feed_plan.assert_not_awaited()


async def test_unknown_device(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "remove_feeding", device_id="nope", time="08:00")
    assert err.value.translation_key == "device_not_found"


async def test_device_of_other_integration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, loaded_entry: MockConfigEntry
) -> None:
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "x")}
    )
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "remove_feeding", device_id=other.id, time="08:00")
    assert err.value.translation_key == "device_not_found"


async def test_entry_not_loaded(
    hass: HomeAssistant, device_id: str, loaded_entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_unload(loaded_entry.entry_id)
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "remove_feeding", device_id=device_id, time="08:00")
    assert err.value.translation_key == "entry_not_loaded"
