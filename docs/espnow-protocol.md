# Energy application protocol v1

Integers are little-endian; signed values use 32-bit two's complement. No packed
struct transmission or compiler padding. Largest packet is 37 bytes (under
ESP-NOW v1's 250-byte payload limit). CRC16/Modbus initial FFFF, reflected A001,
covers header+payload; CRC itself is little-endian. CRC is not authentication.

| Offset | Bytes | Field |
|---|---|---|
| 0 | 1 | protocol_version = 1 |
| 1 | 1 | message_type |
| 2 | 2 | device_id: Sensor=1, Collector=2 |
| 4 | 4 | sequence_number |
| 8 | 2 | payload_length |
| 10 | 4 | sender_uptime_ms |
| 14 | variable | payload |
| 14+payload_length | 2 | CRC |

Payload offsets below are relative to start of payload.

| Type | Value | Length | Fields |
|---|---|---|---|
| TELEMETRY | 1 | 21 | voltage_mv i32@0, current_ma i32@4, power_mw i32@8, energy_mwh u64@12, sensor_status u8@20 |
| COMMAND | 2 | 9 | command_id u32@0, command_type u8@4, command_parameter u32@5 |
| COMMAND_ACK | 3 | 9 | command_id u32@0, result_code u8@4, sampling_interval_ms u32@5 |
| HEARTBEAT | 4 | 9 | sensor_status u8@0, sampling_interval_ms u32@1, sensor_errors u32@5 |
| ERROR | 5 | 2 | error_code u16@0 (1=SENSOR_ERROR) |

Status: 0 real OK, 1 SIMULATED, 2 SENSOR_ERROR. ACK code: 0 OK, 1 invalid
parameter, 2 unsupported, 3 ID conflict. Command 1 sets interval 100–60000ms;
2 requests heartbeat (parameter 0); 3 LED is reserved/unsupported. Unknown command
opcodes receive unsupported ACK; unknown message types cannot decode.

serialize(), deserialize(), validate() check type/status/version/length/CRC and
nonzero device ID. Applications additionally enforce expected peer MAC, device
and direction. Rejected decoding leaves output unchanged. Sensor errors carry
zero measurement placeholders and status=2, never normal fabricated readings.

Freshness uses modular sequence difference strictly 1..2^31-1; equal/old are
rejected except cached command retries get cached ACK. Uptime and sequences wrap.
See architecture.md for idle/reboot reset and finite cache limitations.
ACK completes only after validated type+command-ID correlation. MAC callback
success never completes it. Retries use same command/sequence, 800ms apart,
maximum 3 attempts; late/unmatched ACKs do not complete later transactions.
