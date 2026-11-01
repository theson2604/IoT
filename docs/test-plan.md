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
