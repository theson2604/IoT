# Wiring and commissioning blockers

## YoloUNO

Vendor variant maps TX=GPIO43, RX=GPIO44; firmware uses UART1 routed to these
pins, leaving native USB for debug. Header positions must be checked on the
physical board. Other vendor defaults: SDA=11, SCL=12, SPI SS=10, MOSI=11,
MISO=13, SCK=12, RGB=48. INA219 is not initialized.
DE and /RE are intentionally UNASSIGNED (-1), because no user wiring was supplied.
Do not interpret Arduino header names as raw GPIO numbers.

## Digilent PmodRS485 rev B

| J2 pin | Signal | Connect to |
|---|---|---|
| 1 | /RE | verified receive-enable GPIO |
| 2 | TxD | YoloUNO TX GPIO43 |
| 3 | RxD | YoloUNO RX GPIO44 |
| 4 | DE | verified driver-enable GPIO |
| 5 | GND | YoloUNO logic GND |
| 6 | VCC | regulated 3.3V |

Check pin 1 orientation against the actual PCB. Receive: DE=0, /RE=0.
Transmit: /RE=1, DE=1; UART flush waits for completion before DE=0, /RE=0.
Use an external DE pull-down so reset/high-impedance MCU pins cannot drive the bus.
Firmware cannot guarantee pin state before setup or external module output state.

Half duplex: join A with Y; join B with Z at the Pmod. Connect A/Y to the
Waveshare positive RS485 terminal and B/Z to its negative terminal. Confirm terminal
polarity on the actual device; RS485 lettering conventions can differ.
Use a twisted pair and short stubs. JP1 enables Pmod termination: fit it only
when the Pmod is a bus endpoint. Terminate both physical endpoints, not every node;
inspect the Waveshare termination arrangement before adding another resistor.
The isolated Pmod bus side must not be bridged to logic ground casually.

Pmod recommended supply is 3.3V (manual permitted external range 3.0–5.5V).
Use 3.3V logic with ESP32-S3; verify available supply current before connection.
Power YoloUNO using its documented USB input. Do not connect an industrial supply
to its GPIO or Pmod VCC. Waveshare requires its own rated supply: exact voltage,
input wiring and DO load ratings must be confirmed from unit label/manual before
energizing (wiki access was blocked). This is an explicit commissioning blocker;
no rating is inferred from similarly named Waveshare modules. Keep loads disconnected.

## Unresolved before live tests

- Inspect YoloUNO revision, accessible TX/RX headers and two direction GPIOs.
- Verify Pmod revision/orientation, power budget and reset DE pull-down.
- Verify Waveshare exact supply/load ratings, bus polarity and termination.
- Verify slave 1, 9600 8N1, V2 register map and normal output mode.
- Identify USB port; no connected hardware availability has been established.
