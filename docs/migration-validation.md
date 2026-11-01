# Firmware migration validation — 2026-11-01 (Asia/Bangkok)

## Baseline and final results

Baseline branch `feature/espnow-energy-monitoring`, HEAD `a48ff91`, clean tree.
Existing Modbus tests and original firmware build passed before edits.

| Check | Final result |
|---|---|
| Existing Modbus host tests | PASS |
| Shared energy protocol/runtime tests | PASS |
| Sensor default mock build | PASS |
| Collector build | PASS |
| Legacy yolo_uno build | PASS |
| Real INA219 mode, zero-shunt error configuration | PASS (compile only) |
| Real INA219 mode with synthetic 100mOhm compile fixture | PASS (compile only) |
| Vendor board/variant and legacy byte preservation | PASS |
| git diff --check | PASS |
| Git branch/HEAD preserved, no commits | PASS |
| Physical ESP-NOW, I2C, Wi-Fi/MQTT/HTTP interoperability | UNVERIFIED / BLOCKED: hardware unavailable |

No hardware was discovered, flashed or tested during migration. No radio PASS
is inferred from mocks. The 100mOhm fixture is a compiler exercise only, NOT a
claim about the user's breakout. Default real shunt configuration remains zero;
default firmware remains labelled mock mode. Final default build restored after
real-path compile checks.

Early compile failures (Collector publish access modifier and host MinGW uint64
printf formatting) were fixed; final builds/tests pass. PlatformIO 6.2.0 was
installed in current runtime because it initially was missing. No board definition
changes were used to resolve failures.

## Commands actually executed

PowerShell, repository root `G:/slides/261/IOT/Project`:

```powershell
$python = 'C:/Users/theso/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python -m pip install platformio==6.2.0
./scripts/test.ps1
# Before migration, original baseline:
& $python -m platformio run -d firmware
# Migrated environments:
& $python -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno
# Real path, zero-shunt error configuration:
$env:PLATFORMIO_BUILD_FLAGS='-DARDUINO_USB_CDC_ON_BOOT=1 -DNODE_ROLE_SENSOR -DUSE_MOCK_SENSOR=0'
& $python -m platformio run -d firmware -e sensor_node
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
# Synthetic nonzero-shunt compile fixture, never a physical measurement:
$env:PLATFORMIO_BUILD_FLAGS='-DARDUINO_USB_CDC_ON_BOOT=1 -DNODE_ROLE_SENSOR -DUSE_MOCK_SENSOR=0 -DINA219_SHUNT_MILLIOHMS=100'
& $python -m platformio run -d firmware -e sensor_node
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
# Restore defaults:
& $python -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno
git diff --check
git check-ignore firmware/include/local_config.h
```

Host tests use installed MinGW g++ 5.1, C++11, -Wall -Wextra -Werror and
-D__USE_MINGW_ANSI_STDIO=1. The existing Modbus assertions are unchanged. New tests
exercise shared codec/runtime/forwarding with mock radio/sensor/MQTT. New code was
formatted using clang-format; no legacy/vendor formatting was changed.

## Preservation evidence

Byte comparison against Git HEAD passed for board JSON, variant, Modbus core,
Modbus tests, gateway/main.py, dashboard/README.md and docs/references.md.
Moved entrypoint src/legacy/main.cpp matches original src/main.cpp bytes.
Archived README/hardware/verification/references match committed baseline bytes.

Vendor board SHA256: d7520ff49a1b9fa4dfc9b8c4e52e458eb540bc51d828eaa9241354261c61dc22

Vendor variant SHA256: 9807bf0015cae75b1346a63cf07c5160c25d1cd111c82e1efa019dadbe340b4a

## Required configuration and next phase

Fill ignored local_config.h with actual peer STA MACs, Wi-Fi and local broker
settings. Match Sensor channel to AP channel. Real sensing requires confirmed
INA address/shunt/safe power/wiring. No credentials or actual peer MACs were added.
Run hardware-validation.md next with mock mode first, then instrument-checked real
INA219. LED/load control, encrypted pairing/TLS, persistent session identities,
energy persistence and PC Gateway/AI/CoreIOT remain future work.

## File manifest

Moved without content changes: firmware/src/main.cpp → firmware/src/legacy/main.cpp.

Modified: .gitignore, README.md, docs/hardware.md, docs/verification.md (historical
banner only), firmware/platformio.ini, scripts/test.ps1.

Created:
- `docs/architecture.md`
- `docs/espnow-protocol.md`
- `docs/hardware-validation.md`
- `docs/legacy/README.md`
- `docs/legacy/hardware.md`
- `docs/legacy/references.md`
- `docs/legacy/verification.md`
- `docs/scoring-matrix.md`
- `docs/test-plan.md`
- `firmware/include/Config.h`
- `firmware/include/INA219EnergySensor.h`
- `firmware/include/Radio.h`
- `firmware/include/local_config.example.h`
- `firmware/lib/Energy/Protocol.h`
- `firmware/lib/Energy/Runtime.h`
- `firmware/src/collector/main.cpp`
- `firmware/src/legacy/main.cpp`
- `firmware/src/sensor/main.cpp`
- `tests/energy_test.cpp`
- `docs/migration-validation.md` (this report)
