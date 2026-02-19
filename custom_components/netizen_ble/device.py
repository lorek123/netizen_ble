"""Netizen BLE device client using petnetizen_feeder library."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak_retry_connector import establish_connection, get_device
from petnetizen_feeder import FeederDevice as LibraryFeederDevice
from petnetizen_feeder import FeedSchedule, Weekday

from .const import DEFAULT_VERIFICATION_CODE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NetizenBLEDevice:
    """Wrapper around petnetizen_feeder FeederDevice for Home Assistant."""

    def __init__(
        self,
        address: str,
        verification_code: str = DEFAULT_VERIFICATION_CODE,
        device_type: str | None = None,
        *,
        hass: HomeAssistant | None = None,
        entry_title: str = "",
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
        self._hass = hass
        self._entry_title = entry_title or self._address
        self._state: dict[str, Any] = {}
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()
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
            _LOGGER.debug("Netizen BLE connect error: %s", e)
            return False

    async def async_ensure_connected(self) -> bool:
        """Reconnect via HA bluetooth + bleak_retry_connector if disconnected."""
        if self._device.is_connected:
            return True

        if self._hass is None:
            _LOGGER.debug("No hass reference, skipping HA-level reconnect")
            return False

        async with self._lock:
            if self._device.is_connected:
                return True

            _LOGGER.info("Feeder %s disconnected, reconnecting via HA bluetooth", self._address)
            try:
                from homeassistant.components import bluetooth

                ble_device = bluetooth.async_ble_device_from_address(
                    self._hass, self._address, True
                ) or await get_device(self._address)

                if not ble_device:
                    _LOGGER.warning("Cannot find BLE device %s for reconnection", self._address)
                    return False

                ble_client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._entry_title,
                )

                ok = await self._device.reconnect(ble_client=ble_client)
                if ok:
                    _LOGGER.info("Reconnected to feeder %s", self._address)
                return ok
            except Exception as e:
                _LOGGER.warning("Reconnection to %s failed: %s", self._address, e)
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

    async def set_child_lock(self, locked: bool) -> bool:
        await self.async_ensure_connected()
        try:
            ok = await self._device.set_child_lock(locked)
            if ok:
                self._optimistic["child_lock"] = locked
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set child lock failed: %s", e)
            return False

    async def set_prompt_sound(self, on: bool) -> bool:
        await self.async_ensure_connected()
        try:
            ok = await self._device.set_sound(on)
            if ok:
                self._optimistic["prompt_sound"] = on
                self._notify_listeners()
            return ok
        except Exception as e:
            _LOGGER.debug("Set sound failed: %s", e)
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
        await self.async_ensure_connected()
        try:
            return await self._device.set_schedule(schedules)
        except Exception as e:
            _LOGGER.debug("Set schedule failed: %s", e)
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

            # Query child lock and prompt sound so switches reflect device state
            try:
                child_lock = await self._device.get_child_lock_status()
                if child_lock is not None:
                    self._state["child_lock"] = child_lock
                    self._optimistic.pop("child_lock", None)
            except Exception as e:
                _LOGGER.debug("Query child lock failed: %s", e)
            try:
                prompt_sound = await self._device.get_prompt_sound_status()
                if prompt_sound is not None:
                    self._state["prompt_sound"] = prompt_sound
                    self._optimistic.pop("prompt_sound", None)
            except Exception as e:
                _LOGGER.debug("Query prompt sound failed: %s", e)
            self._notify_listeners()

    async def query_feed_plan(self) -> bool:
        """Request schedule refresh."""
        await self.query_status()
        return True

    def device_type_hint(self) -> str:
        """This wrapper is feeder-only."""
        return "feeder"
