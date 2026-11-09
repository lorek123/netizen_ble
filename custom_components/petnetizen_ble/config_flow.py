"""Config flow for Pet Netizen BLE (feeder via petnetizen_feeder)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .connection import create_device
from .const import (
    CONF_DEVICE_TYPE,
    CONF_VERIFICATION_CODE,
    DEFAULT_VERIFICATION_CODE,
    DOMAIN,
    SERVICE_UUIDS,
    SUPPORTED_BLE_NAME_PREFIXES,
)

VERIFICATION_CODE_FIELD = {
    vol.Optional(CONF_VERIFICATION_CODE, default=DEFAULT_VERIFICATION_CODE): str
}


def _is_netizen_device(info: BluetoothServiceInfoBleak) -> bool:
    """Check if device uses Netizen feeder service UUID or known name prefix."""
    if info.service_uuids:
        for uuid in info.service_uuids:
            if str(uuid).lower() in {u.lower() for u in SERVICE_UUIDS}:
                return True
    name = (info.name or "").strip().upper()
    return any(name.startswith(p.upper()) for p in SUPPORTED_BLE_NAME_PREFIXES)


def _detect_device_type_from_name(name: str | None) -> str:
    """Return device type for protocol: standard, jk, ali, cp01b, f14b or tc02."""
    if not name or not name.strip():
        return "standard"
    name_upper = name.strip().upper()
    if "JK" in name_upper:
        return "jk"
    if "ALI" in name_upper or "ALIBABA" in name_upper:
        return "ali"
    if "CP01B" in name_upper:
        return "cp01b"
    if "F14B" in name_upper:
        return "f14b"
    if "TC02" in name_upper:
        return "tc02"
    return "standard"


class NetizenBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Netizen BLE config flow."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_try_connect(
        self, info: BluetoothServiceInfoBleak, verification_code: str
    ) -> str | None:
        """Connect once with the given code; return an error key, or None if it worked."""
        device = create_device(
            self.hass,
            info.address,
            name=info.name or info.address,
            verification_code=verification_code or DEFAULT_VERIFICATION_CODE,
            device_type=_detect_device_type_from_name(info.name),
            ble_name=info.name,
        )
        try:
            if await device.connect():
                return None
            return "invalid_verification_code" if device.verification_rejected else "cannot_connect"
        finally:
            await device.disconnect()

    def _create_entry(
        self, info: BluetoothServiceInfoBleak, verification_code: str
    ) -> ConfigFlowResult:
        data: dict[str, Any] = {
            CONF_ADDRESS: info.address,
            CONF_DEVICE_TYPE: _detect_device_type_from_name(info.name),
        }
        if verification_code and verification_code != DEFAULT_VERIFICATION_CODE:
            data[CONF_VERIFICATION_CODE] = verification_code
        return self.async_create_entry(title=info.name or info.address, data=data)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a feeder found by Home Assistant's Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not _is_netizen_device(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or discovery_info.address}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered feeder."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input.get(CONF_VERIFICATION_CODE, "").strip()
            if not (error := await self._async_try_connect(self._discovery, code)):
                return self._create_entry(self._discovery, code)
            errors["base"] = error
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(VERIFICATION_CODE_FIELD),
            description_placeholders={"name": self._discovery.name or self._discovery.address},
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a feeder Home Assistant's Bluetooth has seen but that is not set up yet."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered[address]
            code = user_input.get(CONF_VERIFICATION_CODE, "").strip()
            if not (error := await self._async_try_connect(info, code)):
                return self._create_entry(info, code)
            errors["base"] = error
        else:
            configured = self._async_current_ids(include_ignore=False)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.address not in configured and _is_netizen_device(info):
                    self._discovered[info.address] = info
            if not self._discovered:
                return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name or address} ({address})"
                            for address, info in self._discovered.items()
                        }
                    ),
                    **VERIFICATION_CODE_FIELD,
                }
            ),
            errors=errors,
        )
