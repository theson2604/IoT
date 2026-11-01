# Hardware bring-up checklist

**Every item UNVERIFIED: no hardware available, nothing flashed.** Before marking
PASS record date, revision/config without secrets, wiring, capture and measurement.

1. Verify YoloUNO revision, INA219 supply/pull-ups/address/shunt and safe DC setup.
2. Flash each identified board; log actual STA MACs. Configure opposite MACs,
   Collector network/broker and Sensor matching AP channel, rebuild and reflash.
3. Verify Collector AP channel/IP/radio-ready and all four HTTP GET routes.
4. Verify mock telemetry status=1 in broker and HTTP, heartbeat and online status.
5. Send interval 1000/100/60000 with unique IDs; measure cadence and ACK IDs.
   GET_STATUS must ACK and send heartbeat. LED remains unsupported.
6. Send malformed/invalid/repeated/busy commands: verify rejection events.
7. Lose radio/ACKs: verify exactly 3 attempts and timeout. Duplicate retries must
   not reapply commands within cache window. MAC success alone is not an ACK.
8. Power off Sensor: online false in 15s. Restart: verify sequence recovery.
9. Stop/restart broker: radio/HTTP continue, telemetry loss expected, reconnect
   resubscribes; verify retained state/LWT and pending result publication.
10. Disconnect AP/reconnect, then change router channel: Collector follows AP;
    Sensor remains offline until manually matched. Never force Collector channel.
11. Enable real INA mode with verified shunt. Compare V/I/P/energy to instruments.
    Disconnect INA: status=2/error event, invalid zero placeholders, no simulated
    substitution. Reconnect and verify recovery.
12. Stress cadence, HTTP and reconnects. Record queue drops, heap stability and
    timing. No lossless/real-time claim before measured testing.

Channel troubleshooting: compare AP and Sensor logged channels, verify 2.4GHz,
STA MACs (not AP MAC), valid peer config/range, and restart after config changes.
Set fixed router channel or update Sensor, not Collector's connected STA channel.
