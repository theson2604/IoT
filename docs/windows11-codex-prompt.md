# Codex prompt for Windows 11 setup

Copy the text inside this block into Codex on the laptop.

```text
Set up my Smart Energy Monitoring project on this Windows 11 laptop. Work in PowerShell and use C:\Projects\SmartEnergy unless an existing checkout is already present. Clone https://github.com/theson2604/IoT.git on branch main. If the repo is private, have me sign in through Git Credential Manager. Preserve any existing checkout and local changes.

Check Windows architecture, Git, Python, MongoDB and Mosquitto first. Reuse compatible installations. Create a fresh .venv with Python 3.12 and install gateway/requirements-tested.txt. Read README.md, docs/gateway-setup.md, docs/firmware-quickstart.md and the latest Phase 2.1 validation report before starting services.

For an x64 Windows 11 laptop, prefer native MongoDB Community 8.0 and local Mosquitto. Use official installers. If an installer requires elevation or input, give me the exact action to take and continue with checks that can run independently. Use the loopback development endpoints 127.0.0.1:27017 and 127.0.0.1:1883. Start the foreground broker with scripts/mosquitto-local.conf. Preserve existing data, services and firewall settings. For Atlas or a supported remote MongoDB, have me set the URI privately in gateway/.env and authorize this laptop's public IP when needed.

Copy gateway/.env.example to gateway/.env only if the file is absent. Keep credentials in ignored local files and redact them from output. Use the existing MongoDB backend, MQTT topics and REST API. Keep CoreIOT out of this setup.

From the repo root, run these checks and record the exit codes and results:
- ./.venv/Scripts/python.exe -m pip check
- ./.venv/Scripts/python.exe -m pytest -q
- ./.venv/Scripts/python.exe -m scripts.check_integration_services --mongo-crud

Once real MongoDB and the isolated loopback broker are available, set RUN_MONGODB_TESTS=1 and RUN_MQTT_INTEGRATION=1 for the test process. Run ./.venv/Scripts/python.exe -m pytest -q tests/python/test_mosquitto_integration.py and clear the flags afterward. Keep other Collectors and simulators off the test broker during that run. Use only the repository's isolated test database and cleanup. Then start ./.venv/Scripts/python.exe -m gateway and ./.venv/Scripts/python.exe -m simulator --scenario normal --seed 1 in separate terminals. Check http://127.0.0.1:8000/docs and verify telemetry and an application ACK through the REST API.

For firmware validation, install PlatformIO 6.2.0 in a separate Python environment, install platformio/toolchain-gccmingw32 with PlatformIO's package manager, and run scripts/test.ps1 and scripts/check-wire-vectors.ps1. Build sensor_node, collector_node and yolo_uno using platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno. Leave flashing for a separate request.

Report which services were reachable, which checks passed or were blocked, and the exact next action for each blocker. Mark mocked, skipped and physical hardware checks separately from real integration results. Keep the report brief.
```
