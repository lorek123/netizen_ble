# Pet Netizen BLE

Home Assistant integration for **Pet Netizen / CloudPets smart feeders** using the [petnetizen_feeder](https://github.com/lorek123/petnetizen_feeder) BLE library. No cloud or app login required.

## Supported devices

- **Pet Netizen feeders:** Du-W11B, Du-W12B, Du-W15B, Du-W10B, Du-F03B, Du-F06B, Du-F08B, Du-F09B, Du-F16B, DU-F14B (standard BLE service `0000ae30`)

Add by **Bluetooth discovery** or by entering the device **MAC address** (e.g. `E6:C0:07:09:A3:D3`).

## Features

- **Button**: Feed now (uses portions from the number entity), Refresh schedule
- **Number**: Portions (1–15) for manual feed
- **Switches**: Manual feed (trigger), Child lock, Prompt sound
- **Sensor**: Feed plan (slot count; schedule slots in attributes)
- **Binary sensor**: Child lock (locked / unlocked)
- **Service**: `netizen_ble.set_feed_plan` – set feed schedule (device_id, schedule: list of {weekdays, time, portions, enabled})

Weekdays: `sun`, `mon`, `tue`, `wed`, `thu`, `fri`, `sat`. Time: `HH:MM`. Portions: 1–15.

## Installation (HACS)

1. In HACS go to **Integrations** → **⋮** → **Custom repositories**
2. Add this repository URL and choose **Integration**
3. Search for **Pet Netizen BLE** and install
4. Restart Home Assistant
5. **Settings → Devices & services → Add integration** → search **Pet Netizen BLE**
6. Add by MAC address or from the discovered Bluetooth device list

No cloud account or app pairing is required. The integration uses the default verification code `00000000` (configurable in manual setup).

## Repositories

- **HACS**: Add this repo as a custom integration repository
- **Library**: [petnetizen_feeder](https://github.com/lorek123/petnetizen_feeder) (PyPI: `petnetizen-feeder`)
- **GitHub**: [netizen_ble](https://github.com/lorek123/netizen_ble)
