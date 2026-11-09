"""Entity behaviour: actions, values and toy variants."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import ADDRESS


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def eid(hass: HomeAssistant, domain: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, "petnetizen_ble", f"{ADDRESS}_{key}")
    assert entity_id, f"{domain}.{key} not created"
    return entity_id


async def call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data) -> None:
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )


# --- Switches ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "setter"),
    [
        ("child_lock", "set_child_lock"),
        ("prompt_sound", "set_prompt_sound"),
        ("led", "set_led"),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
    key: str,
    setter: str,
) -> None:
    await setup(hass, config_entry)
    entity_id = eid(hass, "switch", key)
    await call(hass, "switch", "turn_on", entity_id)
    getattr(mock_device, setter).assert_awaited_with(True)
    await call(hass, "switch", "turn_off", entity_id)
    getattr(mock_device, setter).assert_awaited_with(False)


@pytest.mark.parametrize(
    ("key", "setter"),
    [
        ("auto_lock", "set_auto_lock"),
        ("atmosphere_light", "set_atmosphere_light"),
        ("long_ring", "set_long_ring"),
    ],
)
async def test_switches_unknown_model(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
    key: str,
    setter: str,
) -> None:
    """Unknown models get every switch."""
    mock_device.supports.side_effect = lambda key: True
    await setup(hass, config_entry)
    await call(hass, "switch", "turn_on", eid(hass, "switch", key))
    getattr(mock_device, setter).assert_awaited_with(True)


async def test_do_not_disturb_switch_and_times(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.supports.side_effect = lambda key: True
    mock_device.snapshot.return_value |= {
        "dnd_enabled": True,
        "dnd_start": "22:00",
        "dnd_end": "07:00",
    }
    await setup(hass, config_entry)

    switch = eid(hass, "switch", "do_not_disturb")
    assert hass.states.get(switch).state == "on"
    await call(hass, "switch", "turn_off", switch)
    mock_device.set_do_not_disturb.assert_awaited_with(False, start_time="22:00", end_time="07:00")

    start, end = eid(hass, "time", "dnd_start"), eid(hass, "time", "dnd_end")
    assert hass.states.get(start).state == "22:00:00"
    await call(hass, "time", "set_value", start, time="21:30")
    mock_device.set_do_not_disturb.assert_awaited_with(
        enabled=True, start_time="21:30", end_time="07:00"
    )
    await call(hass, "time", "set_value", end, time="06:45")
    mock_device.set_do_not_disturb.assert_awaited_with(
        enabled=True, start_time="22:00", end_time="06:45"
    )


async def test_time_entity_bad_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.supports.side_effect = lambda key: True
    mock_device.snapshot.return_value |= {"dnd_start": "garbage"}
    await setup(hass, config_entry)
    assert hass.states.get(eid(hass, "time", "dnd_start")).state == STATE_UNKNOWN
    assert hass.states.get(eid(hass, "time", "dnd_end")).state == STATE_UNKNOWN


# --- Buttons and portions --------------------------------------------------------------


async def test_feed_now_uses_portions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    await setup(hass, config_entry)
    portions = eid(hass, "number", "portions")
    assert hass.states.get(portions).state == "1.0"
    await call(hass, "number", "set_value", portions, value=3)
    assert hass.states.get(portions).state == "3.0"

    await call(hass, "button", "press", eid(hass, "button", "feed_now"))
    mock_device.trigger_feed.assert_awaited_once_with(portions=3)

    await call(hass, "button", "press", eid(hass, "button", "sync_time"))
    mock_device.sync_time.assert_awaited_once()


# --- Sensors -------------------------------------------------------------------


async def test_sensor_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    await hass.config.async_set_time_zone("Europe/Warsaw")
    freezer.move_to(datetime(2026, 11, 9, 21, 0, tzinfo=dt_util.get_default_time_zone()))  # Mon
    mock_device.snapshot.return_value |= {
        "power_mode": "Battery",
        "fault_code": 0x10 | 0x04,  # out of food + low battery
        "feeding_status": "weird",
        "feed_plan_slots": [
            {"weekdays": ["mon"], "time": "08:00", "portions": 1, "enabled": True},  # past
            {"weekdays": ["tue"], "time": "07:30", "portions": 2, "enabled": True},  # next
            {"weekdays": ["mon"], "time": "23:00", "portions": 1, "enabled": False},
            {"weekdays": ["tue"], "time": "bad", "portions": 1, "enabled": True},
        ],
        "last_feed_result": {
            "timestamp": "2026-11-09 20:15:00",
            "portions": 1,
            "status": "Success",
        },
    }
    await setup(hass, config_entry)

    assert hass.states.get(eid(hass, "sensor", "power_source")).state == "battery"
    assert hass.states.get(eid(hass, "sensor", "feeding_status")).state == STATE_UNKNOWN
    plan = hass.states.get(eid(hass, "sensor", "feed_plan"))
    assert plan.state == "4"
    assert len(plan.attributes["slots"]) == 4

    nxt = hass.states.get(eid(hass, "sensor", "next_feeding"))
    assert nxt.state == "2026-11-10T06:30:00+00:00"  # Tue 07:30 local
    assert nxt.attributes["portions"] == 2

    last = hass.states.get(eid(hass, "sensor", "last_feed_time"))
    assert last.state == "2026-11-09T19:15:00+00:00"  # feeder time is local, not UTC
    assert last.attributes["status"] == "Success"

    assert hass.states.get(eid(hass, "binary_sensor", "fault")).state == "on"
    assert hass.states.get(eid(hass, "binary_sensor", "out_of_food")).state == "on"
    assert hass.states.get(eid(hass, "binary_sensor", "stuck_grain")).state == "off"
    assert hass.states.get(eid(hass, "binary_sensor", "low_battery")).state == "on"


async def test_sensor_values_missing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.snapshot.return_value = {"last_feed_result": {"timestamp": "not a time"}}
    await setup(hass, config_entry)
    for key in ("power_source", "feeding_status", "next_feeding", "last_feed_time"):
        assert hass.states.get(eid(hass, "sensor", key)).state == STATE_UNKNOWN, key
    assert hass.states.get(eid(hass, "sensor", "feed_plan")).state == "0"
    assert hass.states.get(eid(hass, "binary_sensor", "fault")).state == STATE_UNKNOWN


async def test_last_feed_without_timestamp(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.snapshot.return_value = {"last_feed_result": {"portions": 1}}
    await setup(hass, config_entry)
    assert hass.states.get(eid(hass, "sensor", "last_feed_time")).state == STATE_UNKNOWN


async def test_battery_percentage_model(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.supports.side_effect = lambda key: True
    mock_device.snapshot.return_value |= {"battery_level": 64}
    await setup(hass, config_entry)
    assert hass.states.get(eid(hass, "sensor", "battery_level")).state == "64"


# --- Toys ------------------------------------------------------------------------


async def test_tc02_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.device_type = "tc02"
    mock_device.snapshot.return_value = {
        "tc02_volume": 40,
        "tc02_color_r": 10,
        "tc02_color_g": 20,
        "tc02_color_b": 30,
        "tc02_auto_countdown_remaining": 5,
    }
    await setup(hass, config_entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("button", "petnetizen_ble", f"{ADDRESS}_feed_now") is None
    assert registry.async_get_entity_id("number", "petnetizen_ble", f"{ADDRESS}_portions") is None
    assert hass.states.get(eid(hass, "sensor", "tc02_auto_countdown_remaining")).state == "5"

    volume = eid(hass, "number", "tc02_volume")
    assert hass.states.get(volume).state == "40.0"
    await call(hass, "number", "set_value", volume, value=55)
    mock_device.set_tc02_volume.assert_awaited_once_with(55)

    # Colour channels are written together.
    await call(hass, "number", "set_value", eid(hass, "number", "tc02_color_g"), value=99)
    mock_device.set_tc02_color_rgb.assert_awaited_once_with(10, 99, 30)
    await call(hass, "number", "set_value", eid(hass, "number", "tc02_color_r"), value=1)
    mock_device.set_tc02_color_rgb.assert_awaited_with(1, 20, 30)
    await call(hass, "number", "set_value", eid(hass, "number", "tc02_color_b"), value=2)
    mock_device.set_tc02_color_rgb.assert_awaited_with(10, 20, 2)


async def test_cp01b_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_device: MagicMock,
) -> None:
    mock_device.device_type = "cp01b"
    mock_device.snapshot.return_value = {"cp01b_prompt_sound": True}
    await setup(hass, config_entry)

    sound = eid(hass, "switch", "cp01b_sound")
    assert hass.states.get(sound).state == "on"
    await call(hass, "switch", "turn_off", sound)
    mock_device.set_cp01b_prompt_sound.assert_awaited_once_with(False)

    volume = eid(hass, "number", "volume")
    assert hass.states.get(volume).state == STATE_UNKNOWN
    await call(hass, "number", "set_value", volume, value=70)
    mock_device.set_cp01b_volume.assert_awaited_once_with(70)
