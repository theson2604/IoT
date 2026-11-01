# Smart Energy Monitoring and Load Control

Phase 0–1: ESP32-S3 YoloUNO → isolated RS485 → Waveshare Modbus RTU IO 8CH.
Future: PC local gateway → CoreIOT. INA219, AI, cloud integration and OTA are deferred.

## Repository

- `firmware/`: Arduino firmware, vendor YoloUNO board and variant, portable C++ Modbus core.
- `gateway/`: inert Python CLI scaffold.
- `dashboard/`: future UI placeholder.
- `docs/`: wiring, provenance, hardware verification and test results.
- `scripts/`: host test runner.
- `tests/`: mock device tests using the actual firmware Modbus core.

## Build and test (PowerShell, from repository root)

Install Python 3 and put it on PATH, then:

```powershell
python -m pip install platformio==6.2.0
python -m platformio run -d firmware
python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32
./scripts/test.ps1
python gateway/main.py --version
python -m platformio device list
python -m platformio run -d firmware -t upload --upload-port COMx
python -m platformio device monitor -d firmware --port COMx --baud 115200
```

Replace COMx with the observed board port. Initial upload may require BOOT + RESET.
No hardware was flashed during automated development.

## Safety and operation

`SAFE_DIAGNOSTIC_MODE=1` is the source default. No FC05 is sent at boot,
periodically, on reconnect, or in response to malformed console input. No automatic
OFF is sent either: existing external output state is not changed by startup.
With confirmed direction pins configured, FC01 and FC02 run every 5 seconds.
Until then firmware logs `ready=0` and refuses bus operations.

Console commands (newline terminated, case sensitive):

```text
read do
read di
do1 on CONFIRM
do1 off CONFIRM
```

Both write commands return Blocked in diagnostic mode. To bench-test writes,
add `-DSAFE_DIAGNOSTIC_MODE=0` to `build_flags`, retaining USB flags and adding
`-DRS485_DE_GPIO=<verified integer>` and `-DRS485_RE_GPIO=<verified integer>`.
These are required local wiring selections, not suggested GPIO mappings.
Use separate DE and /RE GPIOs. Check that selected pins are exposed, output capable,
and do not conflict with USB, flash, PSRAM, boot straps or other peripherals.
Rebuild and flash deliberately. Only an explicit command can change DO1 via firmware.
The external device must also be in normal control mode; linkage/pulse modes can
change outputs independently. Disconnect real loads before commissioning.

Protocol defaults: slave 1, 9600 8N1, 300ms response deadline, up to three total
attempts on timeout/CRC/frame errors. Exceptions stop retries. FC05 retries only
absolute ON/OFF values, never toggle. Lost write acknowledgements can mean the
write happened; a failed result does not prove the output is OFF. Each acknowledged
write requires FC01 readback; mismatch or read failure is an error. Status bits are
logical device state, not measured load voltage/current.

Error numbers in logs: 0 OK, 1 timeout, 2 CRC, 3 frame, 4 exception,
5 blocked, 6 argument, 7 readback mismatch. Exception byte is logged separately.

See [wiring](docs/hardware.md), [verification](docs/verification.md) and
[source provenance](docs/references.md). All physical tests remain UNVERIFIED.
