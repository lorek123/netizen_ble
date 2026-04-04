# Protocol Variant Detection

This document explains how the Petnetizen app detects which BLE protocol variant (standard, JK, or Ali) to use for a device.

## Detection Flow

The app uses a multi-step process to determine the device type and protocol variant:

### 1. Initial Detection (During Scan/Connection)

When a BLE device is discovered, the app attempts to identify it using:

**Primary Method: Device Name Matching**
```java
// From BleDeviceConnectController.getDeviceType()
DeviceType deviceType = DeviceControllerExtend.getDeviceTypeByName(
    bluetoothDevice.getName(), null);
```

**Fallback Method: Scan Record Parsing**
If device name is not available or doesn't match, the app parses the BLE scan record:
```java
// Extract shortened local name from scan record
String shortenedName = DeviceControllerExtend.resolveShortenedLocalName(
    hexUtils.encodeHexStr(scanRecord), 0);
DeviceType deviceType = DeviceControllerExtend.getDeviceTypeByName(
    shortenedName, null);
```

### 2. Device Type Matching

The `getDeviceTypeByName()` method works as follows:

1. **Check Cache**: First checks a cached device type map
2. **Iterate Device Types**: Loops through all known device types
3. **Match BLE Names**: For each device type, checks if the device name **starts with** any of the device type's `bleNames`:
   ```java
   for (String bleName : deviceType.getBleNames()) {
       if (deviceName.startsWith(bleName)) {
           return deviceType;  // Match found!
       }
   }
   ```

### 3. Protocol Variant Selection

Once the `DeviceType` is determined, the app checks specific properties to select the protocol variant:

#### JK Devices
```java
// From DeviceControllerExtend.isJKDevice()
boolean isJK = (deviceType.getModule() == Module.JIAKE.getCode());
```
- **UUIDs**: Uses JK-specific UUIDs (`0000fff0`, `0000fff2`, `0000fff1`)
- **Detection**: Based on `module` property = `Module.JIAKE`

#### Ali Devices
```java
// From DeviceControllerExtend.isAliCommunication()
boolean isAli = (deviceType.getCommunication() == Communication.ALI_IOT.getCode());
```
- **UUIDs**: Uses Ali-specific UUIDs (`0000ffff`, `0000ff01`, `0000ff02`)
- **Detection**: Based on `communication` property = `Communication.ALI_IOT`

#### Standard Devices
- **UUIDs**: Uses standard UUIDs (`0000ae30`, `0000ae01`, `0000ae02`)
- **Detection**: Default for feeders that are neither JK nor Ali

### 4. UUID Selection (in DeviceManager)

The actual UUIDs are selected in `DeviceManager` based on device type checks:

```java
// Service UUID selection
if (isFeeder(deviceType)) {
    if (isJKDevice(deviceType)) {
        return "0000fff0-0000-1000-8000-00805f9b34fb";  // JK
    }
    if (isAliCommunication(deviceType)) {
        return "0000ffff-0000-1000-8000-00805f9b34fb";  // Ali
    }
    return "0000ae30-0000-1000-8000-00805f9b34fb";     // Standard
}
```

## DeviceType Properties

Each `DeviceType` object contains:

- **`bleNames`**: List of BLE device name prefixes to match (e.g., `["CP", "PetFeeder"]`)
- **`module`**: Module code (e.g., `Module.JIAKE`, `Module.CLOUD_PET`)
- **`communication`**: Communication protocol (e.g., `Communication.ALI_IOT`)
- **`index`**: Unique device type index
- **`productId`**: Product identifier
- **`params`**: Device-specific parameters

## Scan Record Parsing

The `resolveShortenedLocalName()` method parses BLE scan records to extract the device name:

1. **Parse AD Structure**: Looks for AD type `0x08` (Shortened Local Name)
2. **Extract Length**: Reads length byte
3. **Extract Name**: Converts hex bytes to UTF-8 string
4. **Recursive Search**: If not found, continues searching through the scan record

Format in scan record:
```
[Length][AD Type 0x08][Name Bytes]
```

## Example Detection Flow

```
1. Device discovered: "CP-Feeder-1234"
   ↓
2. getDeviceTypeByName("CP-Feeder-1234")
   ↓
3. Check bleNames for each DeviceType:
   - DeviceType A: bleNames = ["CP"] → MATCH! (starts with "CP")
   ↓
4. Get DeviceType properties:
   - module = Module.CLOUD_PET
   - communication = Communication.BLE
   ↓
5. Check protocol variant:
   - isJKDevice() → false (module != JIAKE)
   - isAliCommunication() → false (communication != ALI_IOT)
   → Use STANDARD protocol
   ↓
6. Select UUIDs:
   - Service: 0000ae30-0000-1000-8000-00805f9b34fb
   - Write: 0000ae01-0000-1000-8000-00805f9b34fb
   - Notify: 0000ae02-0000-1000-8000-00805f9b34fb
```

## Key Code Locations

### Device Type Detection
- **`BleDeviceConnectController.getDeviceType()`** (line 573)
  - Primary detection logic
  - Tries device name first, then scan record

- **`DeviceControllerExtend.getDeviceTypeByName()`** (line 362)
  - Core matching algorithm
  - Matches device name against `bleNames` list

- **`DeviceControllerExtend.resolveShortenedLocalName()`** (line 915)
  - Parses BLE scan record
  - Extracts shortened local name

### Protocol Variant Checks
- **`DeviceControllerExtend.isJKDevice()`** (line 827)
  - Checks if `module == Module.JIAKE`

- **`DeviceControllerExtend.isAliCommunication()`** (line 723)
  - Checks if `communication == Communication.ALI_IOT`

### UUID Selection
- **`DeviceManager.getServiceUUID()`** (line 122)
- **`DeviceManager.getWriteUUID()`** (line 163)
- **`DeviceManager.getNotifyUUID()`** (line 81)

## Implications for Python PoC

To implement automatic protocol detection in the Python script:

1. **Scan for devices** and get device names
2. **Match device name** against known prefixes (would need device type database)
3. **Check device properties** (if available) to determine module/communication
4. **Select appropriate UUIDs** based on detection

**Alternative Approach:**
- Try each protocol variant in order (standard → JK → Ali)
- Use the one that successfully connects and responds

**Simplest Approach:**
- Let user specify device type manually
- Or try all variants automatically until one works

## Device Type Database

The app maintains a database of device types with their properties. This is likely:
- Loaded from server/API
- Stored in app configuration
- Contains mappings like:
  ```json
  {
    "index": 1,
    "name": "Standard Feeder",
    "bleNames": ["CP", "PetFeeder"],
    "module": 1,  // CLOUD_PET
    "communication": 1,  // BLE
    "type": 1  // FEEDER
  }
  ```

Without access to this database, the Python PoC would need to:
- Use heuristics (device name patterns)
- Try multiple protocols
- Allow manual specification

## Summary

The app detects protocol variants through:
1. **Device name matching** against a `bleNames` list
2. **Scan record parsing** as fallback
3. **Property checking** (`module` for JK, `communication` for Ali)
4. **UUID selection** based on device type properties

The detection happens **before connection**, allowing the app to use the correct UUIDs from the start.
