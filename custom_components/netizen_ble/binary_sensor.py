"""Netizen BLE binary sensor entities."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

_LOGGER = logging.getLogger(__name__)

# Child lock is exposed only as a switch (control + state) to avoid switch/sensor sync issues.
BINARY_SENSORS: list = []


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE binary sensors."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    if not BINARY_SENSORS:
        async_add_entities([])
        return
    # Reserved for future binary sensors; child lock is switch-only.
    async_add_entities([])
