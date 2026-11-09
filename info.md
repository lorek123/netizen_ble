# Pet Netizen BLE

Home Assistant integration for **Pet Netizen / CloudPets smart feeders** over Bluetooth, using the
[petnetizen_feeder](https://github.com/lorek123/petnetizen_feeder) library. No cloud account or
app login is needed.

## Supported devices

Du-W10B, Du-W11B, Du-W12B, Du-W15B, Du-F03B, Du-F06B, Du-F08B, Du-F09B, Du-F16B, DU-PD01B,
DU-F14B, plus the Du-TC02 and DU-CP01B cat toys. Each model only gets the entities it supports.

## Features

- **Feed now** button with a **Portions** setting, and the `petnetizen_ble.set_feed_plan` action
- **Feeding status**, **Last feed time**, **Feed plan** and **Next feeding** sensors
- **Fault** sensors: any fault, food stuck, food outlet blocked, out of food, low battery
- Settings where the model has them: child lock, prompt sound, LED, auto lock, do not disturb
- Power source (mains / battery)

## Setup

Feeders are discovered automatically through Home Assistant's Bluetooth (local adapter or an
ESPHome Bluetooth proxy on ESPHome 2026.10+). Click **Add** on the discovered device, or use
**Add integration → Pet Netizen BLE** and pick it from the list. Leave the verification code at
`00000000` unless you set a custom one in the Pet Netizen app.
