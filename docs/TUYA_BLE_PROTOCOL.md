# Tuya BLE Protocol Discovery

## Overview

The Petnetizen feeder uses a protocol inspired by **Tuya BLE**. This was discovered by analyzing the decompiled Android app code, specifically the `BleProtocol.blufiCommand()` method.

## Protocol Format

### Commands (App → Device)
- **Header**: `0xEA` (234) - Different from notifications
- **Footer**: `0xAE` (174) - Same as notifications
- **Format**: `EA + Command + Length + Data + CRC(00) + AE`

### Notifications (Device → App)
- **Header**: `0xEB` (235) - Different from commands
- **Footer**: `0xAE` (174) - Same as commands
- **Format**: `EB + Command + Length + Data + CRC + AE`

## Code Reference

From `app/src/main/java/cn/logical/pet/bluetooth/BleProtocol.java`:

```java
public final byte[] blufiCommand(@NotNull String command, @NotNull String action) {
    byte[] bytes = action.getBytes(Charsets.UTF_8);
    int length = bytes.length;
    ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
    byteArrayOutputStream.write(234);  // 0xEA header
    byteArrayOutputStream.write(Integer.parseInt(command, 16));  // Command byte
    byteArrayOutputStream.write(length);  // Length byte
    byteArrayOutputStream.write(bytes, 0, length);  // Data bytes
    byteArrayOutputStream.write(0);  // CRC placeholder (0x00)
    byteArrayOutputStream.write(174);  // 0xAE footer
    return byteArrayOutputStream.toByteArray();
}
```

## Example Commands

### Feed Command
- **Command**: `08` (FEEDING)
- **Length**: `01`
- **Data**: `01` (1 portion)
- **Full**: `EA 08 01 01 00 AE`

### Verification Code (SET_FAMILY_ID)
- **Command**: `06` (SET_FAMILY_ID)
- **Length**: `04`
- **Data**: `00000000` (4 bytes, default verification code)
- **Full**: `EA 06 04 00 00 00 00 00 AE`

### Query Name/Version
- **Command**: `00` (NAME_AND_VERSION)
- **Length**: `00`
- **Data**: (none)
- **Full**: `EA 00 00 00 AE`

## Example Notifications

From nRF Connect logs:

### Child Lock Status
- **Raw**: `EB 0D 01 01 00 AE`
- **Decoded**: 
  - Header: `EB`
  - Command: `0D` (CHILD_LOCK)
  - Length: `01`
  - Data: `01` (locked)
  - CRC: `00`
  - Footer: `AE`

### Feed Response
- **Raw**: `EB 08 01 01 00 AE`
- **Decoded**:
  - Header: `EB`
  - Command: `08` (FEEDING response)
  - Length: `01`
  - Data: `01` (acknowledged)
  - CRC: `00`
  - Footer: `AE`

## CRC Calculation

Currently, the protocol uses `0x00` as a CRC placeholder in commands. However, some codecs in the app use `SystemUtils.calculateCrc()` for certain commands. The CRC calculation may be:
- Simple XOR of all bytes (as seen in `SenderCommand.getCrcHex()`)
- Or a more complex algorithm for specific commands

For now, `0x00` works for most commands, but CRC calculation may need to be implemented for full compatibility.

## Related Resources

- Tuya BLE Protocol: https://github.com/PlusPlus-ua/ha_tuya_ble
- Tuya Developer Documentation: https://developer.tuya.com/en/docs/iot/device-development/access-mode-mcu/ble-mesh-general-solution/tuya-universal-serial-port-protocol

## Key Differences from Standard BLE

1. **Header Byte**: Commands use `EA`, notifications use `EB`
2. **CRC**: Currently `0x00` placeholder, but may need calculation
3. **Length Byte**: Always present, indicates data length
4. **Footer Byte**: Always `AE` for both commands and notifications

## Implementation Status

✅ Command encoding updated to use `EA` header  
✅ Notification decoding already handles `EB` header  
✅ CRC placeholder (`0x00`) implemented  
⚠️ CRC calculation may need implementation for some commands  
⚠️ Action data encoding (UTF-8 vs hex) may vary by command type
