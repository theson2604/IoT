# Phase 2.1 integration report — 2026-11-01 (Asia/Bangkok)

**PARTIAL — completion criteria NOT met. Phase 3 integration should wait.**

## Verified service state

- Windows 10; no unsupported MongoDB Community installation attempted.
- No gateway/.env, process MONGODB_URI, or Atlas credentials configured.
  Effective MongoDB URI is the default localhost; Atlas cluster/IP authorization
  cannot be inspected without user configuration. No Atlas account action taken.
- Configured MongoDB ping: BLOCKED, ServerSelectionTimeoutError.
- Local TCP 27017/1883 unavailable; Mosquitto absent from PATH, standard location
  and matching Windows services. No usable existing service found.
- No credentials/tokens created, displayed or committed; no application DB writes,
  firewall/service changes, user-data cleanup or Git commits.

## Commands executed and exits

| Command (repository root) | Exit | Actual result |
|---|---:|---|
| ./.venv/Scripts/python.exe -m scripts.check_integration_services | 1 | MongoDB ping blocked; MQTT TCP timeout |
| ./.venv/Scripts/python.exe -m pytest -q | 0 | 65 PASS, 1 SKIPPED; DB tests explicitly mocked |
| ./.venv/Scripts/python.exe -m pytest -q -m integration | 0 | 1 SKIPPED, 65 deselected — NOT integration PASS |
| powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1 | 0 | Modbus + energy C++ suites PASS |
| powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-wire-vectors.ps1 | 0 | Five wire vectors PASS |
| runtime Python -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno | 0 | All 3 builds PASS |
| git diff --check | 0 | PASS |

Runtime Python used: C:/Users/theso/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe.
PowerShell's execution-policy argument affected only those child processes; no
machine policy was persisted. One existing Starlette/httpx deprecation warning.

## Integration not executed

Real database writes/restart persistence, real MQTT telemetry→MongoDB, CLI Gateway
and Simulator sessions, REST→MQTT→application ACK, duplicate ACK and timeout flows
are BLOCKED pending services. Mock tests and skipped integration do not establish
these outcomes. The test is ready to check all these flows once both services work.

## Minimal changes

- Fixed real-test fixture to load gateway/.env like the application, retaining a
  fresh energy_test_<UUID> database and exact-name-only cleanup.
- Added real-MQTT duplicate ACK injection and persistent ACK immutability assertion
  to the existing integration test (unexecuted in real mode).
- Hid credential-bearing configuration fields from repr; two regression tests.
- Added redacted, read-only service probe and Atlas instructions in gateway setup.
- Hash comparison confirms firmware, simulator, MQTT models and REST response
  contracts unchanged. Existing working-tree edits preserved.

## Required operator actions

Follow [Atlas setup](gateway-setup.md#phase-21-atlas-setup-operator-actions):
create/select an isolated Atlas Free cluster, authorize this PC's current public
IP as /32, provision the database/test user privately, and put the Atlas driver
URI into ignored gateway/.env. Dynamic UUID databases require test-only create,
read/write, index and dropDatabase privileges; use a disposable cluster, not
production. Keep TLS verification and SRV DNS working; never send credentials in
chat or command arguments.

Install Mosquitto manually from its official Windows installer if needed; operator
handles any installer/elevation prompt. Avoid registering/changing services when
only a foreground loopback broker is needed. Then run these in separate terminals:

```powershell
& 'C:/Program Files/mosquitto/mosquitto.exe' -c scripts/mosquitto-local.conf -v
./.venv/Scripts/python.exe -m scripts.check_integration_services
```

After the probe succeeds, with no other simulator/Collector active:

```powershell
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
try { ./.venv/Scripts/python.exe -m pytest -q tests/python/test_mosquitto_integration.py } finally {
    Remove-Item Env:RUN_MONGODB_TESTS
    Remove-Item Env:RUN_MQTT_INTEGRATION
}
```

Then run `./.venv/Scripts/python.exe -m gateway` and
`./.venv/Scripts/python.exe -m simulator --scenario normal --seed 1` in separate
terminals. Keep these stopped while the integration test owns the fixed topics.
Re-run/record real results before declaring Phase 2.1 complete or beginning Phase 3.
