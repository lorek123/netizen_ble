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

Optional entities are created only for models that have the feature, using the same
per-model feature list as the Pet Netizen app (matched by the advertised BLE name, e.g.
`Du-W11B`). Unknown models get every entity. Entities for unsupported features are
removed on startup. Settings (switches, do-not-disturb times, portions, sync time) are
*configuration* entities and power source is *diagnostic*; the firmware version is shown in the
device info.

| Platform | Entity | Notes |
|---|---|---|
| `button` | Feed now | Triggers feed using the Portions value |
| `button` | Sync time | Sets the feeder clock to Home Assistant's local time (config) |
| `number` | Portions | 1–15, used by Feed now |
| `switch` | Child lock | Models with child lock |
| `switch` | Prompt sound | Feeding reminder tone; models with it |
| `switch` | LED indicator | Models with an indicator light |
| `switch` | Atmosphere light | Du-F03B |
| `switch` | Auto lock | DU-PD01B, Du-TC02 |
| `switch` | Do not disturb | Du-F09B, Du-F16B |
| `switch` | Long ring | Unknown models only (the app never shows it) |
| `sensor` | Battery | % — DU-F14B, DU-CP01B |
| `sensor` | Power source | Mains / battery; models with a battery |
| `sensor` | Feed plan | Slot count; full schedule in attributes |
| `sensor` | Next feeding | Timestamp of next scheduled feed |
| `sensor` | Feeding status | Idle / Feeding / Done / Failed |
| `sensor` | Last feed time | Timestamp |
| `binary_sensor` | Fault | `problem` class — any fault |
| `binary_sensor` | Food stuck / Food outlet blocked / Out of food | Individual fault bits |
| `binary_sensor` | Low battery | Fault bit; only while on battery |
| `time` | Do not disturb start / end | Models with do not disturb |

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

### `petnetizen_ble.set_feed_plan`

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

Copy `custom_components/petnetizen_ble/` into your HA `custom_components/` directory and restart.

## Upgrading from 2.x to 3.0

3.0 renames the integration from `netizen_ble` to **`petnetizen_ble`** (the name intended for
Home Assistant core) and removes a few entities. Home Assistant cannot move a device between
integrations, so the feeder has to be added again:

1. **Settings → Devices & services → Pet Netizen BLE** — delete the feeder entry.
2. Update **Pet Netizen BLE** to 3.0 in HACS and restart Home Assistant. If a
   `custom_components/netizen_ble` folder is left behind, delete it and restart again.
3. The feeder is discovered again — click **Add**. Because the old entry was deleted first, the
   entities get the same entity IDs as before.
4. Update automations and scripts:

| 2.x | 3.0 |
|---|---|
| Action `netizen_ble.set_feed_plan` | `petnetizen_ble.set_feed_plan` |
| Manual feed switch | **Feed now** button |
| Refresh schedule button | `homeassistant.update_entity` on any feeder entity |
| Factory reset button | Removed (use the Pet Netizen app) |
| Fault status sensor | **Fault** binary sensor plus Food stuck / Food outlet blocked / Out of food |
| Firmware version sensor | Shown in the device info |
| Feeding status `error` | `done` (the old value was a mis-decoding) |

## Setup

Feeders in range of a Home Assistant Bluetooth adapter or proxy are discovered automatically
and show up under **Settings → Devices & services** — click **Add**. You can also add one with
**Add integration → Pet Netizen BLE** and pick it from the list of feeders Home Assistant
currently sees. If none is listed, check that the feeder is powered and in range, and that it
appears under **Settings → System → Hardware → Bluetooth**.

The device type is detected from the Bluetooth name (`Du-TC02` → TC02, `Du-CP01B` → CP01B, …).
The **verification code** defaults to `00000000` — leave it unless you set a custom code in the
Pet Netizen app.

## BLE proxy (remote feeders)

ESPHome Bluetooth proxies work with **ESPHome 2026.10 or newer** (tested: 2026.10.0 on an
ESP32-C6, with the proxy as the only connection path). Before that update, the same proxy failed
every connection while enabling notifications (`BluetoothGATTErrorResponse: Unknown error (19)`
during `start_notify`), so if you see that error, update the proxy's ESPHome first.

The proxy must be **active** to make connections:

```yaml
bluetooth_proxy:
  active: true
```

When both a local adapter and a proxy can hear the feeder, Home Assistant picks the path for
each connection by signal strength and free slots. Enable debug logging for
`custom_components.petnetizen_ble` to see which path each connection used.

## Protocol

EA/AE framing over Tuya BLE (service UUID `0000ae30`). Reverse engineered from the
Pet Netizen Android app. No cloud involvement at runtime.

## Development

```bash
uv sync --dev          # Python 3.14.2+, pulls Home Assistant's test harness
uv run pytest          # tests in tests/ (config flow, setup/unload, actions)
uv run ruff check custom_components/ tests/
```

## License

MIT
