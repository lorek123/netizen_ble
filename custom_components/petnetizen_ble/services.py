"""Actions (services) for Pet Netizen BLE."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import NetizenBLEConfigEntry

SERVICE_SET_FEED_PLAN = "set_feed_plan"

SET_FEED_PLAN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("schedule"): [
            vol.Schema(
                {
                    vol.Required("weekdays"): [cv.string],
                    vol.Required("time"): cv.string,
                    vol.Optional("portions", default=1): vol.All(int, vol.Range(0, 15)),
                    vol.Optional("enabled", default=True): bool,
                }
            )
        ],
    }
)


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


async def _async_set_feed_plan(call: ServiceCall) -> None:
    """Write a feeding schedule to the feeder."""
    entry = _entry_for_device(call.hass, call.data[CONF_DEVICE_ID])
    coordinator = entry.runtime_data
    if not await coordinator.device.set_feed_plan(call.data["schedule"]):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_feed_plan_failed",
            translation_placeholders={"name": entry.title},
        )
    await coordinator.async_request_refresh()


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, not per config entry)."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FEED_PLAN, _async_set_feed_plan, schema=SET_FEED_PLAN_SCHEMA
    )
