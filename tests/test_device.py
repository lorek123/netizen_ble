"""NetizenBLEDevice: the HA-side wrapper around petnetizen_feeder.FeederDevice."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.petnetizen_ble.device import NetizenBLEDevice

from .conftest import ADDRESS, NAME

LIB_QUERIES = {
    "get_device_info": {"device_name": "Du-W11B", "device_version": "110"},
    "query_schedule": [{"weekdays": ["mon"], "time": "08:00", "portions": 2, "enabled": True}],
    "get_child_lock_status": True,
    "get_prompt_sound_status": False,
    "get_fault_status": 0,
    "get_feeding_status": "idle",
    "get_led_status": True,
    "get_auto_lock_status": False,
    "get_atmosphere_light_status": False,
    "get_long_ring_status": False,
    "get_power_mode": "DC Power",
    "get_do_not_disturb": {"enabled": True, "start_time": "22:00", "end_time": "07:00"},
    "get_battery_level": 80,
    "get_cp01b_state": {"volume": 50},
    "get_tc02_state": {"tc02_volume": 30},
}


@pytest.fixture
def lib() -> Generator[MagicMock]:
    """The library FeederDevice, stubbed."""
    lib = MagicMock()
    lib.is_connected = True
    lib._protocol.device_type = "standard"
    lib.get_last_feed_result.return_value = {"timestamp": "2026-11-09 22:25:42"}
    for name, value in LIB_QUERIES.items():
        setattr(lib, name, AsyncMock(return_value=value))
    for name in (
        "connect",
        "disconnect",
        "ensure_connected",
        "sync_time",
        "feed",
        "set_schedule",
        "set_child_lock",
        "set_sound",
        "set_led",
        "set_auto_lock",
        "set_atmosphere_light",
        "set_long_ring",
        "set_do_not_disturb",
    ):
        setattr(lib, name, AsyncMock(return_value=True))
    with patch("custom_components.petnetizen_ble.device.LibraryFeederDevice", return_value=lib):
        yield lib


def make(ble_name: str | None = NAME, address: str = ADDRESS) -> NetizenBLEDevice:
    return NetizenBLEDevice(address, ble_name=ble_name)


def test_basics(lib: MagicMock) -> None:
    device = make(address="e6c00709a3d3")
    assert device.address == ADDRESS
    assert device.name == ADDRESS  # until the feeder reports its name
    assert device.is_connected is True
    assert device.device_type == "standard"
    device.disconnected_callback("client")
    lib.disconnected_callback.assert_called_once_with("client")
    lib.verification_rejected = True
    assert device.verification_rejected is True


def test_device_type_falls_back_to_standard(lib: MagicMock) -> None:
    del lib._protocol
    assert make().device_type == "standard"


def test_subscribe_and_unsubscribe(lib: MagicMock) -> None:
    device = make()
    seen: list[dict] = []
    unsubscribe = device.subscribe(seen.append)
    device.subscribe(MagicMock(side_effect=RuntimeError))  # a broken listener is isolated
    device._optimistic["led"] = True
    device._notify_listeners()
    assert seen == [{"led": True}]
    unsubscribe()
    unsubscribe()  # idempotent
    device._notify_listeners()
    assert len(seen) == 1


async def test_query_status_fills_state(lib: MagicMock) -> None:
    device = make()
    await device.query_status()
    snapshot = device.snapshot()
    assert snapshot["device_name"] == "Du-W11B"
    assert snapshot["device_version"] == "110"
    assert device.name == "Du-W11B"
    assert snapshot["feed_plan_slots"][0]["portions"] == 2
    assert snapshot["child_lock"] is True
    assert snapshot["led"] is True
    assert snapshot["power_mode"] == "DC Power"
    assert snapshot["last_feed_result"] == {"timestamp": "2026-11-09 22:25:42"}
    # Du-W11B has no DND, auto lock, atmosphere light, long ring or battery %.
    for key in ("dnd_enabled", "auto_lock", "atmosphere_light", "long_ring", "battery_level"):
        assert key not in snapshot
    lib.get_do_not_disturb.assert_not_awaited()

    # Device info is fetched once.
    await device.query_status()
    lib.get_device_info.assert_awaited_once()


async def test_query_status_unknown_model_queries_everything(lib: MagicMock) -> None:
    lib.get_device_info.return_value = {"device_name": "Mystery", "device_version": "1"}
    device = make(ble_name=None)
    await device.query_status()
    snapshot = device.snapshot()
    assert snapshot["dnd_enabled"] is True
    assert snapshot["dnd_start"] == "22:00"
    assert snapshot["battery_level"] == 80
    assert snapshot["auto_lock"] is False


@pytest.mark.parametrize("device_type", ["cp01b", "tc02"])
async def test_query_status_toys(lib: MagicMock, device_type: str) -> None:
    lib._protocol.device_type = device_type
    device = make(ble_name=None)
    await device.query_status()
    expected = {"cp01b": "volume", "tc02": "tc02_volume"}[device_type]
    assert expected in device.snapshot()


async def test_query_status_survives_failures(lib: MagicMock) -> None:
    """Every individual query may fail; the rest still run."""
    for name in LIB_QUERIES:
        getattr(lib, name).side_effect = RuntimeError("link lost")
    lib.get_last_feed_result.return_value = None
    lib._protocol.device_type = "cp01b"
    device = make(ble_name=None)
    await device.query_status()
    assert device.snapshot() == {}

    lib._protocol.device_type = "tc02"
    await device.query_status()
    assert device.snapshot() == {}


async def test_query_status_tolerates_odd_schedule(lib: MagicMock) -> None:
    lib.query_schedule.return_value = [{}, "garbage"]
    device = make()
    await device.query_status()
    assert device.snapshot()["feed_plan_slots"] == [
        {"weekdays": [], "time": "00:00", "portions": 1, "enabled": True},
        {"weekdays": [], "time": "00:00", "portions": 1, "enabled": True},
    ]


async def test_query_status_ignores_missing_values(lib: MagicMock) -> None:
    for name in LIB_QUERIES:
        getattr(lib, name).return_value = None
    lib.get_device_info.return_value = {}
    lib.query_schedule.return_value = None
    device = make(ble_name=None)
    await device.query_status()
    assert device.snapshot() == {
        "feed_plan_slots": [],
        "last_feed_result": lib.get_last_feed_result(),
    }


@pytest.mark.parametrize(
    ("method", "lib_method", "key"),
    [
        ("set_child_lock", "set_child_lock", "child_lock"),
        ("set_prompt_sound", "set_sound", "prompt_sound"),
        ("set_led", "set_led", "led"),
        ("set_auto_lock", "set_auto_lock", "auto_lock"),
        ("set_atmosphere_light", "set_atmosphere_light", "atmosphere_light"),
        ("set_long_ring", "set_long_ring", "long_ring"),
    ],
)
async def test_bool_setters_are_optimistic(
    lib: MagicMock, method: str, lib_method: str, key: str
) -> None:
    device = make()
    assert await getattr(device, method)(True)
    getattr(lib, lib_method).assert_awaited_once_with(True)
    assert device.snapshot()[key] is True
    assert device.get_state(key) is True

    getattr(lib, lib_method).side_effect = RuntimeError("write failed")
    assert await getattr(device, method)(False) is False
    assert device.snapshot()[key] is True  # unchanged on failure


async def test_query_clears_optimistic_value(lib: MagicMock) -> None:
    device = make()
    await device.set_child_lock(False)
    await device.query_status()
    assert device.snapshot()["child_lock"] is True  # the feeder's answer wins


async def test_set_do_not_disturb(lib: MagicMock) -> None:
    device = make()
    assert await device.set_do_not_disturb(True, "21:00", "06:30")
    lib.set_do_not_disturb.assert_awaited_once_with(True, "21:00", "06:30")
    assert device.snapshot()["dnd_start"] == "21:00"

    lib.set_do_not_disturb.side_effect = RuntimeError
    assert await device.set_do_not_disturb(False) is False


async def test_set_feed_plan(lib: MagicMock) -> None:
    device = make()
    assert await device.set_feed_plan(
        [
            {"weekdays": "all", "time": "07:00", "portions": 99},
            {"time": "19:00", "portions": 0, "enabled": False},
        ]
    )
    (schedules,) = lib.set_schedule.await_args.args
    assert [(s.time, s.portions, s.enabled, len(s.weekdays)) for s in schedules] == [
        ("07:00", 15, True, 7),
        ("19:00", 1, False, 7),
    ]
    lib.set_schedule.side_effect = RuntimeError
    assert await device.set_feed_plan([{"time": "07:00"}]) is False


async def test_feed_sync_connect_disconnect(lib: MagicMock) -> None:
    device = make()
    assert await device.trigger_feed(portions=40)
    lib.feed.assert_awaited_once_with(portions=15)
    lib.feed.side_effect = RuntimeError
    assert await device.trigger_feed() is False

    assert await device.sync_time()
    lib.sync_time.side_effect = RuntimeError
    assert await device.sync_time() is False

    assert await device.connect()
    lib.connect.side_effect = RuntimeError
    assert await device.connect() is False

    device._state["led"] = True
    lib.disconnect.side_effect = RuntimeError  # errors on shutdown are ignored
    await device.disconnect()
    assert device.snapshot() == {}


@pytest.mark.parametrize(
    ("method", "lib_method", "args"),
    [
        ("set_cp01b_operation_mode", "set_cp01b_operation_mode", (2,)),
        ("set_cp01b_rotation_mode", "set_cp01b_rotation_mode", (1,)),
        ("set_cp01b_volume", "set_cp01b_volume", (50,)),
        ("set_cp01b_playback_frequency", "set_cp01b_playback_frequency", (3,)),
        ("set_cp01b_sound_effect", "set_cp01b_sound_effect", (4,)),
        ("set_cp01b_auto_mode_countdown", "set_cp01b_auto_mode_countdown", (10,)),
        ("set_cp01b_prompt_sound", "set_cp01b_prompt_sound", (True,)),
        ("set_cp01b_fun_mode", "set_cp01b_fun_mode", (1,)),
        ("set_tc02_operation_mode", "set_tc02_operation_mode", (1,)),
        ("set_tc02_rotation_mode", "set_tc02_rotation_mode", (2,)),
        ("set_tc02_color_rgb", "set_tc02_color_rgb", (1, 2, 3)),
        ("set_tc02_mood_light_mode", "set_tc02_mood_light_mode", (1,)),
        ("set_tc02_led_color", "set_tc02_led_color", (5,)),
        ("set_tc02_sound_effect", "set_tc02_sound_effect", (2,)),
        ("set_tc02_playback_frequency", "set_tc02_playback_frequency", (3,)),
        ("set_tc02_volume", "set_tc02_volume", (40,)),
        ("set_tc02_auto_mode_countdown", "set_tc02_auto_mode_countdown", (15,)),
    ],
)
async def test_toy_setters(lib: MagicMock, method: str, lib_method: str, args: tuple) -> None:
    setattr(lib, lib_method, AsyncMock(return_value=True))
    device = make()
    assert await getattr(device, method)(*args)
    getattr(lib, lib_method).assert_awaited_once_with(*args)

    getattr(lib, lib_method).side_effect = RuntimeError
    assert await getattr(device, method)(*args) is False


async def test_get_state_prefers_optimistic_value(lib: MagicMock) -> None:
    device = make()
    await device.query_status()
    assert device.get_state("led") is True  # confirmed by the feeder
    assert device.get_state("missing", "fallback") == "fallback"
    await device.set_led(False)
    assert device.get_state("led") is False  # just set, not yet confirmed


def pushed(lib: MagicMock):
    """The callback NetizenBLEDevice registered with the library."""
    (listener,) = lib.add_state_listener.call_args.args
    return listener


async def test_pushed_child_lock_overrides_optimistic_unlock(lib: MagicMock) -> None:
    """Du-W11B: unlocking only lasts a few seconds, then the feeder re-locks itself."""
    device = make()
    seen: list[dict] = []
    device.subscribe(seen.append)

    await device.set_child_lock(False)
    assert device.snapshot()["child_lock"] is False

    pushed(lib)({"child_lock": 1, "child_lock_text": "LOCKED"})
    assert device.snapshot()["child_lock"] is True
    assert "child_lock" not in device._optimistic
    assert seen[-1]["child_lock"] is True  # coordinator is told right away


def test_pushed_status_dnd_and_feed_records(lib: MagicMock) -> None:
    device = make()
    push = pushed(lib)
    push({"feeding_status": 2, "feeding_status_text": "Done"})
    push({"do_not_disturb": True, "dnd_start": "21:00", "dnd_end": "06:00"})
    push({"fault_code": 4, "power_mode": "Battery", "led": True})
    lib.get_last_feed_result.return_value = {"timestamp": "2026-11-10 00:00:39"}
    push({"feed_records": [{"timestamp": "2026-11-10 00:00:39"}]})
    assert device.snapshot() == {
        "feeding_status": "done",
        "dnd_enabled": True,
        "dnd_start": "21:00",
        "dnd_end": "06:00",
        "fault_code": 4,
        "power_mode": "Battery",
        "led": True,
        "last_feed_result": {"timestamp": "2026-11-10 00:00:39"},
    }


def test_pushed_fields_without_ha_state_are_ignored(lib: MagicMock) -> None:
    device = make()
    seen: list[dict] = []
    device.subscribe(seen.append)
    pushed(lib)({"verification_response": 1, "verification_success": True})
    lib.get_last_feed_result.return_value = None
    pushed(lib)({"feed_records": []})
    assert device.snapshot() == {}
    assert seen == []


async def test_written_schedule_is_shown_right_away(lib: MagicMock) -> None:
    device = make()
    seen: list[dict] = []
    device.subscribe(seen.append)
    assert await device.set_feed_plan(
        [{"weekdays": ["fri", "mon"], "time": "07:00", "portions": 2, "enabled": True}]
    )
    expected = [{"weekdays": ["mon", "fri"], "time": "07:00", "portions": 2, "enabled": True}]
    assert device.snapshot()["feed_plan_slots"] == expected
    assert seen[-1]["feed_plan_slots"] == expected

    lib.set_schedule.return_value = False
    assert not await device.set_feed_plan([{"time": "09:00"}])
    assert device.snapshot()["feed_plan_slots"] == expected  # unchanged
