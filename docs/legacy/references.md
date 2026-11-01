# Official references and board provenance

- https://wiki.ohstem.vn/yolo_uno/yolo_uno_khoi_lenh/gioi_thieu_yolo_uno
- https://wiki.ohstem.vn/orc_bot/arduino_platformio/cai_dat
- https://wiki.ohstem.vn/orc_bot/arduino_platformio/cau_hinh_project
- https://github.com/AITT-VN/orc_hub_arduino_examples
- https://digilent.com/reference/_media/reference/pmod/pmodrs485/pmodrs485-rm.pdf
- https://www.waveshare.com/wiki/Modbus_RTU_IO_8CH
- https://coreiot.io/docs/ (future architecture reference only; fetch timed out)

Vendor board JSON and pins_arduino.h copied unchanged from AITT-VN example
commit de3864343c048cdf53f035c10a20d2dd785860d4, as linked by OhStem's setup guide.
The custom board ID is yolo_uno; no generic development board is substituted.
Its internal ARDUINO_ESP32S3_DEV macro is part of the vendor definition.
It specifies ESP32-S3, 8MB flash, 240MHz and its own yolo_uno variant.
PSRAM is not used or assumed by this project. Platform espressif32 is pinned to
6.12.0; this uses upstream Arduino core with the vendor board/variant.
Physical board revision and memory population still require inspection.

Waveshare wiki direct access returned HTTP 403; its indexed official protocol
content was available. Implementation uses the documented V2 zero-based map:
FC01/FC02 start 0 quantity 8; FC05 channels 0–7 with FF00/0000.
Confirm actual module firmware protocol revision before enabling writes.
No credentials or cloud connection are included.
