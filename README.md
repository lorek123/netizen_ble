# Pet Netizen BLE – Home Assistant integration

Home Assistant custom component for **Pet Netizen / CloudPets** smart feeders. Uses the [petnetizen_feeder](https://github.com/lorek123/petnetizen_feeder) BLE library. Works **without cloud or app login**.

## Supported devices

Pet Netizen feeders that use the standard BLE protocol (service UUID `0000ae30`), including:

- **Du-W11B**, **Du-W12B**, **Du-W15B**, **Du-W10B**
- **Du-F03B**, **Du-F06B**, **Du-F08B**, **Du-F09B**, **Du-F16B**
- **DU-F14B**

Add by **Bluetooth discovery** or by entering the device **MAC address** (e.g. `E6:C0:07:09:A3:D3`).

## Features

- **Button**: Feed now (uses portions from the number entity), Refresh schedule
- **Number**: Portions (1–15) for manual feed
- **Switches**: Manual feed (trigger), Child lock, Prompt sound
- **Sensor**: Feed plan (slot count; schedule slots in attributes)
- **Binary sensor**: Child lock (locked / unlocked)
- **Service**: `netizen_ble.set_feed_plan` – set feed schedule (`device_id`, `schedule`: list of `{weekdays, time, portions, enabled}`). Weekdays: `sun`, `mon`, `tue`, `wed`, `thu`, `fri`, `sat`. Time: `HH:MM`. Portions: 1–15.

## Installation

### Via HACS (recommended)

1. Open **HACS** → **Integrations** → **⋮** → **Custom repositories**
2. Add this repository URL and choose **Integration**
3. Search for **Pet Netizen BLE** and install
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/netizen_ble` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

**Note:** The integration depends on the [petnetizen-feeder](https://pypi.org/project/petnetizen-feeder/) PyPI package. If you install manually, ensure your environment has `petnetizen-feeder>=0.1.0` (Home Assistant will install it from `manifest.json` when the integration is loaded).

## Configuration

1. **Settings → Devices & services → Add integration**
2. Search for **Pet Netizen BLE**
3. Either:
   - **Configure** and enter the device **MAC address** (e.g. `E6:C0:07:09:A3:D3`), or
   - Add a **discovered** device from the list.

Optional: **Verification code** (default `00000000`) can be set when adding manually; leave default unless you use a custom code in the app.

No cloud account or app pairing is required.

## Protocol

BLE communication is handled by the [petnetizen_feeder](https://github.com/lorek123/petnetizen_feeder) library (Tuya BLE protocol). Service UUID: `0000ae30`.

## License

MIT
