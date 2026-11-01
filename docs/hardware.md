# Current MVP hardware

**All physical checks UNVERIFIED.** Two OhStem YoloUNO ESP32-S3 boards required.
Existing vendor variant defines SDA=GPIO11, SCL=GPIO12. Firmware uses SDA/SCL
symbols. Inspect board revision and connector positions before wiring. Native USB
CDC at 115200 provides MACs and debug logs.

Sensor: INA219 SDA→SDA, SCL→SCL, shared GND and ESP32-compatible 3.3V logic supply
and pull-ups. Inspect actual breakout regulator/pull-ups, address straps and shunt.
Do not attach 5V I2C pull-ups to ESP32 pins. IN+/IN- follow current direction on a
safe DC bench. INA219 IC supports bus 0–26V; actual breakout/shunt/terminal current
and power limits may be lower. No mains measurements. Default 0x40 configuration
requires matching address straps. No shunt is assumed; confirm milliohms before
setting INA219_SHUNT_MILLIOHMS.

Adapter writes 0x399F (continuous bus/shunt, 12-bit) and reads raw registers:
bus=(reg>>3)*4mV, shunt=10uV per signed bit, current_mA=shunt_uV/shunt_milliohms,
power_mW=voltage_mV*current_mA/1000. It does not use calibrated current/power
registers. Overflow/not-ready, config mismatch or I2C failure yields SENSOR_ERROR.
Accuracy/calibration/bus drop/wiring and real reads require instrument comparison.

Collector needs a reachable 2.4GHz AP and separately deployed local broker. Use
actual STA MACs from logs. Match Sensor channel to logged AP channel. Neither
broker nor PC Gateway is deployed here. Power boards through supported USB input;
verify power budget and grounding, with real loads disconnected initially.
LED is not controlled. Pmod/Waveshare are not connected in this MVP; their previous
wiring/power/termination blockers remain in [legacy hardware](legacy/hardware.md).
