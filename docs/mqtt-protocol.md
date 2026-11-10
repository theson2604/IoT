# MQTT, units and API contract (schema v1)

One configured pair is `node01`. MQTT topics are fixed to the existing firmware:

| Topic | Publisher / subscriber | Schema and retention |
|---|---|---|
| energy/node01/telemetry | Collector → Gateway | Telemetry below; not retained |
| energy/node01/state | Collector → Gateway | State fields below; retained |
| energy/node01/command | Gateway → Collector | Numeric firmware command; NEVER retained |
| energy/node01/ack | Collector → Gateway | Application result; not retained |
| energy/node01/event | Collector → Gateway | error/event string; not retained |

Paho uses MQTT 3.1.1, clean sessions, QoS0 in both directions, matching firmware.
This is best effort: no offline command resend/replay queue, no transport-level
success claim. Missing ACKs become timeouts. Reconnect backoff 1–30s resubscribes
all incoming topics. Callbacks enqueue up to 256 messages (max 4096 bytes each);
service processing occurs outside the MQTT network thread. Drops are counted.
QoS1 could improve telemetry delivery in future but cannot upgrade physical
firmware's QoS0 publishes; it also requires a deliberate duplicate/replay policy.

## Telemetry

```json
{"schema_version":1,"device_id":"node01","available":true,"sequence_number":42,"sender_uptime_ms":1000,"voltage_mv":12000,"current_ma":125,"power_mw":1500,"energy_mwh":2,"sensor_status":1}
```

All fields are strictly typed JSON integers except booleans/string identity.
schema_version=1, device_id=node01, available=true. Sequence/uptime are uint32;
voltage/current/power use signed int32 wire ranges; energy_mwh is uint64.
Non-error bus voltage must be nonnegative. INA219 physical limits are narrower
than the transport range; these checks do not certify safe hardware operation.
Sensor status: 0 real OK, 1 SIMULATED, 2 SENSOR_ERROR.

Normalized REST/MongoDB data contains voltage_v=voltage_mv/1000,
current_a=current_ma/1000, power_w=power_mw/1000, energy_wh=energy_mwh/1000.
Example above is 12V, 0.125A, 1.5W and 0.002Wh. Floats are not metrology-grade;
very large uint64 energy converted to floating Wh loses integer precision.
Error status 2 maps voltage/current/power to JSON null, valid=false; zero error
placeholders are NOT interpreted as a load off. Energy is the last accumulated
counter, not proof of successful sampling during an error. Simulation remains
labelled even though values look plausible. SIMULATION_MODE=false rejects status 1.

`received_at` is gateway UTC Unix seconds from time.time(). `sender_uptime_ms`
is elapsed SENSOR time, wrapping at uint32, never a Unix timestamp. No fabricated
sensor timestamp is added. Previously deployed firmware lacks schema/device/uptime
in MQTT: Gateway defaults schema=1 and device=node01 from the fixed topic; uptime
stays null. The only firmware change in Phase 2 is adding those three fields to
telemetry JSON; ESP-NOW bytes and existing metric field names remain unchanged.
Gateway receipt-time status and Collector state provide connection information
separately from measurements. Latest data can be stale: consult device status.

## State and errors

State fields: wifi_connected bool, wifi_channel integer 0..14, espnow_ready bool,
mqtt_connected bool, sensor_seen bool, sensor_online bool, sensor_status 0..2,
age_ms uint32, command_pending bool. All are optional for the separate firmware
last-will form `{"collector_online":false}`. Empty states/unknown keys are rejected.
Retained online snapshots are informational, never fresh evidence of liveness;
a retained negative last will can suppress online status. Fresh telemetry or a
live state update plus connected Gateway transport is required. The default
freshness deadline is 20s. Collector's sensor heartbeat deadline remains 15s.
Gateway restarts do not treat persisted snapshots as online.

Events: `{"error":"SENSOR_ERROR"}` or `{"event":"collector_connected"}`;
strings are bounded to 128 chars. Invalid JSON/schema/nonfinite numbers are rejected
and logged as metadata-only events without copying arbitrary payloads into logs.
Retained telemetry and ACKs are rejected to avoid treating replay as fresh data.

## Commands and ACK correlation

External API accepts public string ID (1–64 letters/digits/underscore/hyphen),
optional generated UUID, and only these methods:

```json
{"command_id":"cmd-001","method":"set_sampling_interval","params":{"interval_ms":2000}}
```

GET_STATUS: `{"method":"get_status"}`. Set interval accepts strict integers
100..60000ms. Unknown methods, LED/load actions and extra parameters are rejected.
MongoDB maps each public ID to an atomic counter uint32 wire ID, preserving the
firmware contract rather than hashing/colliding string IDs:

```json
{"command_id":1,"command_type":1,"command_parameter":2000}
```

Type 1=set interval; type 2=GET_STATUS with parameter 0. Exactly one accepted
command may be pending. Repeating the same public ID/content returns its existing
record without another publish. Different content with that ID returns HTTP 409.
No broker/device connection yields 503. A failed publish is `publish_failed`.

Firmware application result: `{"command_id":1,"result":"acknowledged","code":0}`.
Only a matching numeric ID for a pending command before its deadline gives
success (code 0); codes 1/2/3 give failed. `{"result":"timeout","code":-1,...}`
or default gateway 5s deadline gives timeout. Late/unmatched/duplicate ACKs cannot
turn terminal results into success. Retained ACKs are rejected. An ACK proves
application handling, not MQTT publish receipt or physical load behavior.

Collector's internal 800ms / 3-attempt ESP-NOW retry remains unchanged. A timeout
can occur after sensor executed the command but its ACK was lost. Gateway never
automatically retries. Restart marks pending commands interrupted; it never replays
them. Command IDs/duplicate history are retained for 7 days/10000 rows by default;
wire atomic counter IDs are not reused when old records are pruned. Do not replace
or delete a live DB while nodes have commands in flight; session nonces and
persistent device deduplication are future work.
