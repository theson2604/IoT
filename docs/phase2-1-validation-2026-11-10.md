# Phase 2.1 validation — 2026-11-10 (Asia/Bangkok)

**PARTIAL.** Real MongoDB persistence and Mosquitto command delivery remain blocked.
The earlier [integration report](phase2-1-integration.md) records its own run.

Windows 10, branch `feature/pc-gateway-simulator`, HEAD `e7b6160`, Python 3.12.14
in `.venv`, PyMongo 4.19.0, dnspython 2.9.1, Paho 2.1.0, pytest 9.2.0.
`gateway/.env` and process `MONGODB_URI` were absent. The default MongoDB ping
timed out. No Mosquitto executable, running process, service or reachable listener
was found on the checked paths and `127.0.0.1:1883`.

| Check | Result |
|---|---|
| Real MongoDB ping, isolated insert/read/update/cleanup | **BLOCKED**. Server selection timeout before any write |
| Mosquitto TCP, publish/subscribe and reconnect | **BLOCKED**. No reachable local broker |
| Real telemetry, device state and database indexes | **BLOCKED**. Requires live services |
| Real REST commands, application ACK, negative/duplicate/unknown ACK, timeout and restart persistence | **SKIPPED**. Integration flags require live services |
| Real malformed/repeated/out-of-order telemetry and ACK/timeout race | **BLOCKED**. Mock coverage passed |
| Live MongoDB outage/recovery and physical hardware | **NOT TESTED** |
| Python regression suite | **PASS**. 68 passed, 1 real integration test skipped |
| C++ Modbus and energy suites, five wire vectors | **PASS** |
| Sensor, Collector and legacy builds | **PASS** |
| Dependency check and `git diff --check` | **PASS** |

| Command | Exit | Outcome |
|---|---:|---|
| `.venv/Scripts/python.exe -m pip check` | 0 | Dependencies consistent |
| `.venv/Scripts/python.exe -m scripts.check_integration_services --mongo-crud` | 1 | Both service prerequisites blocked |
| `.venv/Scripts/python.exe -m pytest -q` | 0 | 68 passed, 1 skipped, existing TestClient deprecation warning |
| `.venv/Scripts/python.exe -m pytest -q -m integration` | 0 | 1 skipped, 68 deselected |
| `./scripts/test.ps1` and `./scripts/check-wire-vectors.ps1` | 0 each | C++ and wire checks passed |
| Bundled Python `-m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno` | 1 | PlatformIO module missing from bundled Python |
| Bundled Python `-m venv data/phase21-platformio` | 0 | Workspace build environment created |
| `data/phase21-platformio/Scripts/python.exe -m pip install platformio==6.2.0 --quiet` | 0 | Pinned tooling restored |
| `data/phase21-platformio/Scripts/python.exe -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno` | 0 | All three environments built |
| `git diff --check` | 0 | Whitespace check passed |

Changed `scripts/check_integration_services.py`, `tests/python/conftest.py`,
`tests/python/test_mosquitto_integration.py`, `tests/python/test_mongodb.py`,
`tests/python/test_integration_probe.py` and `docs/gateway-setup.md`. The CRUD probe
uses `energy_integration_probe` and deletes its own UUID-tagged document. The
integration fixture checks that the generated database is empty before use.
The opt-in tests use the loopback broker and verify stored data directly. Hashes
match the previous firmware, simulator, MQTT and REST contracts.

Configure the Atlas database user and current public IP in Atlas, then set
`MONGODB_URI` privately in ignored `gateway/.env`. Install or start the loopback
Mosquitto broker and run the documented publish/subscribe check. The setup guide
includes commands for the CRUD probe, real pytest run, Gateway and Simulator.
Phase 3 waits for both live services and the real end-to-end checks to pass.
[Windows and Atlas setup](gateway-setup.md).
