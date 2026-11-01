#pragma once
#include "Protocol.h"
#include <limits.h>
#include <stdio.h>
namespace energy {
inline void telemetryJson(const Message &m, char *out, size_t size) {
  snprintf(
      out, size,
      "{\"available\":true,\"voltage_mv\":%ld,\"current_ma\":%ld,\"power_mw\":%"
      "ld,\"energy_mwh\":%llu,\"sensor_status\":%u,\"sequence_number\":%lu}",
      (long)m.voltage, (long)m.current, (long)m.power,
      (unsigned long long)m.energy, unsigned(m.status),
      (unsigned long)m.sequence);
}
inline bool forwardTelemetry(MqttTransport &broker, const Message &m) {
  if (m.type != Type::Telemetry || !validate(m))
    return false;
  char json[384];
  telemetryJson(m, json, sizeof json);
  return broker.publish("energy/node01/telemetry", json, false);
}
inline bool validInterval(uint32_t n) { return n >= 100 && n <= 60000; }
struct Reading {
  int32_t voltage = 0, current = 0, power = 0;
  Status status = Status::SensorError;
};
struct EnergySensor {
  virtual ~EnergySensor() {};
  virtual bool begin() = 0;
  virtual Reading read() = 0;
};
struct MockEnergySensor : EnergySensor {
  bool fault = false;
  bool begin() override { return true; }
  Reading read() override {
    Reading r;
    if (!fault) {
      r.voltage = 12000;
      r.current = 125;
      r.power = 1500;
      r.status = Status::Simulated;
    }
    return r;
  }
};
inline Reading convertIna(uint16_t bus, int16_t shunt, uint32_t milliohms) {
  Reading r;
  if (!milliohms || (bus & 1) || !(bus & 2))
    return r;
  int64_t ma = int64_t(shunt) * 10 / milliohms;
  r.voltage = (bus >> 3) * 4;
  int64_t power = int64_t(r.voltage) * ma / 1000;
  if (ma > INT32_MAX || ma < INT32_MIN || power > INT32_MAX ||
      power < INT32_MIN)
    return Reading{};
  r.current = int32_t(ma);
  r.power = int32_t(power);
  r.status = Status::Ok;
  return r;
}
// Positive consumption only, mW*ms / 3,600,000 = mWh. Preserve fractional
// remainder.
struct Integrator {
  uint64_t mwh = 0, remainder = 0;
  uint32_t last = 0;
  bool previousValid = false;
  int32_t previousPower = 0;
  uint64_t sample(const Reading &r, uint32_t now) {
    if (previousValid && r.status != Status::SensorError) {
      uint64_t x = uint64_t(previousPower > 0 ? previousPower : 0) *
                       uint32_t(now - last) +
                   remainder;
      uint64_t delta = x / 3600000;
      remainder = x % 3600000;
      mwh = UINT64_MAX - mwh < delta ? UINT64_MAX : mwh + delta;
    }
    previousValid = r.status != Status::SensorError;
    previousPower = r.power;
    last = now;
    return mwh;
  }
};
// Cache makes retransmitted commands idempotent; changed content with same ID
// is rejected.
class Commands {
  struct Entry {
    bool used = false;
    uint32_t id = 0, parameter = 0;
    CommandType type = CommandType::GetStatus;
    Message ack;
  };
  Entry cache[8];
  unsigned next = 0;

public:
  uint32_t interval = 1000;
  bool requestStatus = false;
  Message handle(const Message &cmd) {
    for (auto &c : cache)
      if (c.used && c.id == cmd.commandId) {
        Message a = c.ack;
        if (c.type != cmd.command || c.parameter != cmd.parameter)
          a.ack = AckCode::IdConflict;
        return a;
      }
    Message a;
    a.type = Type::Ack;
    a.commandId = cmd.commandId;
    a.ack = AckCode::Unsupported;
    if (cmd.command == CommandType::SetInterval) {
      a.ack = validInterval(cmd.parameter) ? AckCode::Ok
                                           : AckCode::InvalidParameter;
      if (a.ack == AckCode::Ok)
        interval = cmd.parameter;
    } else if (cmd.command == CommandType::GetStatus) {
      a.ack = cmd.parameter == 0 ? AckCode::Ok : AckCode::InvalidParameter;
      requestStatus = a.ack == AckCode::Ok;
    }
    a.interval = interval;
    Entry &c = cache[next++ % 8];
    c.used = true;
    c.id = cmd.commandId;
    c.parameter = cmd.parameter;
    c.type = cmd.command;
    c.ack = a;
    return a;
  }
  bool cached(uint32_t id) const {
    for (auto &c : cache)
      if (c.used && c.id == id)
        return true;
    return false;
  }
};
enum class Completion { None, Acknowledged, Timeout };
class PendingCommand {
  Transport &transport;
  uint8_t packet[MaxPacket]{};
  size_t length = 0;
  uint32_t last = 0;

public:
  bool active = false;
  uint32_t id = 0;
  unsigned attempts = 0;
  Completion completion = Completion::None;
  AckCode code = AckCode::Ok;
  explicit PendingCommand(Transport &t) : transport(t) {}
  bool start(const Message &m, uint32_t now) {
    if (active || m.type != Type::Command)
      return false;
    length = serialize(m, packet, sizeof packet);
    if (!length)
      return false;
    active = true;
    id = m.commandId;
    attempts = 1;
    last = now;
    completion = Completion::None;
    transport.send(packet, length);
    return true;
  }
  void tick(uint32_t now) {
    if (!active || uint32_t(now - last) < 800)
      return;
    if (attempts >= 3) {
      active = false;
      completion = Completion::Timeout;
      return;
    }
    ++attempts;
    last = now;
    transport.send(packet, length);
  }
  bool ack(const Message &m) {
    if (!active || m.type != Type::Ack || m.commandId != id)
      return false;
    active = false;
    completion = Completion::Acknowledged;
    code = m.ack;
    return true;
  }
};
} // namespace energy
