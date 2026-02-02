"""Config flow for Pet Netizen BLE (feeder via petnetizen_feeder)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_DEVICE_TYPE, DOMAIN, SERVICE_UUIDS, SUPPORTED_BLE_NAME_PREFIXES

_LOGGER = logging.getLogger(__name__)


def _is_netizen_device(info: BluetoothServiceInfoBleak) -> bool:
    """Check if device uses Netizen feeder service UUID or known name prefix."""
    if info.service_uuids:
        for uuid in info.service_uuids:
            if str(uuid).lower() in {u.lower() for u in SERVICE_UUIDS}:
                return True
    name = (info.name or "").strip().upper()
    return any(name.startswith(p.upper()) for p in SUPPORTED_BLE_NAME_PREFIXES)


def _detect_device_type_from_name(name: str | None) -> str:
    """Return device type for protocol: standard, jk, or ali."""
    if not name or not name.strip():
        return "standard"
    name_upper = name.strip().upper()
    if "JK" in name_upper:
        return "jk"
    if "ALI" in name_upper or "ALIBABA" in name_upper:
        return "ali"
    return "standard"


class NetizenBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Netizen BLE config flow."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: list[tuple[str, str, str]] = []  # (address, name, device_type)

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
        """Choose add method: manual MAC or discover."""
        if user_input is not None:
            if user_input.get("method") == "discover":
                return await self.async_step_discover()
            return await self.async_step_manual()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="manual"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="manual", label="Enter MAC address"),
                                selector.SelectOptionDict(value="discover", label="Search for devices"),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual add by MAC address."""
        errors: dict[str, str] = {}
        if user_input:
            addr = (user_input.get(CONF_ADDRESS) or "").strip().upper().replace("-", ":")
            if len(addr) == 12 and ":" not in addr:
                addr = ":".join(addr[i : i + 2] for i in range(0, 12, 2))
            if len(addr) == 17 and addr.count(":") == 5:
                await self.async_set_unique_id(addr)
                self._abort_if_unique_id_configured()
                data: dict[str, Any] = {CONF_ADDRESS: addr}
                if user_input.get("verification_code"):
                    data["verification_code"] = user_input["verification_code"].strip()
                return self.async_create_entry(
                    title=user_input.get("name") or f"Netizen {addr[-8:].replace(':', '')}",
                    data=data,
                )
            errors["base"] = "invalid_address"

        return self.async_show_form(
            step_id="manual",
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

    async def async_step_discover(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Run BLE scan and let user pick a feeder (library discover_feeders)."""
        from petnetizen_feeder import discover_feeders

        # Run or re-run discovery when first entering or when retrying after no devices found
        if user_input is None or not self._discovered:
            self._discovered = await discover_feeders(timeout=12.0)
            if not self._discovered:
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema(
                        {vol.Optional("retry", default=True): bool}
                    ),
                    errors={"base": "no_devices_found"},
                )

        # If we have no selection yet, show the device picker
        if user_input is not None and CONF_ADDRESS not in user_input:
            # User submitted the "no devices" retry form - already re-ran discovery above
            if not self._discovered:
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema(
                        {vol.Optional("retry", default=True): bool}
                    ),
                    errors={"base": "no_devices_found"},
                )
            options = [
                selector.SelectOptionDict(value=addr, label=f"{name} ({addr})")
                for addr, name, _ in self._discovered
            ]
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=options,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Optional("verification_code", default="00000000"): str,
                    }
                ),
            )

        if user_input is None:
            options = [
                selector.SelectOptionDict(value=addr, label=f"{name} ({addr})")
                for addr, name, _ in self._discovered
            ]
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=options,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Optional("verification_code", default="00000000"): str,
                    }
                ),
            )

        addr = (user_input.get(CONF_ADDRESS) or "").strip()
        verification_code = (user_input.get("verification_code") or "00000000").strip()
        selected = next((t for t in self._discovered if t[0] == addr), None)
        if not selected:
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value=a, label=f"{n} ({a})"
                                    )
                                    for a, n, _ in self._discovered
                                ],
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Optional("verification_code", default="00000000"): str,
                    }
                ),
                errors={"base": "invalid_selection"},
            )
        _addr, name, device_type = selected
        await self.async_set_unique_id(addr)
        self._abort_if_unique_id_configured()
        data: dict[str, Any] = {
            CONF_ADDRESS: addr,
            CONF_DEVICE_TYPE: device_type,
        }
        if verification_code:
            data["verification_code"] = verification_code
        return self.async_create_entry(
            title=name or f"Netizen {addr[-8:].replace(':', '')}",
            data=data,
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm discovered device (Bluetooth)."""
        if not self._discovery:
            return self.async_abort(reason="no_discovery")
        if user_input is not None:
            device_type = _detect_device_type_from_name(self._discovery.name)
            data: dict[str, Any] = {
                CONF_ADDRESS: self._discovery.address,
                CONF_DEVICE_TYPE: device_type,
            }
            return self.async_create_entry(
                title=self._discovery.name or self._discovery.address,
                data=data,
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
        data: dict[str, Any] = {CONF_ADDRESS: addr}
        if import_data.get("verification_code"):
            data["verification_code"] = import_data["verification_code"]
        if import_data.get("device_type") in ("standard", "jk", "ali"):
            data[CONF_DEVICE_TYPE] = import_data["device_type"]
        return self.async_create_entry(
            title=import_data.get("name") or f"Netizen {addr[-8:].replace(':', '')}",
            data=data,
        )
