# Pet Netizen BLE – Home Assistant integration

Home Assistant custom component for **Pet Netizen / CloudPets / Du** smart feeders and pet toys.
Uses the [petnetizen-feeder](https://github.com/lorek123/petnetizen-feeder) library.
Works **fully local — no cloud, no app login, no account required**.

## Supported devices

### Feeders

All feeders advertise over BLE name prefix `Du-` and use service UUID `0000ae30`.

| Model | Notes |
|---|---|
| **Du-F03B**, **Du-F06B**, **Du-F08B**, **Du-F09B**, **Du-F16B** | Standard feeder |
| **Du-W10B**, **Du-W11B**, **Du-W12B**, **Du-W15B** | Water-dispenser feeder |
| **DU-F14B** | V2 protocol variant |
| **DU-CP01B** | Interactive ball feeder — extra controls (see below) |

Also works with `JK-`, `ALI-`, `PET-`, `FEED-` prefix devices using the same BLE protocol.

### Laser cat teaser

| Model | Notes |
|---|---|
| **Du-TC02** | Laser toy — LED color, rotation, sound, auto countdown |

## Entities

### All feeders

| Platform | Entity | Notes |
|---|---|---|
| `button` | Feed now | Triggers feed using the Portions value |
| `button` | Refresh schedule | Re-polls schedule from device |
| `button` | Sync time | Syncs device clock to HA server time |
| `button` | Factory reset | |
| `number` | Portions | 1–15, used by Feed now and Manual feed switch |
| `switch` | Manual feed | Momentary trigger (same as Feed now button) |
| `switch` | Child lock | |
| `switch` | Prompt sound | Feeding reminder tone |
| `switch` | LED indicator | |
| `switch` | Atmosphere light | |
| `switch` | Auto lock | |
| `switch` | Do not disturb | |
| `switch` | Long ring | |
| `sensor` | Battery | % (where supported) |
| `sensor` | Feed plan | Slot count; full schedule in attributes |
| `sensor` | Next feeding | Timestamp of next scheduled feed |
| `sensor` | Firmware version | |
| `sensor` | Fault status | Text description of fault code |
| `sensor` | Feeding status | |
| `sensor` | Last feed time | Timestamp |
| `binary_sensor` | Fault | `problem` class — use in automations |
| `time` | Do not disturb start | |
| `time` | Do not disturb end | |

### DU-CP01B extras

| Platform | Entity | Range |
|---|---|---|
| `number` | Operation mode | 0–5 |
| `number` | Rotation mode | 0–5 |
| `number` | Volume | 0–100 % |
| `number` | Playback frequency | 0–10 |
| `number` | Sound effect | 0–10 |
| `number` | Auto mode countdown | 0–60 min |
| `number` | Fun mode | 0–10 |
| `switch` | Sound | On/off |

### Du-TC02 (laser toy)

| Platform | Entity | Range |
|---|---|---|
| `number` | Operation mode | 0–5 |
| `number` | Rotation mode | 0–5 |
| `number` | Mood light mode | 0–10 |
| `number` | LED color | 0–255 |
| `number` | Sound effect | 0–10 |
| `number` | Playback frequency | 0–10 |
| `number` | Volume | 0–100 % |
| `number` | Auto mode countdown | 0–60 min |
| `number` | Color red / green / blue | 0–255 each |
| `sensor` | Countdown remaining | minutes |
| `switch` | Prompt sound | On/off |
| `button` | Sync time | |
| `button` | Factory reset | |
| `binary_sensor` | Fault | `problem` class |

## Services

### `netizen_ble.set_feed_plan`

Set feed schedule from an automation or script.

| Field | Type | Notes |
|---|---|---|
| `device_id` | string | HA device ID |
| `schedule` | list | List of slot objects (see below) |

Slot object:

```yaml
weekdays: [mon, wed, fri]   # sun mon tue wed thu fri sat, or all
time: "08:00"               # HH:MM
portions: 1                 # 1–15
enabled: true
```

## Installation

### Via HACS (recommended)

1. Open **HACS → Integrations → ⋮ → Custom repositories**
2. Add this repository URL, category **Integration**
3. Install **Pet Netizen BLE** and restart Home Assistant

### Manual

Copy `custom_components/netizen_ble/` into your HA `custom_components/` directory and restart.

## Setup

1. **Settings → Devices & services → Add integration → Pet Netizen BLE**
2. Choose **Search for devices** (BLE scan) or **Enter MAC address**
3. Device type is auto-detected from the BLE name (`Du-TC02` → TC02, `Du-CP01B` → CP01B, etc.)

The **verification code** defaults to `00000000` — leave it unless you set a custom code in the Pet Netizen app.

## Finding your device MAC address

- **nRF Connect** (Android/iOS) — scan and look for devices named `Du-*`, `JK-*`, etc.
- **HA Bluetooth integration** — check **Settings → System → Hardware → Bluetooth** discovered devices
- The MAC appears in the Pet Netizen app under device settings on some firmware versions

## BLE proxy (remote feeders)

If your feeder is out of direct Bluetooth range of the HA server, use an **ESPHome BLE proxy** (ESP32).
The integration automatically restarts the proxy ESP32 if the feeder becomes persistently unreachable.

## Protocol

EA/AE framing over Tuya BLE (service UUID `0000ae30`). Reverse engineered from the
Pet Netizen Android app. No cloud involvement at runtime.

## License

MIT
