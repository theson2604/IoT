> HISTORICAL: replaced by ../gateway-setup.md. Do not use for current setup.

# Gateway setup — Windows and WSL2

Requires Python 3.11+, local Mosquitto, and three terminal sessions. Docker is not
required. Installation and firewall changes are manual operator actions only.

## Native Windows PowerShell

```powershell
Set-Location G:\slides\261\IOT\Project
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r gateway/requirements-dev.txt
Copy-Item gateway/.env.example gateway/.env
```

If `python` opens the Windows Store, use the full path to an installed Python.
Activation is optional; explicit .venv Python paths avoid PowerShell policy issues.
`gateway/requirements-tested.txt` records the exact dependency set used for the
validation run; install it instead for a reproduction of that environment.

Install Mosquitto using the official [Windows download](https://mosquitto.org/download/).
Do not overwrite or stop an existing broker service automatically; select a free
port and update LOCAL_MQTT_PORT if a service already owns 1883. Run manually:

```powershell
& 'C:/Program Files/mosquitto/mosquitto.exe' -c ./scripts/mosquitto-local.conf -v
```

The supplied config allows anonymous access **on loopback only**, no persistence.
It is for this local simulation, not a public/network listener. Verify in another terminal:

```powershell
./scripts/check-broker.ps1
& 'C:/Program Files/mosquitto/mosquitto_sub.exe' -h 127.0.0.1 -p 1883 -t 'energy/node01/#' -v
```

Optional publish test from another terminal (non-retained event):

```powershell
'{"event":"manual_smoke"}' | & 'C:/Program Files/mosquitto/mosquitto_pub.exe' -h 127.0.0.1 -p 1883 -t 'energy/node01/event' -s
```

Then run `./scripts/start-gateway.ps1` and `./scripts/start-simulator.ps1 -Scenario normal`
in separate terminals, or the equivalent `python -m gateway` / `python -m simulator`.
API binds 127.0.0.1:8000. Browse /docs for typed request/response schemas.
Only diagnostic commands exist; do not expose this unauthenticated local API to
public networks or use multiple Uvicorn workers. One gateway process owns one DB.

## WSL2 Ubuntu

Inside WSL, from the repository root (for example `/mnt/g/slides/261/IOT/Project`):

```bash
sudo apt update
sudo apt install python3-venv mosquitto mosquitto-clients
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install -r gateway/requirements-dev.txt
cp gateway/.env.example gateway/.env
mosquitto -c scripts/mosquitto-local.conf -v
# In two separate WSL shells:
.venv-wsl/bin/python -m gateway
.venv-wsl/bin/python -m simulator --scenario normal
```

These sudo commands are instructions only; not executed by Codex. A package-managed
broker may already run; inspect it rather than starting a second listener. Keep
all services in the same environment initially. Windows↔WSL localhost forwarding
varies by networking setup; verify the listener before mixing environments.
Use separate Windows/WSL venvs; they cannot share interpreter binaries.
Python tests work in either; C++ PowerShell runner is Windows-specific. On Linux
use `g++ -std=c++11 -Wall -Wextra -Werror -Ifirmware/lib/Energy tests/energy_test.cpp -o /tmp/energy-test`
then `/tmp/energy-test`, and similarly use lib/Modbus for modbus_test.cpp.

## Configuration and storage

`gateway/.env` is ignored. Environment variables override .env. Defaults are in
.env.example: localhost:1883, no credentials, data/energy.sqlite3, INFO logging,
simulation enabled, device timeout 20s, command deadline 5s, 7-day retention,
100000 telemetry rows, 10000 events and 10000 command records. Paths are relative
to the working directory: start from repository root. SQLite schema v1 initializes
automatically, with WAL and indexes; no ORM or server install. Schema versions
newer than the app are rejected. Raw payloads/secrets are not logged. Logging goes
to the console; use your service manager for rotation if persisting logs.

Pydantic models enforce integer ranges and null invalid sensor values. Public
commands map durably to numeric wire IDs. Retention runs every second; row caps
may temporarily exceed by at most the current processing burst, and pending
commands are not pruned. SQLite reuses freed pages; pruning is not file compaction.
Use history/events `limit` 1..1000 and `before_id` for bounded pagination. Events
include invalid-payload/unmatched-ACK diagnostics. A restarted gateway reports old
pending commands interrupted and waits for fresh device evidence before online.
Wall-clock gateway time must be synchronized; clock adjustments affect deadlines.

## Hardware migration

Stop the simulator. Configure actual board MACs, Wi-Fi/AP channel and INA219 per
hardware-validation.md. Set SIMULATION_MODE=false to reject simulated status=1.
Collector's MQTT_HOST must be the PC's actual LAN address or resolvable LAN name:
127.0.0.1 on an ESP32 refers to itself, not the PC. Gateway may keep localhost if
it shares the broker machine. To accept a physical board, the operator must create
a LAN-bound broker listener with authentication/ACLs and appropriate local-network
firewall policy. Do not expose the anonymous loopback development config publicly.
No LAN listener, credentials or firewall changes are provisioned here.
See [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/).

## Troubleshooting

- No broker: check executable/PATH, check-broker.ps1, logs and port. pytest still
  runs all memory tests; integration is skipped unless explicitly enabled.
- Device offline: wait for fresh telemetry/live state. Retained state alone is
  intentionally insufficient; confirm one source, topic, schema and AP channel.
- Command stays pending: publish is not an application ACK; inspect event topic,
  active ID, node connectivity and timeout. Never blindly retry the same action.
- Simulator data rejected: SIMULATION_MODE=false rejects status 1; use true for tests.
- No telemetry latest: HTTP 404 is expected until a valid measurement is stored.
- Restart/old results: DB persists, current live status does not. Do not delete a
  live DB to reset command IDs while nodes may still return old ACKs.
- In this tested dependency set Starlette emits an httpx deprecation warning in
  tests; tests pass. A future test-client dependency update can address it.
