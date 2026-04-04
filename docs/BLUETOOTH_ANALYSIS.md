# Petnetizen App - Bluetooth Communication Analysis

## Project Structure Overview

The decompiled Petnetizen app uses Bluetooth Low Energy (BLE) for communication with pet devices (feeders, water dispensers, teasers, etc.). The app is written in Kotlin (decompiled to Java) and uses a layered architecture.

### Key Directories

```
app/src/main/java/
├── cn/logical/pet/              # Main app logic
│   ├── bluetooth/               # BLE scanning
│   ├── utils/device/controller/ # Device controllers (feed, water, teaser)
│   ├── p072ui/add/device/ble/  # BLE connection UI
│   └── utils/tuya/codec/spec/  # Protocol codecs
├── com/cloudpet/                # Core BLE SDK
│   ├── ble/                     # BLE connection management
│   │   ├── BleDeviceController.java
│   │   ├── BleDeviceConnectController.java
│   │   └── p079v2/              # BLE v2 implementation
│   ├── handler/ble/             # Protocol handlers
│   └── sdk/                     # SDK base classes
```

## Bluetooth Communication Architecture

### 1. Scanning Phase

**BleScanManager** (`cn.logical.pet.bluetooth.BleScanManager.java`)
- Manages BLE device scanning
- Handles permissions (BLUETOOTH_SCAN)
- Uses `Cloudpet.INSTANCE.startScan()` for actual scanning
- Listens for scan results via `ScanControllerListener`

### 2. Connection Phase

**BleDeviceConnectController** (`com.cloudpet.ble.BleDeviceConnectController.java`)
- Handles initial device pairing/connection
- Manages connection lifecycle (connect, disconnect, reconnect)
- Sends initial commands (verification code, family ID)
- Processes device responses during pairing

**BleDeviceController** (`com.cloudpet.ble.BleDeviceController.java`)
- Manages ongoing device communication after pairing
- Handles device state (online/offline)
- Sends commands and receives responses
- Manages connection callbacks

### 3. Protocol Layer

**DataHandler** (`com.cloudpet.handler.ble.DataHandler.java`)
- Encodes/decodes BLE commands
- Handles time synchronization
- Parses command packets
- Uses `CodecKt` for actual encoding/decoding

**Codec Classes** (`cn.logical.pet.utils.tuya.codec.spec/`)
- `BleFeederScheduleCodec` - Feeding schedule encoding
- `BleSyncTimeCodec` / `BleSyncTimeV2Codec` - Time sync
- `BleNameAndVersionCodec` - Device info
- `BleSpecBooleanManualFeedCodec` - Manual feeding
- Many more device-specific codecs

### 4. Device Controllers

**CPBleFeedDeviceController** (`cn.logical.pet.utils.device.controller.feed.CPBleFeedDeviceController.java`)
- High-level controller for feeder devices
- Manages feeding plans, schedules
- Handles device state and UI updates
- Wraps `BleDeviceController` for actual BLE communication

## Communication Flow

### Pairing Flow
1. User initiates scan → `BleScanManager.scan()`
2. Device found → `ScanControllerListener` callback
3. Connect to device → `BleDeviceConnectController.connectBleDevice()`
4. BLE connection established → `BleConnectManager` via `BaseBleManager`
5. Device ready → Send verification code/family ID
6. Device responds → Parse response, complete pairing

### Command Flow
1. App action (e.g., feed pet) → `CPBleFeedDeviceController.feed()`
2. Encode command → `BleDeviceControllerListener.encoder()`
3. Send via BLE → `BleConnectManager.send()`
4. Device responds → `BleConnectCallback.onMessage()`
5. Decode response → `BleDeviceControllerListener.decoder()`
6. Update UI → Device controller callbacks

## Key Components

### BLE Permissions (AndroidManifest.xml)
```xml
<uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30"/>
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30"/>
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" android:usesPermissionFlags="neverForLocation"/>
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>
<uses-permission android:name="android.permission.BLUETOOTH_ADVERTISE"/>
<uses-feature android:name="android.hardware.bluetooth_le" android:required="true"/>
```

### Core Classes

1. **BleConnectManager** - Singleton managing all BLE connections
2. **BaseBleManager** - Base class for device-specific BLE managers
3. **DeviceManager** - Device-specific BLE manager implementations
4. **BleConnectCallback** - Callback interface for connection events
5. **BleDeviceControllerListener** - Protocol encoder/decoder interface

## Protocol Details

### Command Format
Commands appear to use a hex-encoded format with:
- Command ID (e.g., "00", "06", "07", "0C")
- Length field
- Data payload (hex-encoded)

### Example Commands
- `"00"` - Query name and version
- `"06"` - Query offline data count
- `"07"` - Query specific offline data
- `"0C"` - Set threshold (for call pet devices)

### Verification Flow
1. Device connects
2. App sends verification code (8 hex digits, default "00000000")
3. Device validates and responds
4. If valid, pairing succeeds

## Jadx Export Issues

### 1. Decompilation Errors

Several files contain decompilation issues marked with:
```
Code decompiled incorrectly, please refer to instructions dump.
To view partially-correct code enable 'Show inconsistent code' option in preferences
```

**Affected Files:**
- `CPBleFeedDeviceController.java` - Multiple methods (lines 176, 368, 509)
- `DeviceBleConnectActivity.java` - `onKeyDown()` method (line 49)
- `BleDeviceConnectController.java` - Some coroutine methods

**Recommendations:**
1. Enable "Show inconsistent code" in Jadx preferences
2. Use Jadx with `--show-bad-code` flag
3. Consider using alternative decompilers for problematic methods
4. Some methods may need manual reconstruction from bytecode

### 2. Obfuscated Names

Many classes use obfuscated names:
- `o0000oO0`, `o0O00`, `o0OoO00O` - Anonymous inner classes
- `OooO0o`, `OooOOOO` - EventBus methods
- `f8972OooO00o` - Constants

**Recommendation:**
- These are likely from Kotlin coroutines and library code
- Not critical for understanding Bluetooth communication
- Focus on `com.cloudpet.ble` and `cn.logical.pet.bluetooth` packages

### 3. Missing Source Information

Some files reference Kotlin source files:
```
@SourceDebugExtension({"SMAP\nBleDeviceController.kt\nKotlin\n...
```

**Recommendation:**
- Original code was Kotlin, decompiled to Java
- Some Kotlin-specific features may not translate perfectly
- Coroutines are converted to callback-based code

### 4. Incomplete Method Bodies

Some methods show incomplete decompilation:
```java
/* JADX WARN: Code restructure failed: missing block: B:20:0x0077, code lost: */
```

**Recommendation:**
- Use Jadx's "Export as Gradle project" to get better decompilation
- Try different Jadx versions
- Some control flow may be lost but logic should be recoverable

## Key Files for Bluetooth Analysis

### Essential Files:
1. `com/cloudpet/ble/BleDeviceController.java` - Main device controller
2. `com/cloudpet/ble/BleDeviceConnectController.java` - Pairing controller
3. `com/cloudpet/ble/p079v2/BleConnectManager.java` - Connection manager
4. `com/cloudpet/ble/p079v2/manager/DeviceManager.java` - Device manager
5. `com/cloudpet/handler/ble/DataHandler.java` - Protocol handler
6. `cn/logical/pet/bluetooth/BleScanManager.java` - Scanning
7. `cn/logical/pet/utils/device/controller/feed/CPBleFeedDeviceController.java` - Feeder controller

### Protocol Codecs:
- `cn/logical/pet/utils/tuya/codec/spec/BleFeederScheduleCodec.java`
- `cn/logical/pet/utils/tuya/codec/spec/BleSyncTimeCodec.java`
- `cn/logical/pet/utils/tuya/codec/spec/BleNameAndVersionCodec.java`

## Recommendations for Further Analysis

1. **Enable Jadx Bad Code Display**: Use `--show-bad-code` flag to see problematic sections
2. **Focus on Core Packages**: `com.cloudpet.ble` and `com.cloudpet.handler.ble` contain the main logic
3. **Trace Command Flow**: Start from UI actions → Controllers → BLE send → Device response
4. **Analyze Codecs**: The codec classes show the actual protocol format
5. **Check Native Libraries**: Some BLE logic might be in `.so` files in `lib/arm64-v8a/`

## Notes

- The app uses Nordic Semiconductor's BLE library (`no.nordicsemi.android.ble`)
- Communication is encrypted/authenticated via verification codes
- Devices support multiple firmware versions (handled by version-specific codecs)
- The protocol appears to be custom, not standard BLE GATT services
