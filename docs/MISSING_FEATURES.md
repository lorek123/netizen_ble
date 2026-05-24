# Netizen BLE – Missing Features Specification

Source of truth: decompiled PetNetizen 2.3.5 APK (`net.cloudpets.petNetizen.apk` extracted from
`PetNetizen_2.3.5_APKPure.xapk`), decompiled with JADX 1.5.5.

All APK paths below are relative to `/tmp/petnetizen_jadx/sources/`.

---

## Priority matrix

| # | Feature | Effort | Impact | Status |
|---|---------|--------|--------|--------|
| 1 | [ae00 UUID fix in manifest](#1-ae00-uuid-in-manifestjson) | Trivial | Unblocks Call Pet + Teaser discovery | Missing |
| 2 | [Battery sensor for feeders](#2-battery-sensor-for-feeders) | Small | All supported feeders | Missing |
| 3 | [Water bowl (DpWater)](#3-water-bowl-dpwater) | N/A | Du-W* are standard feeders, no BLE impl needed | N/A |
| 4 | [Cat litter box (DpCatLitter)](#4-cat-litter-box-dpcatlitter) | N/A | Not in ble-device-type.json (WiFi/cloud only) | N/A |
| 5 | [Camera-enabled feeder DPs](#5-camera-enabled-feeder-dps) | Medium | Du-F*C / cam feeders | Missing |
| 6 | [Call Pet intercom (ae00)](#6-call-pet-intercom-ae00) | Large | New device class | Missing |
| 7 | [Aurora Cat (55AA)](#7-aurora-cat-55aa-protocol) | Large | New device class, new protocol | Missing |
| 8 | [DU-CP01B full entities](#8-du-cp01b-full-entities) | Small | Already connects | Done |
| 9 | [DU-F14B sync_time V2](#9-du-f14b-sync_time-v2) | Small | Already connects | Done |
| 10 | [Du-TC02 laser cat teaser](#10-du-tc02-laser-cat-teaser) | Medium | New device class | Done |

---

## 1. ae00 UUID in `manifest.json`

**Source:** `com/cloudpet/handler/ble/Constant.java` lines 17–27

```
CALL_PET_DEVICE_UUID        = "0000ae00-0000-1000-8000-00805f9b34fb"
CALL_PET_DEVICE_UUID_NOTIFY = "0000ae02-0000-1000-8000-00805f9b34fb"
CALL_PET_DEVICE_UUID_WRITE  = "0000ae01-0000-1000-8000-00805f9b34fb"
TEASER_DEVICE_UUID          = "0000ae00-0000-1000-8000-00805f9b34fb"
TEASER_DEVICE_UUID_NOTIFY   = "0000ae02-0000-1000-8000-00805f9b34fb"
TEASER_DEVICE_UUID_WRITE    = "0000ae01-0000-1000-8000-00805f9b34fb"
```

**Problem:** `custom_components/netizen_ble/manifest.json` `bluetooth` filter has `0000ae30`, `0000fff0`,
`0000ffff` but NOT `0000ae00`. Call Pet and Cat Teaser devices are never advertised to HA.

**Fix:** Add to `manifest.json` bluetooth filter:

```json
{"service_uuid": "0000ae00-0000-1000-8000-00805f9b34fb"}
```

Also update `const.py` `SERVICE_UUIDS` to include `"0000ae00-0000-1000-8000-00805f9b34fb"`.

> Note: ae00 shares notify (ae02) and write (ae01) characteristics with ae30 feeders; the service UUID
> itself is the differentiator that identifies the device class.

---

## 2. Battery sensor for feeders

**Source:** `cn/logical/pet/enumeration/DpFeeder.java` – entry `BATTERY_PERCENTAGE`

```java
BATTERY_PERCENTAGE(tag="battery_percentage", defaultDp="battery_percentage",
    defaultCodes="BleFeederBatteryCodec")
```

**Wire:** Response notification on characteristic `ae02`; command byte `0x10` (`BleFeederCmd.AUTO_LOCK`
is NOT battery — `BATTERY_PERCENTAGE` real_tag resolves to a different byte; cross-reference
`ble-device-type.json` dpMappings for the target device to find the correct `real_tag`).

From `BleFeederCmd.java` the hex byte for battery query appears as `0x09` in device type definitions for
some models (same byte as `feed_state`). Verify against nRF Connect capture before shipping:
the response frame `EB 09 ...` contains both feed state and battery in different fields.

**Implementation:**
- In `petnetizen_feeder/protocol.py`: parse the `battery_level` field from the `EB 09` notification
  (already decoded for `feed_state`; battery appears to be in byte offset 5 as a 0–100 value).
- In `device.py`: expose `battery_level: int | None` property (cached from last `EB 09`).
- In HA `sensor.py`: add `SensorEntityDescription` for `battery_level`, device class
  `SensorDeviceClass.BATTERY`, unit `%`, state class `MEASUREMENT`.

---

## 3. Water bowl (DpWater)

> **N/A — no separate BLE implementation needed.**

Inspecting `ble-device-type.json` (the definitive BLE command mapping source): all Du-W* models
(Du-W10B, Du-W11B, Du-W12B, Du-W15B) are `type=0` (FEEDER) with **identical dpMappings to standard
feeders**. They already connect and work as standard feeders via `petnetizen_feeder`.

`DpWater.java` is used by Tuya cloud/WiFi dispatch (cloud DPs, not BLE real_tags). There is no
BLE-specific water bowl device class in the APK's BLE device type registry.

---

## 4. Cat litter box (DpCatLitter)

> **N/A — not a BLE device in this ecosystem.**

`ble-device-type.json` contains only 13 entries (all feeders + TC02); no `type=7` (cat litter) BLE
device is present. `DpCatLitter.java` is Tuya cloud/WiFi dispatch only.

No BLE name prefixes for litter boxes appear in the known device registry. If a BLE litter box is
ever captured with nRF Connect, verify its service UUID and add a new entry.

---

## 5. Camera-enabled feeder DPs

**Source:** `cn/logical/pet/enumeration/DpFeeder.java` entries 21–42 (camera section)

These are present in DpFeeder but missing from `petnetizen_feeder` and the HA integration.
Affects models with built-in camera (e.g. `Du-F*C` suffix or `Du-CAM*`).

| tag | mapping_tag | Entity type | Notes |
|-----|-------------|-------------|-------|
| `motion_switch` | `motion_switch` | `switch` | Motion detection |
| `basic_nightvision` | `basic_nightvision` | `select` | off/auto/on |
| `basic_flip` | `basic_flip` | `switch` | Flip image 180° |
| `motion_sensitivity` | `motion_sensitivity` | `select` | low/medium/high |
| `intercom_switch` | `intercom_switch` | `switch` | Two-way audio |
| `microphone_switch` | `microphone_switch` | `switch` | Microphone enable |
| `direction_control` | `direction_control` | `select` | Pan/tilt direction |
| `stream_video_quality` | `stream_video_quality` | `select` | low/medium/high |

**Also:** `DpCamera.java` (5 DPs, separate enum) contains:
- `stream_url`: RTSP/WS URL returned from device — could expose as HA camera entity
- `recording_switch`: on/off
- `sd_status`: SD card status sensor
- `sd_capacity`: sensor (MB)
- `sd_format`: button

**Implementation plan:**
1. Extend `petnetizen_feeder` to send/receive these cmd bytes (resolve via dpMappings in
   `ble-device-type.json` for camera-model devices).
2. In HA: add `switch.py` entries gated on model having camera capability (check `device_type`
   from BLE name or from `ble-device-type.json` `productModel` field).
3. For `stream_url` (DpCamera): if the device returns a WebSocket URL, implement HA `camera` platform
   using `async_camera_image()` — DO NOT inline HTTP calls, use `aiohttp_client.async_get_clientsession`.

---

## 6. Call Pet intercom (ae00)

**Source:**
- `com/cloudpet/handler/ble/Constant.java` – service `ae00`, write `ae01`, notify `ae02`
- `com/cloudpet/ble/v2/manager/DeviceManager.java` – `isCallPet()` branch routes to ae00

**Protocol:** Same EA/AE framing as feeders: `EA [cmd] [len] [data...] 0x00 AE`.
Notify responses: `EB [cmd] [len] [data...] [crc] AE`.

Command set is different from feeders (no feed plan, etc.). Commands available for Call Pet:
- Connect handshake: real_tags 37 (name+version), 27 (mac), 28 (family_id) — same as V2 devices
- `0x01` – query device status
- `0x02` – intercom call initiate
- `0x03` – intercom accept / answer
- `0x04` – intercom hang up
- `0x05` – play sound/alert
- `0x06` – ring doorbell (one-shot)
- `0x08` – power/charging status query

Exact byte layout must be verified via nRF Connect capture against a real Call Pet device;
the above is inferred from `DpCallPet` enum (not fully decompiled in this session).

**BLE name prefix:** `PET` (already in `SUPPORTED_BLE_NAME_PREFIXES`).

**Implementation plan:**
1. Add `ae00` to `manifest.json` bluetooth filter (see §1).
2. Config-flow: detect service ae00 → set `device_type = "call_pet"`.
3. Create `petnetizen_feeder/call_pet.py` (or new library) with `CallPetDevice` wrapping bleak;
   uses ae01/ae02 characteristics.
4. HA entities: `button` for ring/call, `binary_sensor` for connection status.
5. Two-way audio would require a media player or assist satellite entity — out of scope for v1;
   ship discovery + ring button first.

---

## 7. Aurora Cat (55AA protocol)

**Source:** `com/cloudpet/sdk/utils/BluetoothProtocol.java`

**This is a completely different wire protocol from EA/AE.** Frame format:

```
[0x55] [0xAA] [cmd_hi] [cmd_lo] [len_hi] [len_lo] [data...] [crc16]
```

CRC is CRC-16/IBM over bytes 0..(frame_len-2).

**Service UUID:** `0000ae00-0000-1000-8000-00805f9b34fb` (same as Call Pet — differentiated by BLE
device name prefix: `AURORA` or `TCat` or similar).

**Commands identified in `BluetoothProtocol.java`:**
| cmd (2-byte) | Purpose |
|---|---|
| `0x0001` | LED color (RGB) |
| `0x0002` | Driving speed |
| `0x0003` | Auto mode on/off |
| `0x0004` | Device lock |
| `0x0005` | Query status |
| `0x0006` | Firmware version |

Data payloads are big-endian; length field is 2-byte big-endian.

**BLE name prefix:** `AURORA` or `TC` (verify with nRF Connect scan of actual device).

**Implementation plan:**
1. Add `ae00` to `manifest.json` bluetooth filter (see §1).
2. Config-flow: detect service ae00 + name prefix → route to `device_type = "aurora_cat"`.
3. Create `petnetizen_aurora/` with new `AuroraCatProtocol` implementing the 55AA framing
   (completely separate from `petnetizen_feeder/protocol.py` which does EA/AE).
4. HA entities: `light` (RGB LED), `number` (driving speed), `switch` (auto mode, lock).
5. CRC-16/IBM implementation needed — Python `crcmod` library works: `crcmod.predefined.mkCrcFun('crc-16')`.

> **Warning:** Do not attempt to reuse `petnetizen_feeder/protocol.py` for 55AA devices.
> The frame structures are incompatible. Ship as a separate integration entry in `manifest.json`
> or as a separate HA integration (`netizen_aurora`) to avoid coupling.

---

## 8. DU-CP01B full entities

**Status: Done.** `number.py` and `switch.py` have descriptors gated on `device.device_type == "cp01b"`.
All DPs below are implemented.

| real_tag | mapping_tag | Entity type |
|----------|-------------|-------------|
| `33` | `operation_mode` | `number` (0–5) |
| `2F` | `rotation_mode` | `number` (0–5) |
| `34` | `volume` | `number` (0–100 %) |
| `36` | `prompt_sound` | `switch` (via `cp01b_sound`) |
| `3E` | `fun_mode` | `number` (0–10) |
| `31` | `playback_frequency` | `number` (0–10) |
| `32` | `sound_effect` | `number` (0–10) |
| `35` | `auto_mode_countdown` | `number` (0–60 min) |

---

## 9. DU-F14B sync_time V2 (Done)

**Current state:** F14B connects and maps commands to V2 real_tags. `sync_time` sends standard
6-byte payload `[YY, MM, DD, hh, mm, ss]`.

**Risk:** `BleSyncTimeV2Codec` in the APK (`cn/logical/pet/utils/tuya/codec/spec/BleSyncTimeV2Codec.java`)
may encode time differently (e.g. 4-byte Unix timestamp little-endian, or epoch + TZ offset).

**Action:**
1. Decompile `BleSyncTimeV2Codec.java` fully (run `jadx --no-res` on the APK and read the file).
2. If encoding differs, patch `petnetizen_feeder/protocol.py` `_encode_sync_time_v2()`.
3. Capture nRF Connect log from a real F14B pairing to verify.

**Decompile command:**
```bash
jadx -d /tmp/petnetizen_jadx /tmp/petnetizen_jadx/net.cloudpets.petNetizen.apk \
    --no-res --show-bad-code
cat /tmp/petnetizen_jadx/sources/cn/logical/pet/utils/tuya/codec/spec/BleSyncTimeV2Codec.java
```

---

## Wire protocol reference

### EA/AE (feeders, water, litter, Call Pet)

```
TX: EA [cmd] [len] [data × len] 00 AE
RX: EB [cmd] [len] [data × len] [crc8] AE
```

CRC-8 polynomial: `0x07` (CRC-8/SMBUS). Computed over `[cmd, len, data...]`.

### 55AA (Aurora Cat / Teaser)

```
TX: 55 AA [cmd_hi] [cmd_lo] [len_hi] [len_lo] [data × len] [crc_hi] [crc_lo]
RX: same framing
```

CRC-16/IBM over all preceding bytes.

---

## Discovery and device-class detection

Current `const.py`:

```python
SUPPORTED_BLE_NAME_PREFIXES = ("Du", "JK", "ALI", "PET", "FEED")
SERVICE_UUIDS = {"0000ae30...", "0000fff0...", "0000ffff..."}
```

After implementing the above features, update to:

```python
SUPPORTED_BLE_NAME_PREFIXES = ("Du", "JK", "ALI", "PET", "FEED", "AURORA", "TC")
SERVICE_UUIDS = {
    "0000ae30-0000-1000-8000-00805f9b34fb",  # standard feeder / water / litter
    "0000fff0-0000-1000-8000-00805f9b34fb",  # JK feeder
    "0000ffff-0000-1000-8000-00805f9b34fb",  # ALI feeder
    "0000ae00-0000-1000-8000-00805f9b34fb",  # Call Pet + Aurora Cat/Teaser
}
```

Device-class routing in config-flow should prioritise name prefix over UUID when ae00 is present,
since Call Pet and Aurora Cat share the same service UUID.

---

## 10. Du-TC02 laser cat teaser

**Status: Done.**

Du-TC02 uses EA/AE framing on service UUID `0000ae30` (same as feeders) — **not** the 55AA protocol.
`ble-device-type.json` `type=5` (TOY_CAT) lists real_tags 50–59 for TC02-specific DPs.

**Implemented in:**
- `petnetizen_feeder/protocol.py`: TC02 command constants, decode cases, `set_tc02_dp()`, `set_tc02_color_rgb()`
- `petnetizen_feeder/feeder.py`: `get_tc02_state()`, 9 setter methods
- `netizen_ble/config_flow.py`: `"TC02"` name → `device_type = "tc02"`
- `netizen_ble/device.py`: `query_status()` TC02 block, `_set_tc02()`, 9 setter wrappers
- `netizen_ble/number.py`: `TC02_NUMBERS` list, `async_setup_entry` gate, RGB channel RGB write-through
- `strings.json` / `translations/en.json`: TC02 entity translation keys

| real_tag | key | Entity | Range |
|----------|-----|--------|-------|
| `50` | `tc02_operation_mode` | `number` | 0–5 |
| `51` | `tc02_rotation_mode` | `number` | 0–5 |
| `52` | `tc02_color_r/g/b` | `number` × 3 | 0–255 |
| `53` | `tc02_mood_light_mode` | `number` | 0–10 |
| `54` | `tc02_led_color` | `number` | 0–255 |
| `55` | `tc02_sound_effect` | `number` | 0–10 |
| `56` | `tc02_playback_frequency` | `number` | 0–10 |
| `57` | `tc02_volume` | `number` | 0–100 % |
| `59` | `tc02_auto_countdown_total` | `number` | 0–60 min |
