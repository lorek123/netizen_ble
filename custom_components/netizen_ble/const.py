"""Constants for Pet Netizen BLE integration (feeder-only, uses petnetizen_feeder library)."""

DOMAIN = "netizen_ble"

CONF_ADDRESS = "address"
CONF_VERIFICATION_CODE = "verification_code"

# BLE service UUID (standard feeder protocol - petnetizen_feeder)
SERVICE_UUID = "0000ae30-0000-1000-8000-00805f9b34fb"

# Default verification code (no cloud required)
DEFAULT_VERIFICATION_CODE = "00000000"

# Supported feeder name prefixes for Bluetooth discovery
SUPPORTED_BLE_NAMES = (
    "Du-W12B",
    "Du-W11B",
    "Du-F08B",
    "Du-F06",
    "Du-F03B",
    "Du-F09B",
    "Du-F16B",
    "Du-W15B",
    "Du-W10B",
    "DU-F14B",
)
