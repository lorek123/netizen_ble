"""Actions (services) for Pet Netizen BLE: editing the feeding schedule.

The feeder has no per-slot commands: SET_FEEDER_PLAN always replaces the whole
plan. Single-slot actions therefore read the current plan from the
coordinator, change one slot and write all of them back.
"""

from __future__ import annotations

import logging
from datetime import time
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import NetizenBLEConfigEntry
from .device import WEEKDAY_ORDER as WEEKDAYS

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_FEEDING = "set_feeding"
SERVICE_REMOVE_FEEDING = "remove_feeding"
SERVICE_SET_FEEDING_SCHEDULE = "set_feeding_schedule"
SERVICE_SET_FEED_PLAN = "set_feed_plan"  # deprecated alias of set_feeding_schedule

# Same limits as the Pet Netizen app (plan_count / feed_count for every model).
MAX_FEEDINGS = 10
MAX_PORTIONS = 15

ATTR_TIME = "time"
ATTR_WEEKDAYS = "weekdays"
ATTR_PORTIONS = "portions"
ATTR_ENABLED = "enabled"
ATTR_SCHEDULE = "schedule"

_WEEKDAYS_SCHEMA = vol.All(
    cv.ensure_list, [vol.All(cv.string, vol.Lower, vol.In(WEEKDAYS))], vol.Length(min=1)
)
_PORTIONS_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_PORTIONS))

SLOT_FIELDS = {
    vol.Required(ATTR_TIME): cv.time,
    vol.Optional(ATTR_WEEKDAYS, default=WEEKDAYS): _WEEKDAYS_SCHEMA,
    vol.Optional(ATTR_PORTIONS, default=1): _PORTIONS_SCHEMA,
    vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
}

SET_FEEDING_SCHEMA = vol.Schema({vol.Required(CONF_DEVICE_ID): cv.string, **SLOT_FIELDS})
REMOVE_FEEDING_SCHEMA = vol.Schema(
    {vol.Required(CONF_DEVICE_ID): cv.string, vol.Required(ATTR_TIME): cv.time}
)
SET_FEEDING_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(ATTR_SCHEDULE): vol.All(cv.ensure_list, [vol.Schema(SLOT_FIELDS)]),
    }
)


def _hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _slot(data: dict[str, Any]) -> dict[str, Any]:
    """Validated action data -> slot in the form the feeder reports it."""
    return {
        ATTR_WEEKDAYS: [day for day in WEEKDAYS if day in data[ATTR_WEEKDAYS]],
        ATTR_TIME: _hhmm(data[ATTR_TIME]),
        ATTR_PORTIONS: data[ATTR_PORTIONS],
        ATTR_ENABLED: data[ATTR_ENABLED],
    }


def _entry_for_device(hass: HomeAssistant, device_id: str) -> NetizenBLEConfigEntry:
    """Return the loaded config entry that owns ``device_id``."""
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    for entry_id in device_entry.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"name": entry.title},
                )
            return entry
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={"device_id": device_id},
    )


async def _current_schedule(entry: NetizenBLEConfigEntry) -> list[dict[str, Any]]:
    """The feeder's current plan; refreshed first if it has not been read yet."""
    coordinator = entry.runtime_data
    if "feed_plan_slots" not in (coordinator.data or {}):
        await coordinator.async_refresh()
    slots = (coordinator.data or {}).get("feed_plan_slots")
    if slots is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schedule_unknown",
            translation_placeholders={"name": entry.title},
        )
    return [dict(slot) for slot in slots]


def _check_schedule(slots: list[dict[str, Any]]) -> None:
    if len(slots) > MAX_FEEDINGS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="too_many_feedings",
            translation_placeholders={"max": str(MAX_FEEDINGS)},
        )
    times = [slot[ATTR_TIME] for slot in slots]
    if duplicates := sorted({t for t in times if times.count(t) > 1}):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="duplicate_feeding_time",
            translation_placeholders={"time": ", ".join(duplicates)},
        )


async def _write_schedule(entry: NetizenBLEConfigEntry, slots: list[dict[str, Any]]) -> None:
    _check_schedule(slots)
    coordinator = entry.runtime_data
    if not await coordinator.device.set_feed_plan(sorted(slots, key=lambda s: s[ATTR_TIME])):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_feed_plan_failed",
            translation_placeholders={"name": entry.title},
        )
    await coordinator.async_request_refresh()


async def _async_set_feeding(call: ServiceCall) -> None:
    """Add a feeding, or update the one at the same time."""
    entry = _entry_for_device(call.hass, call.data[CONF_DEVICE_ID])
    new = _slot(call.data)
    slots = [s for s in await _current_schedule(entry) if s[ATTR_TIME] != new[ATTR_TIME]]
    await _write_schedule(entry, [*slots, new])


async def _async_remove_feeding(call: ServiceCall) -> None:
    """Remove the feeding at the given time."""
    entry = _entry_for_device(call.hass, call.data[CONF_DEVICE_ID])
    when = _hhmm(call.data[ATTR_TIME])
    slots = await _current_schedule(entry)
    remaining = [s for s in slots if s[ATTR_TIME] != when]
    if len(remaining) == len(slots):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="feeding_not_found",
            translation_placeholders={"time": when, "name": entry.title},
        )
    await _write_schedule(entry, remaining)


async def _async_set_feeding_schedule(call: ServiceCall) -> None:
    """Replace the whole schedule."""
    if call.service == SERVICE_SET_FEED_PLAN:
        _LOGGER.warning(
            "%s.%s is deprecated, use %s.%s instead",
            DOMAIN,
            SERVICE_SET_FEED_PLAN,
            DOMAIN,
            SERVICE_SET_FEEDING_SCHEDULE,
        )
    entry = _entry_for_device(call.hass, call.data[CONF_DEVICE_ID])
    await _write_schedule(entry, [_slot(slot) for slot in call.data[ATTR_SCHEDULE]])


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, not per config entry)."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FEEDING, _async_set_feeding, schema=SET_FEEDING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_FEEDING, _async_remove_feeding, schema=REMOVE_FEEDING_SCHEMA
    )
    for service in (SERVICE_SET_FEEDING_SCHEDULE, SERVICE_SET_FEED_PLAN):
        hass.services.async_register(
            DOMAIN, service, _async_set_feeding_schedule, schema=SET_FEEDING_SCHEDULE_SCHEMA
        )
