# Smart Energy Monitoring and Anomaly Detection

Firmware MVP: YoloUNO Sensor (INA219 or labelled mock) → ESP-NOW → YoloUNO
Collector → Wi-Fi/local MQTT broker. Collector provides a read-only HTTP server.
PC Gateway, broker deployment, AI, dashboard, CoreIOT and OTA are out of scope.
Existing gateway/dashboard scaffolds remain unchanged.

Both roles use the existing vendor `yolo_uno` board and Arduino configuration.
Modbus/Waveshare is preserved in a legacy environment, **not part of current MVP**.
No real load control or LED actuation is implemented.

## Configuration

Copy `firmware/include/local_config.example.h` to `firmware/include/local_config.h`
(Git ignored). Set actual opposite STA MACs from the boards' serial logs:
COLLECTOR_MAC on Sensor, SENSOR_MAC on Collector. No MAC is prefilled.
Set Wi-Fi credentials, MQTT host/port and optional MQTT user/password on Collector.
Blank config builds but does not connect to a network or guessed peer.
Set SENSOR_CHANNEL to the AP's actual 2.4GHz channel. Collector connects first
and uses that AP channel; it never forces another channel while associated.

USE_MOCK_SENSOR=1 is default: readings always have SIMULATED status 1.
For real INA219, use 0, verify address straps and configure the actual
INA219_SHUNT_MILLIOHMS. Zero shunt configuration reports SENSOR_ERROR.
I2C uses vendor SDA/SCL symbols, not guessed pins.

## Build and test

PowerShell from repository root, with Python 3:

```powershell
python -m pip install platformio==6.2.0
python -m platformio run -d firmware -e sensor_node
python -m platformio run -d firmware -e collector_node
python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32
./scripts/test.ps1
```

From `firmware/`, equivalent commands are `pio run -e sensor_node` and
`pio run -e collector_node`. `pio run` builds both default roles.
The tests compile the real shared C++ code with mock radio, sensor and broker.
They do not verify physical radio/I2C or a running broker.

When hardware becomes available (nothing has been flashed):

```powershell
python -m platformio device list
python -m platformio run -d firmware -e sensor_node -t upload --upload-port COMx
python -m platformio run -d firmware -e collector_node -t upload --upload-port COMy
python -m platformio device monitor -d firmware --port COMx --baud 115200
```

Identify actual ports first. Initial upload may need BOOT + RESET.
Collector logs its IP/channel/MAC; open its IP at `/`, `/api/status`,
`/api/telemetry`, `/api/diagnostics`. No POST endpoint exists.
Sensor logs sampling/status, packet counts, sensor errors and ACK queue count every 5s.

## MQTT contract

| Topic | Direction | Payload |
|---|---|---|
| energy/node01/telemetry | Collector → broker | JSON integer voltage_mv/current_ma/power_mw/energy_mwh/sensor_status/sequence_number |
| energy/node01/state | Collector → broker | retained online/connection snapshot and disconnect LWT |
| energy/node01/command | broker → Collector | command schema below |
| energy/node01/ack | Collector → broker | command_id, result, code |
| energy/node01/event | Collector → broker | errors/rejections/connection events |

Example: `{"command_id":1,"command_type":1,"command_parameter":1000}`.
Type 1 sets interval (100–60000ms); type 2 requests status (parameter 0).
Use a new uint32 ID for each command; only one may be pending. Accepted commands
produce a correlated acknowledged/timeout result. Code 0=OK, 1=invalid parameter,
2=unsupported, 3=ID conflict; timeout code=-1. Timeout does not prove non-execution.
Malformed/busy/offline/duplicate commands produce an event and are not forwarded.
SET_LOCAL_LED is reserved/unsupported and rejected at MQTT.

This is a trusted-lab implementation: local plaintext MQTT/QoS0, MAC allowlisting
but unencrypted ESP-NOW. CRC is not authentication. Configure broker ACLs, do not
retain commands, and keep the interface on a trusted LAN. Encryption/TLS and
provisioning are future hardening work. No credentials are committed.

See [architecture](docs/architecture.md), [protocol](docs/espnow-protocol.md),
[hardware](docs/hardware.md), [bring-up](docs/hardware-validation.md),
[test plan](docs/test-plan.md), [acceptance matrix](docs/scoring-matrix.md),
and [executed results](docs/migration-validation.md).
**Every hardware test remains UNVERIFIED.**
Previous work: [legacy Modbus README](docs/legacy/README.md).
