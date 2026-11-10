# Smart Energy Monitoring and Anomaly Detection

Phase 2 adds a Python two-node device simulator and PC Gateway:

`Sensor → application-level ESP-NOW link → Collector → local MQTT → FastAPI/MongoDB`

The real YoloUNO firmware remains buildable. The simulator uses the same v1 binary
layout and MQTT integer-unit contract. **Simulation does not verify ESP-NOW RF,
INA219, physical Wi-Fi or device HTTP.** CoreIOT, AI, a full frontend, load switching
and OTA remain out of scope.

## Quick start — Windows PowerShell

Use Python 3.11+ from the repository root. For a fresh Windows 11 laptop, see
the [Codex setup prompt](docs/windows11-codex-prompt.md).

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r gateway/requirements-dev.txt
Copy-Item gateway/.env.example gateway/.env
```

Install MongoDB Community on a supported Windows host and Mosquitto manually using [gateway setup](docs/gateway-setup.md). No installer,
service or firewall changes are run by this repository. In terminal 1:

```powershell
& 'C:/Program Files/mosquitto/mosquitto.exe' -c ./scripts/mosquitto-local.conf -v
```

Terminal 2:

```powershell
./.venv/Scripts/python.exe -m gateway
```

Terminal 3:

```powershell
./.venv/Scripts/python.exe -m simulator --scenario normal --seed 1
```

Open [API docs](http://127.0.0.1:8000/docs). Once telemetry arrives:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/devices
Invoke-RestMethod http://127.0.0.1:8000/api/devices/node01/telemetry/latest
Invoke-RestMethod http://127.0.0.1:8000/api/devices/node01/telemetry/history
$body = @{command_id='cmd-001'; method='set_sampling_interval'; params=@{interval_ms=2000}} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/devices/node01/commands -ContentType application/json -Body $body
Invoke-RestMethod http://127.0.0.1:8000/api/commands/cmd-001
```

POST initially returns `pending`, not success. Poll until a matching application
ACK produces `success`, failure or timeout. Run only one Collector source
(simulator OR physical board) on `energy/node01/*` at a time.

## Test without hardware or broker

```powershell
./.venv/Scripts/python.exe -m pytest -q
./scripts/test.ps1
./scripts/check-wire-vectors.ps1
python -m platformio run -d firmware -e sensor_node -e collector_node
```

The C++ commands require the existing PlatformIO/MinGW setup; see
[firmware guide](docs/firmware-quickstart.md). For opt-in real-broker tests:

```powershell
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
./.venv/Scripts/python.exe -m pytest -q -m integration
Remove-Item Env:RUN_MQTT_INTEGRATION
Remove-Item Env:RUN_MONGODB_TESTS
```

Use a dedicated local Mosquitto broker with no physical node/simulator running.
Missing broker tests are **SKIPPED/BLOCKED**, never reported as integration PASS.

See [setup/WSL2/troubleshooting](docs/gateway-setup.md),
[MQTT and data contract](docs/mqtt-protocol.md), [simulation scenarios](docs/simulator.md),
[architecture](docs/architecture.md), [test plan](docs/test-plan.md), and
[Phase 2 results](docs/phase2-validation.md).
Existing [firmware protocol](docs/espnow-protocol.md),
[hardware checklist](docs/hardware-validation.md) and
[legacy Modbus implementation](docs/legacy/README.md) are retained.

Persistence is now **MongoDB only**. Set MONGODB_URI and MONGODB_DATABASE in
ignored gateway/.env. The application fails startup if MongoDB is unreachable;
it never falls back to SQLite or memory. Default Python tests inject a mock
explicitly and do not establish real MongoDB persistence. See
[MongoDB migration/status](docs/mongodb-migration.md). This development machine's
Windows 10 is outside current MongoDB Windows support; server installation and
real persistence/integration validation require a supported host.
