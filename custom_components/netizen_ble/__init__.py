"""Pet Netizen BLE integration (feeder devices via petnetizen_feeder library)."""

from __future__ import annotations

import logging

import voluptuous as vol
from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEVICE_TYPE,
    CONF_VERIFICATION_CODE,
    DEFAULT_VERIFICATION_CODE,
    DOMAIN,
)
from .coordinator import NetizenBLECoordinator
from .device import NetizenBLEDevice

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.TIME,
]

_LOGGER = logging.getLogger(__name__)


def _remove_unsupported_entities(
    hass: HomeAssistant, entry: ConfigEntry, device: NetizenBLEDevice
) -> None:
    """Drop registry entries for features this feeder model does not have."""
    features = device.features
    if features is None:
        return
    ent_reg = er.async_get(hass)
    prefix = f"{device.address}_"
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        key = ent.unique_id.removeprefix(prefix)
        if ent.unique_id.startswith(prefix) and not device.supports(key):
            _LOGGER.debug("Removing %s: not supported by %s", ent.entity_id, features.model)
            ent_reg.async_remove(ent.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netizen BLE from a config entry (feeder via petnetizen_feeder)."""
    address = entry.data[CONF_ADDRESS].upper().replace("-", ":")
    if len(address) == 12 and ":" not in address:
        address = ":".join(address[i : i + 2] for i in range(0, 12, 2))
    verification_code = entry.data.get(CONF_VERIFICATION_CODE) or DEFAULT_VERIFICATION_CODE
    device_type = entry.data.get(CONF_DEVICE_TYPE)

    ble_device = bluetooth.async_ble_device_from_address(hass, address, True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"BLE device {address} not found by any scanner")

    entry_title = entry.title

    async def _create_ble_connection() -> BleakClient:
        """Obtain a fresh BleakClient via HA's Bluetooth stack.

        HA picks the connection path itself (by RSSI and slot availability
        across all connectable scanners); the BLEDevice passed here does not
        pin it to an adapter, and there is no supported API that does.
        """
        dev = bluetooth.async_ble_device_from_address(hass, address, True)
        if dev is None:
            raise RuntimeError(f"BLE device {address} not found by any scanner")
        client = await establish_connection(
            BleakClient,
            dev,
            entry_title,
            disconnected_callback=device.disconnected_callback,
            ble_device_callback=lambda: (
                bluetooth.async_ble_device_from_address(hass, address, True) or dev
            ),
        )
        _LOGGER.debug("Connected to feeder %s via %s", address, getattr(client, "backend_id", "?"))
        return client

    device = NetizenBLEDevice(
        address,
        verification_code=verification_code,
        device_type=device_type,
        connection_factory=_create_ble_connection,
        ble_name=ble_device.name or entry.title,
    )

    # The library retries failed connection attempts itself; HA retries setup on top.
    if not await device.connect():
        # Release a half-open link so a proxy does not leak the slot.
        await device.disconnect()
        raise ConfigEntryNotReady(f"Could not connect to feeder {address}")

    coordinator = NetizenBLECoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    # The first refresh fetched the reported model name, so features are final.
    _remove_unsupported_entities(hass, entry, device)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def _async_stop(_: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop))

    async def async_set_feed_plan(call) -> None:
        """Service: set_feed_plan(device_id, schedule). schedule: list of {weekdays, time, portions, enabled}."""
        device_id = call.data.get(CONF_DEVICE_ID)
        schedule = call.data.get("schedule", [])
        if not device_id or not schedule:
            _LOGGER.warning("set_feed_plan requires device_id and schedule")
            return
        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(device_id)
        if not device_entry:
            _LOGGER.warning("Device %s not found", device_id)
            return
        for _entry_id, coord in list(hass.data.get(DOMAIN, {}).items()):
            if not isinstance(coord, NetizenBLECoordinator):
                continue
            if (DOMAIN, coord.device.address) in device_entry.identifiers:
                await coord.device.set_feed_plan(schedule)
                await coord.async_request_refresh()
                return
        _LOGGER.warning("Netizen BLE device not found for device_id %s", device_id)

    hass.services.async_register(
        DOMAIN,
        "set_feed_plan",
        async_set_feed_plan,
        vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required("schedule"): [
                    vol.Schema(
                        {
                            vol.Required("weekdays"): [str],
                            vol.Required("time"): str,
                            vol.Optional("portions", default=1): vol.All(int, vol.Range(0, 15)),
                            vol.Optional("enabled", default=True): bool,
                        }
                    )
                ],
            }
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: NetizenBLECoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok
