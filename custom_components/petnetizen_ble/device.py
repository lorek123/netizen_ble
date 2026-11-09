"""Netizen BLE device client using petnetizen_feeder library."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.util import dt as dt_util
from petnetizen_feeder import FeederDevice as LibraryFeederDevice
from petnetizen_feeder import FeedSchedule, ModelFeatures, Weekday, model_features

from .const import DEFAULT_VERIFICATION_CODE

_LOGGER = logging.getLogger(__name__)

# Entity/state key -> ModelFeatures field. Keys not listed are always supported.
_FEATURE_FIELDS = {
    "child_lock": "child_lock",
    "prompt_sound": "prompt_sound",
    "led": "indicator_light",
    "auto_lock": "auto_lock",
    "do_not_disturb": "do_not_disturb",
    "dnd_start": "do_not_disturb",
    "dnd_end": "do_not_disturb",
    "atmosphere_light": "atmosphere_light",
    "power_source": "power_source",
    "low_battery": "power_source",
    "battery_level": "battery_percentage",
}
# The app never exposes these for any known model.
_NEVER_ON_KNOWN_MODELS = {"long_ring"}

# Fields the feeder pushes that map 1:1 onto HA state, with their HA type.
_PUSHED_FIELDS = {
    "child_lock": bool,
    "prompt_sound": bool,
    "led": bool,
    "auto_lock": bool,
    "atmosphere_light": bool,
    "long_ring": bool,
    "fault_code": int,
    "power_mode": str,
    "battery_level": int,
}


class NetizenBLEDevice:
    """Wrapper around petnetizen_feeder FeederDevice for Home Assistant."""

    def __init__(
        self,
        address: str,
        verification_code: str = DEFAULT_VERIFICATION_CODE,
        device_type: str | None = None,
        connection_factory: Any = None,
        ble_name: str | None = None,
    ) -> None:
        address = address.upper()
        self._address = (
            address
            if ":" in address
            else ":".join(address[i : i + 2] for i in range(0, min(12, len(address)), 2))
        )
        self._verification_code = verification_code or DEFAULT_VERIFICATION_CODE
        self._device = LibraryFeederDevice(
            self._address,
            self._verification_code,
            device_type=device_type,
            connection_factory=connection_factory,
            clock=dt_util.now,  # HA's time zone, even if the process runs in UTC
        )
        self._ble_name = ble_name
        self._state: dict[str, Any] = {}
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()
        self._optimistic: dict[str, Any] = {}
        # Apply what the feeder pushes right away (e.g. the child lock re-locking
        # itself), instead of waiting for the next poll.
        self._device.add_state_listener(self._on_feeder_state)

    @property
    def address(self) -> str:
        return self._address

    @property
    def verification_rejected(self) -> bool:
        """True if the feeder rejected the verification code on the last connect."""
        return self._device.verification_rejected

    @property
    def is_connected(self) -> bool:
        return self._device.is_connected

    @property
    def name(self) -> str:
        return self._state.get("device_name") or self._address

    @property
    def features(self) -> ModelFeatures | None:
        """Model features from the advertised name, else the reported name; None if unknown."""
        return model_features(self._ble_name) or model_features(self._state.get("device_name"))

    def supports(self, key: str) -> bool:
        """Whether this model has the feature behind an entity/state key (unknown model: all)."""
        features = self.features
        if features is None:
            return True
        if key in _NEVER_ON_KNOWN_MODELS:
            return False
        field = _FEATURE_FIELDS.get(key)
        return field is None or getattr(features, field)

    def get_state(self, key: str, default: Any = None) -> Any:
        if key in self._optimistic:
            return self._optimistic[key]
        return self._state.get(key, default)

    def _on_feeder_state(self, fields: dict[str, Any]) -> None:
        """Merge a notification from the feeder into HA state and tell listeners."""
        changed: dict[str, Any] = {
            key: to_ha(fields[key]) for key, to_ha in _PUSHED_FIELDS.items() if key in fields
        }
        if "feeding_status_text" in fields:
            changed["feeding_status"] = fields["feeding_status_text"].lower()
        if "do_not_disturb" in fields:
            changed["dnd_enabled"] = fields["do_not_disturb"]
            changed["dnd_start"] = fields.get("dnd_start", "22:00")
            changed["dnd_end"] = fields.get("dnd_end", "08:00")
        if "feed_records" in fields and (last := self._device.get_last_feed_result()):
            changed["last_feed_result"] = last
        if not changed:
            return
        self._state.update(changed)
        for key in changed:
            self._optimistic.pop(key, None)  # the feeder's word beats our guess
        self._notify_listeners()

    def snapshot(self) -> dict[str, Any]:
        """Current state with optimistic (just-set) values applied."""
        return {**self._state, **self._optimistic}

    def _notify_listeners(self) -> None:
        state = self.snapshot()
        for cb in self._listeners:
            try:
                cb(state.copy())
            except Exception:
                pass

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    async def connect(self, ble_client=None) -> bool:
        try:
            return await self._device.connect(ble_client=ble_client)
        except Exception as e:
            _LOGGER.debug("Netizen BLE connect error: %s", e)
            return False

    def disconnected_callback(self, client: Any) -> None:
        """Bleak disconnected_callback; logs when the feeder drops the link."""
        self._device.disconnected_callback(client)

    async def async_ensure_connected(self) -> bool:
        """Reconnect if disconnected (delegates to library's ensure_connected)."""
        return await self._device.ensure_connected()

    async def _fetch_device_info(self) -> None:
        """Query device name and firmware version from feeder."""
        try:
            info = await self._device.get_device_info()
            if info.get("device_name"):
                self._state["device_name"] = info["device_name"]
            if info.get("device_version"):
                self._state["device_version"] = info["device_version"]
            self._notify_listeners()
        except Exception as e:
            _LOGGER.debug("get_device_info failed: %s", e)

    async def sync_time(self) -> bool:
        """Sync feeder clock with host time."""
        await self.async_ensure_connected()
        try:
            await self._device.sync_time()
            return True
        except Exception as e:
            _LOGGER.debug("Sync time failed: %s", e)
            return False

    async def disconnect(self) -> None:
        try:
            await self._device.disconnect()
        except Exception:
            pass
        self._state.clear()

    async def trigger_feed(self, portions: int = 1) -> bool:
        await self.async_ensure_connected()
        try:
            return await self._device.feed(portions=min(15, max(1, portions)))
        except Exception as e:
            _LOGGER.debug("Feed failed: %s", e)
            return False

    async def _set_bool_state(self, state_key: str, enabled: bool, setter) -> bool:
        """Ensure-connected wrapper: call setter, update optimistic state on success."""
        await self.async_ensure_connected()
        try:
            ok = await setter
            if ok:
                self._optimistic[state_key] = enabled
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set %s failed: %s", state_key, e)
            return False

    async def set_child_lock(self, locked: bool) -> bool:
        return await self._set_bool_state("child_lock", locked, self._device.set_child_lock(locked))

    async def set_prompt_sound(self, on: bool) -> bool:
        return await self._set_bool_state("prompt_sound", on, self._device.set_sound(on))

    async def set_feed_plan(self, slots: list[dict]) -> bool:
        """Set feed schedule. slots: list of {weekdays, time, portions, enabled}."""
        schedules: list[FeedSchedule] = []
        for s in slots:
            weekdays = s.get("weekdays") or Weekday.ALL_DAYS
            if isinstance(weekdays, str) and weekdays.lower() == "all":
                weekdays = Weekday.ALL_DAYS
            time_str = s.get("time", "08:00")
            portions = min(15, max(1, s.get("portions", 1)))
            enabled = s.get("enabled", True)
            schedules.append(
                FeedSchedule(weekdays=weekdays, time=time_str, portions=portions, enabled=enabled)
            )
        await self.async_ensure_connected()
        try:
            return await self._device.set_schedule(schedules)
        except Exception as e:
            _LOGGER.debug("Set schedule failed: %s", e)
            return False

    async def set_led(self, enabled: bool) -> bool:
        return await self._set_bool_state("led", enabled, self._device.set_led(enabled))

    async def set_auto_lock(self, enabled: bool) -> bool:
        return await self._set_bool_state("auto_lock", enabled, self._device.set_auto_lock(enabled))

    async def set_atmosphere_light(self, enabled: bool) -> bool:
        return await self._set_bool_state(
            "atmosphere_light", enabled, self._device.set_atmosphere_light(enabled)
        )

    async def set_long_ring(self, enabled: bool) -> bool:
        return await self._set_bool_state("long_ring", enabled, self._device.set_long_ring(enabled))

    async def set_do_not_disturb(
        self, enabled: bool, start_time: str = "22:00", end_time: str = "08:00"
    ) -> bool:
        await self.async_ensure_connected()
        try:
            ok = await self._device.set_do_not_disturb(enabled, start_time, end_time)
            if ok:
                self._optimistic["dnd_enabled"] = enabled
                self._optimistic["dnd_start"] = start_time
                self._optimistic["dnd_end"] = end_time
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set DND failed: %s", e)
            return False

    async def query_status(self) -> None:
        """Query schedule and update state."""
        async with self._lock:
            if "device_version" not in self._state:
                await self._fetch_device_info()

            try:
                raw = await self._device.query_schedule()
                # Library returns list of dicts; normalize to feed_plan_slots format
                slots = []
                for item in raw if isinstance(raw, list) else []:
                    if isinstance(item, dict):
                        slots.append(
                            {
                                "weekdays": item.get("weekdays", []),
                                "time": item.get("time", "00:00"),
                                "portions": item.get("portions", 1),
                                "enabled": item.get("enabled", True),
                            }
                        )
                    else:
                        slots.append(
                            {"weekdays": [], "time": "00:00", "portions": 1, "enabled": True}
                        )
                self._state["feed_plan_slots"] = slots
                self._notify_listeners()
            except Exception as e:
                _LOGGER.debug("Query schedule failed: %s", e)

            # Query child lock and prompt sound so switches reflect device state
            if self.supports("child_lock"):
                try:
                    child_lock = await self._device.get_child_lock_status()
                    if child_lock is not None:
                        self._state["child_lock"] = child_lock
                        self._optimistic.pop("child_lock", None)
                except Exception as e:
                    _LOGGER.debug("Query child lock failed: %s", e)
            if self.supports("prompt_sound"):
                try:
                    prompt_sound = await self._device.get_prompt_sound_status()
                    if prompt_sound is not None:
                        self._state["prompt_sound"] = prompt_sound
                        self._optimistic.pop("prompt_sound", None)
                except Exception as e:
                    _LOGGER.debug("Query prompt sound failed: %s", e)

            # Query new state: fault, feeding status, DND, LED, auto_lock, atmosphere_light, long_ring
            try:
                fault = await self._device.get_fault_status()
                if fault is not None:
                    self._state["fault_code"] = fault
            except Exception as e:
                _LOGGER.debug("Query fault status failed: %s", e)
            try:
                feeding = await self._device.get_feeding_status()
                if feeding is not None:
                    self._state["feeding_status"] = feeding
            except Exception as e:
                _LOGGER.debug("Query feeding status failed: %s", e)
            for key, getter in (
                ("led", self._device.get_led_status),
                ("auto_lock", self._device.get_auto_lock_status),
                ("atmosphere_light", self._device.get_atmosphere_light_status),
                ("long_ring", self._device.get_long_ring_status),
            ):
                if not self.supports(key):
                    continue
                try:
                    value = await getter()
                    if value is not None:
                        self._state[key] = value
                        self._optimistic.pop(key, None)
                except Exception as e:
                    _LOGGER.debug("Query %s failed: %s", key, e)

            if self.supports("power_source"):
                try:
                    power = await self._device.get_power_mode()
                    if power is not None:
                        self._state["power_mode"] = power
                except Exception as e:
                    _LOGGER.debug("Query power source failed: %s", e)
            if self.supports("do_not_disturb"):
                try:
                    dnd = await self._device.get_do_not_disturb()
                    if dnd is not None:
                        self._state["dnd_enabled"] = dnd["enabled"]
                        self._state["dnd_start"] = dnd["start_time"]
                        self._state["dnd_end"] = dnd["end_time"]
                        self._optimistic.pop("dnd_enabled", None)
                        self._optimistic.pop("dnd_start", None)
                        self._optimistic.pop("dnd_end", None)
                except Exception as e:
                    _LOGGER.debug("Query DND failed: %s", e)

            if self.supports("battery_level"):
                try:
                    battery = await self._device.get_battery_level()
                    if battery is not None:
                        self._state["battery_level"] = battery
                        self._optimistic.pop("battery_level", None)
                except Exception as e:
                    _LOGGER.debug("Query battery level failed: %s", e)

            if self.device_type == "cp01b":
                try:
                    cp01b = await self._device.get_cp01b_state()
                    self._state.update(cp01b)
                except Exception as e:
                    _LOGGER.debug("Query CP01B state failed: %s", e)

            if self.device_type == "tc02":
                try:
                    tc02 = await self._device.get_tc02_state()
                    self._state.update(tc02)
                except Exception as e:
                    _LOGGER.debug("Query TC02 state failed: %s", e)

            last_feed = self._device.get_last_feed_result()
            if last_feed is not None:
                self._state["last_feed_result"] = last_feed

            self._notify_listeners()

    # ------------------------------------------------------------------
    # CP01B setters
    # ------------------------------------------------------------------

    async def _set_cp01b(self, key: str, coro) -> bool:
        await self.async_ensure_connected()
        try:
            ok = await coro
            if ok:
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set CP01B %s failed: %s", key, e)
            return False

    async def set_cp01b_operation_mode(self, value: int) -> bool:
        return await self._set_cp01b("operation_mode", self._device.set_cp01b_operation_mode(value))

    async def set_cp01b_rotation_mode(self, value: int) -> bool:
        return await self._set_cp01b("rotation_mode", self._device.set_cp01b_rotation_mode(value))

    async def set_cp01b_volume(self, value: int) -> bool:
        return await self._set_cp01b("volume", self._device.set_cp01b_volume(value))

    async def set_cp01b_playback_frequency(self, value: int) -> bool:
        return await self._set_cp01b(
            "playback_frequency", self._device.set_cp01b_playback_frequency(value)
        )

    async def set_cp01b_sound_effect(self, value: int) -> bool:
        return await self._set_cp01b("sound_effect", self._device.set_cp01b_sound_effect(value))

    async def set_cp01b_auto_mode_countdown(self, value: int) -> bool:
        return await self._set_cp01b(
            "auto_mode_countdown", self._device.set_cp01b_auto_mode_countdown(value)
        )

    async def set_cp01b_prompt_sound(self, enabled: bool) -> bool:
        return await self._set_cp01b(
            "cp01b_prompt_sound", self._device.set_cp01b_prompt_sound(enabled)
        )

    async def set_cp01b_fun_mode(self, value: int) -> bool:
        return await self._set_cp01b("fun_mode", self._device.set_cp01b_fun_mode(value))

    # ------------------------------------------------------------------
    # TC02 (Du-TC02 laser cat teaser) setters
    # ------------------------------------------------------------------

    async def _set_tc02(self, key: str, coro) -> bool:
        await self.async_ensure_connected()
        try:
            ok = await coro
            if ok:
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set TC02 %s failed: %s", key, e)
            return False

    async def set_tc02_operation_mode(self, value: int) -> bool:
        return await self._set_tc02(
            "tc02_operation_mode", self._device.set_tc02_operation_mode(value)
        )

    async def set_tc02_rotation_mode(self, value: int) -> bool:
        return await self._set_tc02(
            "tc02_rotation_mode", self._device.set_tc02_rotation_mode(value)
        )

    async def set_tc02_color_rgb(self, r: int, g: int, b: int) -> bool:
        return await self._set_tc02("tc02_color_rgb", self._device.set_tc02_color_rgb(r, g, b))

    async def set_tc02_mood_light_mode(self, value: int) -> bool:
        return await self._set_tc02(
            "tc02_mood_light_mode", self._device.set_tc02_mood_light_mode(value)
        )

    async def set_tc02_led_color(self, value: int) -> bool:
        return await self._set_tc02("tc02_led_color", self._device.set_tc02_led_color(value))

    async def set_tc02_sound_effect(self, value: int) -> bool:
        return await self._set_tc02("tc02_sound_effect", self._device.set_tc02_sound_effect(value))

    async def set_tc02_playback_frequency(self, value: int) -> bool:
        return await self._set_tc02(
            "tc02_playback_frequency", self._device.set_tc02_playback_frequency(value)
        )

    async def set_tc02_volume(self, value: int) -> bool:
        return await self._set_tc02("tc02_volume", self._device.set_tc02_volume(value))

    async def set_tc02_auto_mode_countdown(self, value: int) -> bool:
        return await self._set_tc02(
            "tc02_auto_mode_countdown", self._device.set_tc02_auto_mode_countdown(value)
        )

    @property
    def device_type(self) -> str:
        """Return the protocol-level device type (standard, jk, ali, cp01b, …)."""
        try:
            return self._device._protocol.device_type
        except AttributeError:
            return "standard"
