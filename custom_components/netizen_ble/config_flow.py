"""Config flow for Pet Netizen BLE (feeder via petnetizen_feeder)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, SERVICE_UUID, SUPPORTED_BLE_NAMES

_LOGGER = logging.getLogger(__name__)


def _is_netizen_device(info: BluetoothServiceInfoBleak) -> bool:
    """Check if device uses Netizen feeder service UUID or known name."""
    if info.service_uuids:
        for uuid in info.service_uuids:
            if SERVICE_UUID.lower() in str(uuid).lower():
                return True
    name = (info.name or "").strip().upper()
    for prefix in SUPPORTED_BLE_NAMES:
        if name.startswith(prefix.upper()):
            return True
    return False


def _detect_device_type(info: BluetoothServiceInfoBleak) -> str:
    """Return device type for discovery (feeder-only)."""
    return "feeder"


class NetizenBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Netizen BLE config flow."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._discovery: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        """Handle Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not _is_netizen_device(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or discovery_info.address}
        return await self.async_step_confirm()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual add by MAC address."""
        errors: dict[str, str] = {}
        if user_input:
            addr = (user_input.get(CONF_ADDRESS) or "").strip().upper().replace("-", ":")
            if len(addr) == 12 and ":" not in addr:
                addr = ":".join(addr[i : i + 2] for i in range(0, 12, 2))
            if len(addr) == 17 and addr.count(":") == 5:
                await self.async_set_unique_id(addr)
                self._abort_if_unique_id_configured()
                data = {CONF_ADDRESS: addr}
                if user_input.get("verification_code"):
                    data["verification_code"] = user_input["verification_code"].strip()
                return self.async_create_entry(
                    title=user_input.get("name") or f"Netizen {addr[-8:].replace(':', '')}",
                    data=data,
                )
            errors["base"] = "invalid_address"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS, default=user_input.get(CONF_ADDRESS, "") if user_input else ""
                    ): str,
                    vol.Optional("name", default=""): str,
                    vol.Optional("verification_code", default="00000000"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hint": "Enter device MAC address (e.g. E6:C0:07:09:A3:D3). No cloud or app login required."
            },
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm discovered device."""
        if not self._discovery:
            return self.async_abort(reason="no_discovery")
        if user_input is not None:
            device_type = _detect_device_type(self._discovery)
            return self.async_create_entry(
                title=self._discovery.name or self._discovery.address,
                data={CONF_ADDRESS: self._discovery.address, "device_type": device_type},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"name": self._discovery.name or self._discovery.address},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle YAML import (optional)."""
        addr = (import_data.get(CONF_ADDRESS) or "").strip().upper().replace("-", ":")
        if len(addr) != 17 or addr.count(":") != 5:
            return self.async_abort(reason="invalid_address")
        await self.async_set_unique_id(addr)
        self._abort_if_unique_id_configured()
        data = {CONF_ADDRESS: addr}
        if import_data.get("verification_code"):
            data["verification_code"] = import_data["verification_code"]
        return self.async_create_entry(
            title=import_data.get("name") or f"Netizen {addr[-8:].replace(':', '')}",
            data=data,
        )
