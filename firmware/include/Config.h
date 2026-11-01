#pragma once
#if __has_include("local_config.h")
#include "local_config.h"
#endif
#ifndef COLLECTOR_MAC
#define COLLECTOR_MAC ""
#endif
#ifndef SENSOR_MAC
#define SENSOR_MAC ""
#endif
#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif
#ifndef MQTT_HOST
#define MQTT_HOST ""
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif
#ifndef MQTT_USER
#define MQTT_USER ""
#endif
#ifndef MQTT_PASSWORD
#define MQTT_PASSWORD ""
#endif
#ifndef SENSOR_CHANNEL
#define SENSOR_CHANNEL 1
#endif
#ifndef USE_MOCK_SENSOR
#define USE_MOCK_SENSOR 1
#endif
#ifndef INA219_ADDRESS
#define INA219_ADDRESS 0x40
#endif
// Must be measured/confirmed for the actual breakout before enabling real
// sensing.
#ifndef INA219_SHUNT_MILLIOHMS
#define INA219_SHUNT_MILLIOHMS 0
#endif
