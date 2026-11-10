# Two-node firmware architecture

Sensor/device 1 samples EnergySensor, integrates positive consumption, sends
telemetry/error/heartbeat and handles diagnostic commands. Collector/device 2
validates Sensor messages, publishes JSON, serves HTTP and runs one pending
command transaction. PC Gateway is implemented in Phase 2 below; CoreIOT, AI and dashboard remain outside scope.

Shared modules: lib/Energy/Protocol.h (codec/validation/ordering/interfaces) and
Runtime.h (mock sensor, conversion, energy integration, command cache/retry and
MQTT forwarding). include/Radio.h is the bounded ESP-NOW adapter;
INA219EnergySensor.h is the I2C adapter. Separate src/sensor and src/collector
entrypoints are selected by build_src_filter and role flags.

The unchanged Modbus app moved to src/legacy/main.cpp; lib/Modbus and its tests
remain unchanged. Environment yolo_uno builds only legacy Modbus. Existing board
JSON, variant, espressif32@6.12.0, Arduino and native USB settings are preserved.
Baseline documents are copied byte-for-byte under docs/legacy (not current MVP).

## Wi-Fi coexistence

Collector starts STA, connects to the configured AP, logs IP/channel, then adds
the ESP-NOW peer on current channel 0 / WIFI_IF_STA. It never calls
esp_wifi_set_channel. STA reconnect attempts are spaced 10s; MQTT attempts 5s.
Existing ESP-NOW peer follows STA when it reassociates. A peer-init failure retries
on next connection edge; fix config and restart if necessary.
Sensor selects configurable SENSOR_CHANNEL in unassociated STA mode.

If the router changes channel, Collector follows but Sensor does not: Sensor
becomes offline until its channel is manually matched/reflashed. Prefer a fixed
2.4GHz AP channel; no automatic discovery/scan/provisioning is implemented.
During Collector scans/reconnect packet loss/timeouts are possible. Use actual
STA-interface MACs from logs, not AP-interface MACs. Blank/zero/multicast MACs
disable radio setup. Channel must be legal in deployment country.

Callbacks use the installed Arduino-ESP32 2.0.17 / ESP-IDF 4.4 signatures.
Receive callback copies at most 48 bytes into an 8-slot FreeRTOS queue; send
callback updates atomic MAC counters. All parsing, commands, I2C, JSON and MQTT
run in the main loop. Queue overflow/invalid-peer/invalid-frame counts are exposed.

## Delivery and recovery

Enqueue success, MAC success and command application ACK are distinct.
PendingCommand sends identical bytes up to 3 total times, 800ms apart; timeout
at 2400ms. Sensor caches last 8 command IDs/results. Same content resends cached
ACK with a new sequence; different content gives ID conflict. Collector rejects
last 8 accepted IDs and permits one outstanding command. These are bounded RAM
windows, not persistent exactly-once semantics. IDs should never be reused.

All outgoing message types share one sequence per sender. Modular uint32 ordering
rejects repeated/old frames. After 15s without an accepted message, Collector resets
its watermark to permit sensor reboot recovery; Sensor resets command watermark
after 15s command inactivity. Cached retries still receive ACKs. Without a boot
session nonce, old frames after idle can be accepted: only safe diagnostics are
allowed. Heartbeat every 5s keeps online state separate from sampling up to 60s.

Telemetry is best effort with no replay/store-and-forward. A single command result
waits in RAM for MQTT publish acceptance, blocking new commands until drained.
QoS0 publish acceptance is not broker application receipt. Retained state refreshes
every 5s plus LWT. `/api/telemetry` holds the latest sample, which can be stale;
check `/api/status` age/online. Reboot resets counters, caches and energy.

Buffers/caches are bounded: receive queue 8x48 payload bytes, JSON doc 256 bytes,
MQTT buffer 512, response buffers up to 512. Arduino HTTP/network internals use
String allocation, but no Strings are used in radio callbacks. Synchronous HTTP
and MQTT DNS/TCP connect can delay the main loop; overflow is counted. This needs
hardware load testing, not an assumption of lossless real-time behavior.

## Sensing behavior

Mock produces 12000mV/125mA/1500mW, labelled SIMULATED. Real mode verifies I2C
reads/config; failure yields status SENSOR_ERROR, zero INVALID placeholders and
ERROR code 1. It retries initialization without stopping communications and never
substitutes simulated data. GET_STATUS ACKs then triggers a heartbeat.
Integration uses previous positive power over elapsed ms with fractional remainder;
intervals across sensor errors are skipped, reverse power is not accumulated.
Volatile energy resets at boot. SET_LOCAL_LED is unsupported: RGB pin metadata
does not verify driver/polarity behavior. No GPIO loads or Modbus in new roles.

Primary references:
[ESP-IDF ESP-NOW](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-reference/network/esp_now.html),
[TI INA219](https://www.ti.com/lit/ds/symlink/ina219.pdf),
[PubSubClient 2.8](https://github.com/knolleary/pubsubclient/tree/v2.8).

## Phase 2 PC Gateway and simulator

`simulator/Sensor + Link + Collector → Paho → Mosquitto → Paho queue → Gateway service → MongoDB → FastAPI`.
API commands take the reverse path with a durable public-string-ID/numeric-wire-ID
mapping. Only matched application ACKs mark success. MQTT publication and link send
acceptance alone do not. The Simulator uses the shared byte layout, C++-generated
fixtures, seeded randomness and explicit ticks. MemoryBroker is a unit-test fixture,
not MQTT protocol implementation or RF simulation.

Gateway layers: models (strict boundary/API schemas), mqtt (Paho adapter), services
(routing/status/command correlation), storage (PyMongo collections/indexes), main (FastAPI lifespan,
100ms maintenance loop and REST). A lock serializes local service/API operations; MongoDB unique indexes and conditional single-document updates protect command creation and terminal transitions.
Paho callbacks enqueue bounded messages; maintenance runs outside their thread.
Shutdown waits for maintenance completion before closing MongoDB. No database or
network connections are created at import time. REST is loopback-only by default.

Broker and device outages are independent. Gateway online requires its broker
connection plus fresh device evidence; measurements can remain available offline.
Telemetry sequences deduplicate modulo uint32 until a 20s idle reset for reboot
recovery. This is a RAM/time watermark, not a durable boot-session identity.
Schema/device/uptime metadata is now present in firmware MQTT telemetry; legacy
payloads still work with unknown uptime. Wire bytes and physical configuration are
unchanged. Full contract: mqtt-protocol.md; runbook: gateway-setup.md.
