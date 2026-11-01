#pragma once
#include "Config.h"
#include <Runtime.h>
#include <Wire.h>
class INA219EnergySensor : public energy::EnergySensor {
  bool configured = false;
  bool reg(uint8_t address, uint16_t &value) {
    Wire.beginTransmission(INA219_ADDRESS);
    Wire.write(address);
    if (Wire.endTransmission(false) != 0 ||
        Wire.requestFrom(uint8_t(INA219_ADDRESS), uint8_t(2)) != 2)
      return false;
    value = uint16_t(Wire.read()) << 8;
    value |= Wire.read();
    return true;
  }

public:
  bool begin() override {
    Wire.begin(SDA, SCL);
    Wire.setTimeOut(50);
    if (!INA219_SHUNT_MILLIOHMS)
      return false;
    // Continuous bus+shunt, 12-bit, +/-320mV gain. Use raw readings, not
    // calibrated registers.
    Wire.beginTransmission(INA219_ADDRESS);
    Wire.write(0);
    Wire.write(0x39);
    Wire.write(0x9f);
    uint16_t config = 0;
    configured =
        Wire.endTransmission() == 0 && reg(0, config) && config == 0x399f;
    return configured;
  }
  energy::Reading read() override {
    uint16_t bus = 0, shunt = 0, config = 0;
    if (!configured) {
      begin();
      return {};
    }
    if (!reg(0, config) || config != 0x399f || !reg(2, bus) || !reg(1, shunt)) {
      configured = false;
      return {};
    }
    const int16_t signedShunt =
        int16_t(int32_t(shunt) - ((shunt & 0x8000) ? 65536 : 0));
    return energy::convertIna(bus, signedShunt, INA219_SHUNT_MILLIOHMS);
  }
};
