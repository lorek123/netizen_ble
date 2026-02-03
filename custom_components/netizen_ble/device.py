"""Netizen BLE device client using petnetizen_feeder library."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from petnetizen_feeder import FeederDevice as LibraryFeederDevice
from petnetizen_feeder import FeedSchedule, Weekday

from .const import DEFAULT_VERIFICATION_CODE

_LOGGER = logging.getLogger(__name__)


class NetizenBLEDevice:
    """Wrapper around petnetizen_feeder FeederDevice for Home Assistant."""

    def __init__(
        self,
        address: str,
        verification_code: str = DEFAULT_VERIFICATION_CODE,
        device_type: str | None = None,
    ) -> None:
        self._address = (
            address.upper()
            if ":" in address
            else ":".join(address[i : i + 2] for i in range(0, min(12, len(address)), 2))
        )
        self._verification_code = verification_code or DEFAULT_VERIFICATION_CODE
        self._device = LibraryFeederDevice(
            self._address,
            self._verification_code,
            device_type=device_type,
        )
        self._state: dict[str, Any] = {}
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()
        # Optimistic state (library doesn't return child_lock/prompt_sound from device)
        self._optimistic: dict[str, Any] = {}

    @property
    def address(self) -> str:
        return self._address

    @property
    def is_connected(self) -> bool:
        return self._device.is_connected

    @property
    def name(self) -> str:
        return self._state.get("device_name") or self._address

    def set_ble_device(self, _ble_device: Any) -> None:
        """No-op: library uses address only."""

    def get_state(self, key: str, default: Any = None) -> Any:
        if key in self._optimistic:
            return self._optimistic[key]
        return self._state.get(key, default)

    def _notify_listeners(self) -> None:
        state = {**self._state, **self._optimistic}
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

    async def connect(self, ble_client: Any = None) -> bool:
        try:
            ok = await self._device.connect(ble_client=ble_client)
            if ok:
                await self._fetch_device_info()
                await self.query_status()
            return ok
        except Exception as e:
            _LOGGER.warning("Netizen BLE connect error: %s", e)
            return False

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
        try:
            await self._device.sync_time()
            return True
        except Exception as e:
            _LOGGER.warning("Sync time failed: %s", e)
            return False

    async def disconnect(self) -> None:
        try:
            await self._device.disconnect()
        except Exception:
            pass
        self._state.clear()

    async def trigger_feed(self, portions: int = 1) -> bool:
        try:
            return await self._device.feed(portions=min(15, max(1, portions)))
        except Exception as e:
            _LOGGER.warning("Feed failed: %s", e)
            return False

    async def set_child_lock(self, locked: bool) -> bool:
        try:
            ok = await self._device.set_child_lock(locked)
            if ok:
                self._optimistic["child_lock"] = locked
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.warning("Set child lock failed: %s", e)
            return False

    async def set_prompt_sound(self, on: bool) -> bool:
        try:
            ok = await self._device.set_sound(on)
            if ok:
                self._optimistic["prompt_sound"] = on
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.warning("Set sound failed: %s", e)
            return False

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
        try:
            return await self._device.set_schedule(schedules)
        except Exception as e:
            _LOGGER.warning("Set schedule failed: %s", e)
            return False

    async def query_status(self) -> None:
        """Query schedule and update state."""
        async with self._lock:
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

    async def query_feed_plan(self) -> bool:
        """Request schedule refresh."""
        await self.query_status()
        return True

    def device_type_hint(self) -> str:
        """This wrapper is feeder-only."""
        return "feeder"
