# Tests

`./scripts/test.ps1` compiles existing Modbus tests unchanged and new energy tests
using real shared headers, g++ C++11 and -Wall -Wextra -Werror. MinGW ANSI stdio
is enabled for uint64 JSON formatting. MockEnergySensor/MockRadio/MockMqtt exercise
sensor state, retries and the actual shared MQTT forwarding function.

Coverage: wire golden header/signed fields/all types; every single-bit telemetry
corruption; truncated/extra length, wrong version/type/payload/status; duplicate/
stale/wrapping sequence; interval bounds; cache/id conflict/status/unsupported LED;
wrong/negative/late ACK; timeout/bounded retry/clock wrap; INA conversion,
positive energy/fractions/error gaps/wrap; mock error reporting; MQTT topic/payload
and failed publish propagation.

Build with `python -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno`.
Real INA compile is additionally run with USE_MOCK_SENSOR=0 (validation record).
Physical radio, FreeRTOS timing, I2C, HTTP and real broker integration require
hardware-validation.md; host mocks do not establish hardware PASS.

Baseline: clean branch feature/espnow-energy-monitoring at a48ff91;
Modbus host tests PASS and original yolo_uno firmware PASS before edits.
Current runtime lacked PlatformIO initially; installed version 6.2.0 and then
baseline build passed. Git was neither reinitialized nor committed.

## Phase 2 Python tests

```powershell
./.venv/Scripts/python.exe -m pytest -q
./scripts/check-wire-vectors.ps1
```

Unit tests cover strict telemetry/command/ACK validation, explicit unit conversion,
null sensor-error values, MongoDB queries/retention/pagination/restart, status
freshness/retained snapshots, MQTT topic routing/bounded queues/reconnect
resubscription, API command ID mapping/dedup/conflict/ACK/timeout/publication failure,
all scenarios, deterministic loss/delay/duplicates/out-of-order frames, energy
integration/error gaps, node/broker disconnections and REST/OpenAPI responses.
C++ generated vector fixtures check Python wire parity for all five types.

Real integration is deliberately opt-in on a dedicated local Mosquitto broker:

```powershell
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
./.venv/Scripts/python.exe -m pytest -q -m integration
Remove-Item Env:RUN_MQTT_INTEGRATION
Remove-Item Env:RUN_MONGODB_TESTS
```

That test uses actual Paho clients: Simulator → MQTT → Gateway → MongoDB/REST,
then REST → MQTT → simulated Sensor → ACK → Gateway. Once opted in, missing
broker causes FAIL rather than silently falling back to memory. Without opt-in,
the test is SKIPPED, and does not count as real-broker PASS. Stop other simulators
and physical nodes before running it (fixed node01 topics).

No broker was installed in the Phase 2 execution environment; see phase2-validation.md.
No actual boards, INA219 or ESP-NOW RF are tested by Python. Build tests and
C++ memory tests remain separate from hardware-validation.md.

## MongoDB migration tests

Default pytest uses explicitly injected mongomock clients, not a runtime fallback.
Set RUN_MONGODB_TESTS=1 to run the same persistence tests against a real MongoDB
server. Tests generate only energy_test_<32-hex-UUID> databases and drop precisely
the database created by their fixture. Use a dedicated test server/credential.
Never point tests at production. Both RUN_MONGODB_TESTS=1 and
RUN_MQTT_INTEGRATION=1 are required for real MQTT + MongoDB integration; opted-in
connection failure is an error, never a mock fallback. Tests cover atomic ACK
races, unique command IDs/pending slots, counters, persistence/restart, invalid
documents, connection/HTTP 503 failure, and read-only legacy migration/backups.
See mongodb-migration.md for current results and SQLite reference classification.
