"""Pet Netizen BLE integration (feeder devices via petnetizen_feeder library)."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .connection import create_device
from .const import (
    CONF_DEVICE_TYPE,
    CONF_VERIFICATION_CODE,
    DEFAULT_VERIFICATION_CODE,
    DOMAIN,
)
from .coordinator import NetizenBLEConfigEntry, NetizenBLECoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.TIME,
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions once for the integration."""
    async_setup_services(hass)
    return True


def _remove_orphaned_entities(hass: HomeAssistant, entry: NetizenBLEConfigEntry) -> None:
    """Drop registry entries no current entity claims.

    Covers features this model lacks and entities removed in earlier versions
    (e.g. the pre-2.2.2 child lock binary sensor). Call after platform setup.
    """
    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.disabled_by is not None:
            continue
        state = hass.states.get(ent.entity_id)
        if state is None or state.attributes.get("restored"):
            _LOGGER.debug("Removing orphaned entity %s", ent.entity_id)
            ent_reg.async_remove(ent.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: NetizenBLEConfigEntry) -> bool:
    """Set up Netizen BLE from a config entry (feeder via petnetizen_feeder)."""
    address = entry.data[CONF_ADDRESS].upper().replace("-", ":")
    if len(address) == 12 and ":" not in address:
        address = ":".join(address[i : i + 2] for i in range(0, 12, 2))
    verification_code = entry.data.get(CONF_VERIFICATION_CODE) or DEFAULT_VERIFICATION_CODE
    device_type = entry.data.get(CONF_DEVICE_TYPE)

    ble_device = bluetooth.async_ble_device_from_address(hass, address, True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"BLE device {address} not found by any scanner")

    device = create_device(
        hass,
        address,
        name=entry.title,
        verification_code=verification_code,
        device_type=device_type,
        ble_name=ble_device.name or entry.title,
    )

    # The library retries failed connection attempts itself; HA retries setup on top.
    if not await device.connect():
        # Release a half-open link so a proxy does not leak the slot.
        await device.disconnect()
        raise ConfigEntryNotReady(f"Could not connect to feeder {address}")

    coordinator = NetizenBLECoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def _async_stop(_: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_orphaned_entities(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetizenBLEConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_unload()
    return unload_ok
