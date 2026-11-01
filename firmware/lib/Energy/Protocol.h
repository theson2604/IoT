#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace energy {
constexpr uint8_t Version = 1;
constexpr size_t HeaderSize = 14, MaxPacket = 48;
enum class Type : uint8_t {
  Telemetry = 1,
  Command = 2,
  Ack = 3,
  Heartbeat = 4,
  Error = 5
};
enum class Status : uint8_t { Ok = 0, Simulated = 1, SensorError = 2 };
enum class CommandType : uint8_t {
  SetInterval = 1,
  GetStatus = 2,
  SetLocalLed = 3
};
enum class AckCode : uint8_t {
  Ok = 0,
  InvalidParameter = 1,
  Unsupported = 2,
  IdConflict = 3
};
struct Message {
  Type type = Type::Heartbeat;
  uint16_t device = 1;
  uint32_t sequence = 0, uptime = 0;
  int32_t voltage = 0, current = 0, power = 0;
  uint64_t energy = 0;
  Status status = Status::Ok;
  uint32_t commandId = 0, parameter = 0, interval = 1000, sensorErrors = 0;
  CommandType command = CommandType::GetStatus;
  AckCode ack = AckCode::Ok;
  uint16_t error = 0;
};
inline void put(uint8_t *p, uint64_t v, size_t n) {
  for (size_t i = 0; i < n; ++i)
    p[i] = uint8_t(v >> (8 * i));
}
inline uint64_t get(const uint8_t *p, size_t n) {
  uint64_t v = 0;
  for (size_t i = 0; i < n; ++i)
    v |= uint64_t(p[i]) << (8 * i);
  return v;
}
inline int32_t signed32(uint32_t n) {
  return n <= 0x7fffffffu ? int32_t(n) : int32_t(-1 - int64_t(0xffffffffu - n));
}
inline uint16_t crc(const uint8_t *p, size_t n) {
  uint16_t c = 0xffff;
  while (n--) {
    c ^= *p++;
    for (int i = 0; i < 8; ++i)
      c = c & 1 ? (c >> 1) ^ 0xa001 : c >> 1;
  }
  return c;
}
inline size_t payloadSize(Type t) {
  switch (t) {
  case Type::Telemetry:
    return 21;
  case Type::Command:
  case Type::Ack:
  case Type::Heartbeat:
    return 9;
  case Type::Error:
    return 2;
  }
  return 0;
}
inline bool validate(const Message &m) {
  if (!payloadSize(m.type) || !m.device)
    return false;
  if ((m.type == Type::Telemetry || m.type == Type::Heartbeat) &&
      uint8_t(m.status) > 2)
    return false;
  if (m.type == Type::Ack && uint8_t(m.ack) > 3)
    return false;
  return true; // Unknown command opcode is valid framing; sensor responds
               // Unsupported.
}
inline size_t serialize(const Message &m, uint8_t *out, size_t capacity) {
  size_t payload = payloadSize(m.type), n = HeaderSize + payload + 2;
  if (!validate(m) || capacity < n)
    return 0;
  out[0] = Version;
  out[1] = uint8_t(m.type);
  put(out + 2, m.device, 2);
  put(out + 4, m.sequence, 4);
  put(out + 8, payload, 2);
  put(out + 10, m.uptime, 4);
  uint8_t *p = out + HeaderSize;
  switch (m.type) {
  case Type::Telemetry:
    put(p, uint32_t(m.voltage), 4);
    put(p + 4, uint32_t(m.current), 4);
    put(p + 8, uint32_t(m.power), 4);
    put(p + 12, m.energy, 8);
    p[20] = uint8_t(m.status);
    break;
  case Type::Command:
    put(p, m.commandId, 4);
    p[4] = uint8_t(m.command);
    put(p + 5, m.parameter, 4);
    break;
  case Type::Ack:
    put(p, m.commandId, 4);
    p[4] = uint8_t(m.ack);
    put(p + 5, m.interval, 4);
    break;
  case Type::Heartbeat:
    p[0] = uint8_t(m.status);
    put(p + 1, m.interval, 4);
    put(p + 5, m.sensorErrors, 4);
    break;
  case Type::Error:
    put(p, m.error, 2);
    break;
  }
  put(out + n - 2, crc(out, n - 2), 2);
  return n;
}
inline bool deserialize(const uint8_t *in, size_t n, Message &out) {
  if (!in || n < HeaderSize + 2 || n > MaxPacket || in[0] != Version)
    return false;
  Message m;
  m.type = Type(in[1]);
  size_t size = payloadSize(m.type);
  if (!size || get(in + 8, 2) != size || n != HeaderSize + size + 2 ||
      get(in + n - 2, 2) != crc(in, n - 2))
    return false;
  m.device = get(in + 2, 2);
  m.sequence = get(in + 4, 4);
  m.uptime = get(in + 10, 4);
  const uint8_t *p = in + HeaderSize;
  switch (m.type) {
  case Type::Telemetry:
    m.voltage = signed32(get(p, 4));
    m.current = signed32(get(p + 4, 4));
    m.power = signed32(get(p + 8, 4));
    m.energy = get(p + 12, 8);
    m.status = Status(p[20]);
    break;
  case Type::Command:
    m.commandId = get(p, 4);
    m.command = CommandType(p[4]);
    m.parameter = get(p + 5, 4);
    break;
  case Type::Ack:
    m.commandId = get(p, 4);
    m.ack = AckCode(p[4]);
    m.interval = get(p + 5, 4);
    break;
  case Type::Heartbeat:
    m.status = Status(p[0]);
    m.interval = get(p + 1, 4);
    m.sensorErrors = get(p + 5, 4);
    break;
  case Type::Error:
    m.error = get(p, 2);
    break;
  }
  if (!validate(m))
    return false;
  out = m;
  return true;
}
// RFC1982 style serial ordering: reject repeats and old packets, allow uint32
// wrap.
struct Sequence {
  bool initialized = false;
  uint32_t last = 0;
  bool accept(uint32_t seq) {
    uint32_t delta = seq - last;
    if (initialized && (!delta || delta >= 0x80000000u))
      return false;
    last = seq;
    initialized = true;
    return true;
  }
  void reset() { initialized = false; }
};
struct Transport {
  virtual ~Transport() {};
  virtual bool send(const uint8_t *, size_t) = 0;
};
struct MqttTransport {
  virtual ~MqttTransport() {};
  virtual bool publish(const char *, const char *, bool) = 0;
};
} // namespace energy
