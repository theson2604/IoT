# Verification record

Executed 2026-10-31 (Asia/Bangkok):

| Check | Result |
|---|---|
| PlatformIO build, custom vendor yolo_uno | PASS |
| Shared C++ Modbus mock tests, g++ 5.1, -Wall -Wextra -Werror | PASS |
| Gateway --version | PASS: energy-gateway 0.1.0-scaffold |
| Vendor board and variant SHA256 comparison | PASS: unchanged |
| USB device discovery | COM1 only, no identified YoloUNO |
| Flash / electrical / live Modbus | UNVERIFIED, not attempted |

Final build: RAM 19,168 / 327,680 bytes; application flash 272,181 / 3,342,336
bytes (8MB device, default_8MB partition layout). Final rebuild had no warnings.

Commands actually executed (runtime Python was used because system `python` is
only a Windows Store alias):

```powershell
$python = 'C:/Users/theso/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python -m pip install platformio
& $python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32
& $python -m platformio run -d G:/slides/261/IOT/Project/firmware
& G:/slides/261/IOT/Project/scripts/test.ps1
& $python G:/slides/261/IOT/Project/gateway/main.py --version
& $python -m platformio device list
```

Host test cases include the official FC05 CRC vector, FC01/FC02 bit maps,
FC05 ON/OFF and readback, diagnostic blocking without transport access, channel
bounds, unsupported function, timeout exhaustion, retry recovery, exception code,
CRC corruption, wrong slave/function/byte count, incorrect write echo and state
mismatch. The mock bypasses physical UART timing: scope tests remain required.
All hardware tests: **UNVERIFIED â€” not run**.

## Bench procedure (loads disconnected)

1. Resolve every blocker in hardware.md before power-up. Start in diagnostic mode.
2. Confirm boot logs safe=1 ready=1; scope DE low and /RE low while idle.
3. Run `read do` and `read di`; check FC01 and FC02 requests, CRC and response bits.
4. Change a safe DI stimulus; confirm corresponding FC02 bit changes.
5. Send `do1 on CONFIRM` in diagnostic mode: expect blocked, no FC05 on bus.
6. Observe for at least 60s and reset: no FC05 should occur automatically.
7. Deliberately build with safe mode 0 only for the isolated bench.
8. Send `do1 on CONFIRM`; verify FC05 address 0 value FF00, echo and FC01 bit0=1.
9. Send `do1 off CONFIRM`; verify value 0000 and FC01 bit0=0.
10. Disconnect slave: verify bounded timeouts/retries. Restore connection and confirm
    there is no write replay from the console. Inspect direction turnaround on scope.
11. Restore diagnostic build and flash it after tests.

Do not mark any item passed without recording date, hardware revisions, wiring,
firmware commit, serial capture and measured result. A successful compile or mock
test does not verify electrical timing, power integrity or actual load behavior.
