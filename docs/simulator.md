# Two-node application simulator

Run from repository root with the configured local broker:

```powershell
./.venv/Scripts/python.exe -m simulator --scenario normal --seed 1
./.venv/Scripts/python.exe -m simulator --scenario high_power --fault-at 10 --changed-current-ma 1500
./.venv/Scripts/python.exe -m simulator --scenario load_change --load-change 5:500 --load-change 12:125
./.venv/Scripts/python.exe -m simulator --scenario sensor_error --fault-at 5 --fault-duration 10
./.venv/Scripts/python.exe -m simulator --scenario link_failure --fault-at 5 --fault-duration 25
./.venv/Scripts/python.exe -m simulator --scenario mqtt_disconnect --fault-at 5 --fault-duration 10
./.venv/Scripts/python.exe -m simulator --scenario command_timeout
```

Use `--duration 30` to stop after 30s, otherwise Ctrl+C. All names are lowercase.
Scenario options default: seed=1, 125mA baseline, ±5mA fluctuation, changed current
1000mA, fault-at=5s, duration=5s. `normal` is a 12V source; power is integer
voltage_mv*current_ma/1000. high_power/load_change switch current after fault-at
and remain at that value; repeatable `--load-change SECONDS:CURRENT_MA` overrides
the baseline at selected times. No anomaly classifier is implemented.

Sensor uses status=1 even for normal readings; SENSOR_ERROR uses status=2, zero
invalid raw readings, unchanged energy and ERROR packets. Positive energy uses
the firmware's previous-power integration with fractional mWh and skips error
gaps. Sample interval defaults 1000ms and accepts command changes 100..60000ms.
GET_STATUS ACKs and sends heartbeat; heartbeat also runs every 5s independently.

Link faults may be combined with any scenario:

```powershell
./.venv/Scripts/python.exe -m simulator --scenario normal --loss 0.2 --duplicate 0.3 --delay-ms 50 --jitter-ms 1500 --seed 42
./.venv/Scripts/python.exe -m simulator --sensor-disconnect-at 10
./.venv/Scripts/python.exe -m simulator --collector-disconnect-at 10
```

Loss/duplicate probabilities are 0..1. Random jitter 0..jitter-ms plus base delay
naturally produces out-of-order deliveries. The link heap is capped at 256 packets.
Disconnect-at flags take a node down for the remainder of the run. LINK_FAILURE
suppresses link sends during the configured fault window. MQTT_DISCONNECT stops
and restarts the actual Collector MQTT client; an explicit negative state is sent
before deliberate shutdown (unexpected process death uses broker last will).
COMMAND_TIMEOUT suppresses application ACK delivery while telemetry/heartbeat
continue. Sensor caches last 8 IDs; Collector retries the same wire command at
800ms, max 3 attempts, then publishes timeout; duplicate sequence packets are
rejected. Command result waits in RAM for broker reconnection. Telemetry lost while
disconnected is not replayed.

`simulator.wire` implements exact firmware v1 little-endian bytes and CRC, checked
against five fixtures emitted by C++ `tests/wire_vectors.cpp`. Check with
`./scripts/check-wire-vectors.ps1`; deliberately regenerate with `-Update` only
when protocol changes are reviewed. This does not implement 802.11 radio,
ESP-NOW MAC, antenna propagation, hardware UART/I2C or RF coexistence. Differences
from hardware scheduler timing are expected. Unit tests call tick() with exact
elapsed times for deterministic results. A fixed seed reproduces decisions for
a fixed tick schedule; CLI wall-clock scheduling depends on the host OS.

Run only one simulator/physical Collector on node01 topics. A separate isolated
broker is required for integration tests. Without broker, run pytest's in-memory
flows; these are explicitly not real MQTT integration.
