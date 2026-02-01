# Netizen BLE vs original app – device and feature parity

Comparison against `ble-device-type.json` and app behavior.

## Summary

| Status | Devices | Notes |
|--------|---------|--------|
| **Full parity** | Standard feeders (Du-W*, Du-F* except F14B) | All dpMappings 00–19 + feed plan; 02/60 skipped by design |
| **Full parity** | DU-PD01 (snack) | train_count (0x40), train (0x41) + all feeder features |
| **Full parity** | Du-TC02 (laser) | 0x50–0x59 (operation_mode, rotation_mode, color_rgb, volume, joystick, auto_mode_countdown) + standard |
| **Partial** | DU-F14B | V2 protocol: command mapping (37, 27, 28, 02, 04, 05, 0F, 11, 0A, 0B, 03); decode for 37, 27, 28, 04, 02; sync_time V2 format may differ |
| **Partial** | DU-CP01B (amusement) | V2 protocol: command mapping for connect (37, 27, 28, 08); decode for 33, 2F, 34, 36, 3E; full controls need entity setup |
| **Supported** | JK / Ali | Alternate BLE UUIDs (fff0/fff1/fff2, ffff/ff01/ff02); same EA/AE framing; discovery and connect |

---

## 1. Devices with **full** parity (standard protocol)

All use **service UUID `0000ae30`** and the same **dpMappings** (real_tags 00–19, 60).

| bleName   | productModel | type | Supported |
|-----------|---------------|------|-----------|
| Du-W12B   | Du-W12B       | 0    | Yes       |
| Du-W11B   | Du-W11B       | 0    | Yes       |
| Du-F08B   | Du-F08B       | 0    | Yes       |
| Du-F06    | Du-F06B       | 0    | Yes       |
| Du-F03B   | Du-F03B       | 0    | Yes       |
| Du-F09B   | Du-F09B       | 0    | Yes       |
| Du-F16B   | Du-F16B       | 0    | Yes       |
| Du-W15B   | Du-W15B       | 0    | Yes       |
| Du-W10B   | Du-W10B       | 0    | Yes       |

**Implemented:**  
00 (name_and_version), 04 (query_mac), 05 (sync_time), 06 (set_family_id), 07 (set_feed_plan), 08 (manual_feed), 09 (feed_state), 0A (fault), 0B/0C (feed reports), 0D (child_lock), 0E (power_mode), 0F (led_ctrl), 10 (auto_lock), 11 (query_feed_plan), 12 (prompt_sound), 13 (mood_light), 17 (do_not_disturb_status), 18 (do_not_disturb), 19 (long_ring).

**Intentionally not exposed:**  
02 (up_reset_signal / restore factory), 60 (set_manufacturer_id).

---

## 2. DU-PD01 (snack dispenser) – **full parity**

Same service UUID and same 00–19, 60, **plus**:

| real_tag | mapping_tag   | In netizen_ble |
|----------|---------------|-----------------|
| 40       | train_count   | Yes (sensor)   |
| 41       | train         | Yes (button “Dispense reward” + service) |

- **train_count** sensor; **Dispense reward** button (train status=1, time=6min, times=1).
- Entity filtering: snack-only entities only for devices with name containing DU-PD01.

---

## 3. Du-TC02 (激光逗猫器 / laser toy) – **full parity**

Same service UUID and same 00–19, 60, **plus** 0x50–0x59:

| real_tag | mapping_tag        | In netizen_ble        |
|----------|---------------------|------------------------|
| 50       | operation_mode      | Yes (sensor + number) |
| 51       | rotation_mode       | Yes (sensor + number) |
| 52       | color_rgb           | Yes (device method set_color_rgb) |
| 53       | mood_light_mode     | Yes (device method)   |
| 54       | led_color           | Yes (device method)   |
| 55       | sound_effect        | Yes (device method)   |
| 56       | playback_frequency  | Yes (device method)   |
| 57       | volume              | Yes (sensor + number) |
| 58       | joystick            | Yes (device method set_joystick) |
| 59       | auto_mode_countdown | Yes (sensor + device method) |

- Sensors: operation_mode, rotation_mode, volume, auto_mode_countdown.
- Number entities: volume, operation_mode, rotation_mode.
- Entity filtering: laser entities only for devices with name containing Du-TC02.

---

## 4. DU-F14B – **partial (V2 branch)**

- **Different protocol:** real_tags 37 (name), 27 (mac), 28 (set_family_id), 02 (sync_time), 04 (manual_feed), 05 (child_lock), 0F (led), 11 (auto_lock), 0A (fault), 0B (feed_state), 03 (set_feed_plan), 08 (power), 09 (battery).
- **Implemented:** Command mapping in device (`_real_cmd`) for F14B; protocol decode for 37 (name#version), 27 (mac), 28 (verification), 04 (feed_triggered), 02 (sync_ok). Connect and basic commands use F14B real_tags.
- **Note:** Sync time V2 (BleSyncTimeV2Codec) may use different byte layout; current implementation sends standard 6-byte time.

---

## 5. DU-CP01B (智能逗宠玩具 / amusement) – **partial**

- **Different protocol:** real_tags 37, 27, 28, 08 (power), 09 (battery), 33 (operation_mode), 2F (rotation_mode), 30 (joystick), 35 (auto_mode_countdown), 31 (playback_frequency), 32 (sound_effect), 34 (volume), 36 (prompt_sound), 3E (fun_mode).
- **Implemented:** Command mapping for connect (37, 27, 28, 08); protocol decode for 33, 2F, 34, 36, 3E. Device connects and name/mac/family_id work.
- **Optional:** Add number/switch entities for 33, 2F, 34, 36, 3E when device_type is cp01b (same pattern as Du-TC02).

---

## 6. JK / Ali device types

- **JK:** service UUID `0000fff0`, write `fff2`, notify `fff1`.
- **Ali:** service UUID `0000ffff`, write `ff01`, notify `ff02`.

**Implemented:** Discovery by JK/Ali service UUIDs; config entry stores `device_type` (standard/jk/ali); device uses corresponding write/notify UUIDs and same EA/AE command framing. Same protocol as standard feeders once connected.

---

## Conclusion

- **Full parity** for standard feeders, **DU-PD01** (train_count + train), and **Du-TC02** (0x50–0x59).
- **Partial** for **DU-F14B** (V2 command mapping + decode; sync_time V2 may need adjustment) and **DU-CP01B** (connect + decode; full controls can be added via same entity pattern as laser).
- **JK/Ali** supported with alternate BLE UUIDs and discovery.
