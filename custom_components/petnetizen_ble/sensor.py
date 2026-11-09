"""Netizen BLE sensor entities (feed plan)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .entity import NetizenBLEEntity

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_source",
        translation_key="power_source",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENUM,
        options=["mains", "battery"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="feed_plan",
        translation_key="feed_plan",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="next_feeding",
        translation_key="next_feeding",
        icon="mdi:food-drumstick-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="feeding_status",
        translation_key="feeding_status",
        icon="mdi:food-variant",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "feeding", "done", "failed"],
    ),
    SensorEntityDescription(
        key="last_feed_time",
        translation_key="last_feed_time",
        icon="mdi:history",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

TC02_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="tc02_auto_countdown_remaining",
        translation_key="tc02_auto_countdown_remaining",
        icon="mdi:timer-sand",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

_FEEDER_ONLY_SENSORS = {"feed_plan", "next_feeding", "feeding_status", "last_feed_time"}

_WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _next_feeding(slots: list[dict]) -> tuple[datetime | None, dict | None]:
    """Return (next_datetime, slot) for the earliest upcoming enabled feeding."""
    now = dt_util.now()
    best_dt: datetime | None = None
    best_slot: dict | None = None

    for day_offset in range(8):  # today + 7 days ahead
        check_dt = now + timedelta(days=day_offset)
        check_weekday = check_dt.weekday()  # 0=Mon … 6=Sun

        for slot in slots:
            if not slot.get("enabled", True):
                continue
            weekdays = slot.get("weekdays") or []
            slot_weekdays = {_WEEKDAY_MAP.get(d.lower(), -1) for d in weekdays}
            if check_weekday not in slot_weekdays:
                continue

            time_str = slot.get("time", "00:00")
            try:
                hour, minute = (int(x) for x in time_str.split(":"))
            except (ValueError, AttributeError):
                continue

            candidate = check_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                continue
            if best_dt is None or candidate < best_dt:
                best_dt = candidate
                best_slot = slot

    return best_dt, best_slot


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetizenBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE sensors."""
    coordinator = entry.runtime_data
    device = coordinator.device
    is_tc02 = device.device_type == "tc02"
    active = [
        desc
        for desc in SENSORS
        if not (is_tc02 and desc.key in _FEEDER_ONLY_SENSORS) and device.supports(desc.key)
    ]
    if is_tc02:
        active += TC02_SENSORS
    entities = [NetizenBLESensor(coordinator, desc) for desc in active]
    async_add_entities(entities)


class NetizenBLESensor(NetizenBLEEntity, SensorEntity):
    """Netizen BLE sensor."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> str | int | datetime | None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        if key == "feed_plan":
            slots = data.get("feed_plan_slots") or []
            return len(slots)
        if key == "next_feeding":
            slots = data.get("feed_plan_slots") or []
            next_dt, _ = _next_feeding(slots)
            return next_dt
        if key == "power_source":
            mode = data.get("power_mode")
            if mode is None:
                return None
            return "battery" if mode == "Battery" else "mains"
        if key == "feeding_status":
            status = data.get("feeding_status")
            return status if status in ("idle", "feeding", "done", "failed") else None
        if key == "last_feed_time":
            result = data.get("last_feed_result")
            if not result or not isinstance(result, dict):
                return None
            ts = result.get("timestamp")
            if not ts:
                return None
            try:
                naive = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                # The feeder clock runs on local time (it is synced from the host).
                return naive.replace(tzinfo=dt_util.get_default_time_zone())
            except (ValueError, TypeError):
                return None
        if key == "tc02_auto_countdown_remaining":
            v = data.get("tc02_auto_countdown_remaining")
            return int(v) if v is not None else None
        return data.get(key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose schedule slots / device info in attributes."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        key = self.entity_description.key
        if key == "feed_plan" and "feed_plan_slots" in data:
            attrs["slots"] = data["feed_plan_slots"]
        if key == "next_feeding":
            slots = data.get("feed_plan_slots") or []
            _, slot = _next_feeding(slots)
            if slot:
                attrs["portions"] = slot.get("portions", 1)
                attrs["weekdays"] = slot.get("weekdays", [])
                attrs["time"] = slot.get("time", "")
        if key == "last_feed_time":
            result = data.get("last_feed_result")
            if isinstance(result, dict):
                attrs.update({k: v for k, v in result.items() if k != "timestamp"})
        return attrs
