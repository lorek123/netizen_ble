"""Config flow tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.petnetizen_ble.config_flow import _detect_device_type_from_name
from custom_components.petnetizen_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import ADDRESS, NAME, service_info

OTHER = "AA:BB:CC:DD:EE:FF"
TOOTHBRUSH = service_info(
    name="Toothbrush", address="11:22:33:44:55:66", uuids=["0000fe0d-0000-1000-8000-00805f9b34fb"]
)


@pytest.fixture(autouse=True)
def no_setup() -> Generator[None]:
    """Creating an entry must not try to reach a feeder."""
    with patch("custom_components.petnetizen_ble.async_setup_entry", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_connect() -> Generator[MagicMock]:
    """The connection test the flow runs before creating an entry."""
    device = MagicMock(verification_rejected=False)
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    with patch(
        "custom_components.petnetizen_ble.config_flow.create_device", return_value=device
    ) as create:
        create.device = device
        yield create


@pytest.fixture
def mock_discovered() -> Generator[MagicMock]:
    """Advertisements Home Assistant's Bluetooth currently knows about."""
    with patch(
        "custom_components.petnetizen_ble.config_flow.async_discovered_service_info",
        return_value=[service_info(), TOOTHBRUSH],
    ) as discovered:
        yield discovered


# --- Bluetooth discovery ----------------------------------------------------


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS, "device_type": "standard"}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_custom_code(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info(name="Du-TC02_AABBCCDDEEFF", uuids=[]),  # matched by name only
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"verification_code": " 12345678 "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: ADDRESS,
        "device_type": "tc02",
        "verification_code": "12345678",
    }


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=TOOTHBRUSH
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- User: pick a discovered feeder -------------------------------------------


async def test_user_picks_discovered_feeder(
    hass: HomeAssistant, mock_discovered: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Only feeders are offered, not every Bluetooth device.
    choices = result["data_schema"].schema[CONF_ADDRESS].container
    assert list(choices) == [ADDRESS]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS, "device_type": "standard"}


async def test_user_skips_configured_feeders(
    hass: HomeAssistant, mock_discovered: MagicMock
) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_no_feeders_seen(hass: HomeAssistant, mock_discovered: MagicMock) -> None:
    mock_discovered.return_value = [TOOTHBRUSH]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_feeder_configured_meanwhile(
    hass: HomeAssistant, mock_discovered: MagicMock
) -> None:
    """Another flow (e.g. discovery) set the feeder up while the picker was open."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- Device type detection ----------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (None, "standard"),
        ("  ", "standard"),
        ("JK-Feeder", "jk"),
        ("ALI-1", "ali"),
        ("DU-CP01B_X", "cp01b"),
        ("DU-F14B_X", "f14b"),
        ("Du-TC02_X", "tc02"),
        ("Du-W11B_X", "standard"),
    ],
)
def test_detect_device_type(name: str | None, expected: str) -> None:
    assert _detect_device_type_from_name(name) == expected


# --- Connection test before creating the entry --------------------------------


async def test_bluetooth_confirm_connects_with_code(
    hass: HomeAssistant, mock_connect: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"verification_code": "12345678"}
    )
    assert mock_connect.call_args.kwargs["verification_code"] == "12345678"
    mock_connect.device.disconnect.assert_awaited_once()  # link released for the entry


@pytest.mark.parametrize(
    ("rejected", "error"),
    [(True, "invalid_verification_code"), (False, "cannot_connect")],
)
async def test_bluetooth_confirm_connection_errors(
    hass: HomeAssistant, mock_connect: MagicMock, rejected: bool, error: str
) -> None:
    device = mock_connect.device
    device.connect.return_value = False
    device.verification_rejected = rejected
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"verification_code": "11111111"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Fixing the code (or getting in range) completes the flow.
    device.connect.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"verification_code": "00000000"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_connection_error(
    hass: HomeAssistant, mock_discovered: MagicMock, mock_connect: MagicMock
) -> None:
    mock_connect.device.connect.return_value = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_connect.device.connect.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
