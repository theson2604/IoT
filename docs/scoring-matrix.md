# MVP acceptance matrix

| Criterion | Software evidence | Hardware status |
|---|---|---|
| YoloUNO configuration preserved | Git/hash check | Revision inspection pending |
| Modbus preserved/isolated | Unchanged core/tests, legacy build | UNVERIFIED; not current MVP |
| Sensor/Collector compile | PlatformIO role builds | UNVERIFIED |
| Explicit versioned protocol | Golden vector/corruption host tests | Radio UNVERIFIED |
| Retry/ACK/duplicate handling | Shared runtime tests | Loss/reboot bench UNVERIFIED |
| Mock mode functional | Simulated/error host tests, build | Device execution UNVERIFIED |
| INA219 real adapter | Real-mode compile + conversion tests | I2C/calibration UNVERIFIED |
| MQTT interface | Shared mock forwarding + Collector build | Broker interoperability UNVERIFIED |
| HTTP GET routes | Collector build, code review | Requests on board UNVERIFIED |
| STA/ESP-NOW coexistence | AP-first current-channel code | Channel/reconnect UNVERIFIED |
| No credentials/load control | Ignored blank config, no actuation | Wiring checks pending |
| PC Gateway/AI/CoreIOT/OTA | Scaffolds unchanged | OUT OF SCOPE |
