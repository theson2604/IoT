#pragma once
// Copy to local_config.h (Git ignored). Empty fields deliberately disable
// connections.
#define COLLECTOR_MAC ""
#define SENSOR_MAC ""
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define MQTT_HOST ""
#define MQTT_PORT 1883
#define MQTT_USER ""
#define MQTT_PASSWORD ""
#define SENSOR_CHANNEL                                                         \
  1 // Match router's actual 2.4GHz channel, not a guessed AP channel.
#define USE_MOCK_SENSOR 1
#define INA219_ADDRESS 0x40 // Confirm address straps.
#define INA219_SHUNT_MILLIOHMS                                                 \
  0 // Required for real sensing; never assume breakout resistor.
