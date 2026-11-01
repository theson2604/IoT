#include "Runtime.h"
#include <assert.h>
#include <initializer_list>
#include <stdio.h>
using namespace energy;
struct MockRadio : Transport {
  uint8_t bytes[MaxPacket]{};
  size_t size = 0;
  unsigned calls = 0;
  bool success = true;
  bool send(const uint8_t *p, size_t n) override {
    memcpy(bytes, p, n);
    size = n;
    ++calls;
    return success;
  }
};
struct MockMqtt : MqttTransport {
  char topic[64]{}, payload[384]{};
  unsigned calls = 0;
  bool success = true;
  bool publish(const char *t, const char *p, bool retain) override {
    assert(!retain);
    snprintf(topic, sizeof topic, "%s", t);
    snprintf(payload, sizeof payload, "%s", p);
    ++calls;
    return success;
  }
};
void framing() {
  Message m;
  m.type = Type::Telemetry;
  m.device = 0x1234;
  m.sequence = 0x12345678;
  m.uptime = 0xabcdef01;
  m.voltage = 12000;
  m.current = -125;
  m.power = -1500;
  m.energy = 0x1020304050607080ULL;
  m.status = Status::Simulated;
  uint8_t data[MaxPacket]{};
  auto n = serialize(m, data, sizeof data);
  assert(n == 37);
  const uint8_t header[] = {1,    1,  0x34, 0x12, 0x78, 0x56, 0x34,
                            0x12, 21, 0,    1,    0xef, 0xcd, 0xab};
  assert(!memcmp(data, header, sizeof header));
  assert(data[14] == 0xe0 && data[15] == 0x2e && data[18] == 0x83 &&
         data[19] == 255 && data[26] == 0x80);
  Message out;
  assert(deserialize(data, n, out));
  assert(out.current == -125 && out.power == -1500 && out.energy == m.energy &&
         out.device == 0x1234);
  assert(!serialize(m, data, 36));
  // Every single-bit error anywhere in a valid packet must be detected.
  serialize(m, data, sizeof data);
  for (size_t i = 0; i < n; ++i)
    for (unsigned bit = 0; bit < 8; ++bit) {
      data[i] ^= 1 << bit;
      assert(!deserialize(data, n, out));
      data[i] ^= 1 << bit;
    }
  for (size_t size = 0; size < n; ++size)
    assert(!deserialize(data, size, out));
  assert(!deserialize(data, n + 1, out));
  assert(!deserialize(nullptr, n, out));
  data[0] = 2;
  put(data + n - 2, crc(data, n - 2), 2);
  assert(!deserialize(data, n, out));
  data[0] = 1;
  data[1] = 99;
  put(data + n - 2, crc(data, n - 2), 2);
  assert(!deserialize(data, n, out));
  serialize(m, data, sizeof data);
  data[8] = 20;
  put(data + n - 2, crc(data, n - 2), 2);
  assert(!deserialize(data, n, out));
  serialize(m, data, sizeof data);
  data[34] = 3;
  put(data + n - 2, crc(data, n - 2), 2);
  assert(!deserialize(data, n, out));
  for (Type type : {Type::Command, Type::Ack, Type::Heartbeat, Type::Error}) {
    m.type = type;
    m.commandId = 0x78563412;
    m.parameter = 1234;
    m.interval = 500;
    m.error = 1;
    n = serialize(m, data, sizeof data);
    assert(n <= 250 && deserialize(data, n, out));
    assert(out.type == type);
    if (type == Type::Command)
      assert(out.commandId == m.commandId && out.parameter == 1234);
    if (type == Type::Ack)
      assert(out.commandId == m.commandId && out.interval == 500);
    if (type == Type::Error)
      assert(out.error == 1);
  }
  puts("PASS protocol: golden header, signed fields, all types, every "
       "single-bit corruption, lengths/version/type/status rejection");
}
void sequences() {
  Sequence s;
  assert(s.accept(0xfffffffe));
  assert(!s.accept(0xfffffffe));
  assert(s.accept(0xffffffff));
  assert(s.accept(0));
  assert(!s.accept(0xffffffff));
  assert(s.accept(1));
  assert(!s.accept(0x80000001));
  s.reset();
  assert(s.accept(0));
  puts("PASS sequence: duplicates, old packets, rollover, half-range "
       "rejection, explicit reset");
}
void commands() {
  Commands c;
  Message m;
  m.type = Type::Command;
  m.commandId = 1;
  m.command = CommandType::SetInterval;
  m.parameter = 100;
  assert(c.handle(m).ack == AckCode::Ok && c.interval == 100);
  m.parameter = 500;
  assert(c.handle(m).ack == AckCode::IdConflict && c.interval == 100);
  m.commandId = 2;
  assert(c.handle(m).ack == AckCode::Ok && c.interval == 500);
  m.commandId = 1;
  m.parameter = 100;
  assert(c.handle(m).ack == AckCode::Ok &&
         c.interval == 500); // Replayed old ID does not reapply.
  for (uint32_t invalid : {0u, 99u, 60001u, 0xffffffffu}) {
    m.commandId++;
    m.commandId += 10;
    m.parameter = invalid;
    assert(c.handle(m).ack == AckCode::InvalidParameter && c.interval == 500);
  }
  assert(validInterval(60000));
  m.commandId = 100;
  m.command = CommandType::GetStatus;
  m.parameter = 0;
  assert(c.handle(m).ack == AckCode::Ok && c.requestStatus);
  m.commandId = 101;
  m.command = CommandType::SetLocalLed;
  assert(c.handle(m).ack == AckCode::Unsupported);
  MockRadio radio;
  radio.success = false;
  PendingCommand p(radio);
  m.commandId = 400;
  m.device = 2;
  assert(p.start(m, 0xffffff00));
  assert(!p.start(m, 0));
  assert(radio.calls == 1);
  Message ack;
  ack.type = Type::Ack;
  ack.commandId = 401;
  assert(!p.ack(ack));
  ack.commandId = 400;
  ack.type = Type::Telemetry;
  assert(!p.ack(ack));
  p.tick(uint32_t(0xffffff00u + 799));
  assert(radio.calls == 1);
  p.tick(uint32_t(0xffffff00u + 800));
  assert(radio.calls == 2 && p.active);
  p.tick(uint32_t(0xffffff00u + 1600));
  assert(radio.calls == 3);
  p.tick(uint32_t(0xffffff00u + 2400));
  assert(!p.active && p.completion == Completion::Timeout && radio.calls == 3);
  assert(!p.ack(ack));
  assert(p.start(m, 0));
  ack.type = Type::Ack;
  ack.ack = AckCode::InvalidParameter;
  assert(p.ack(ack) && p.code == AckCode::InvalidParameter &&
         p.completion == Completion::Acknowledged);
  assert(!p.ack(ack));
  p.tick(10000);
  assert(radio.calls == 4);
  Message decoded;
  assert(deserialize(radio.bytes, radio.size, decoded) &&
         decoded.commandId == 400);
  puts("PASS commands: interval bounds, status, unsupported LED, "
       "idempotency/conflict, ACK correlation, timeout/retry and clock wrap");
}
void sensing() {
  MockEnergySensor sensor;
  assert(sensor.begin());
  Reading r = sensor.read();
  assert(r.status == Status::Simulated && r.voltage == 12000 &&
         r.current == 125 && r.power == 1500);
  auto real = convertIna(uint16_t((3000 << 3) | 2), 1250, 100);
  assert(real.status == Status::Ok && real.voltage == 12000 &&
         real.current == 125 && real.power == 1500);
  auto negative = convertIna(uint16_t((3000 << 3) | 2), -1250, 100);
  assert(negative.current == -125 && negative.power == -1500);
  assert(convertIna(2, 1, 0).status == Status::SensorError);
  assert(convertIna(3, 1, 100).status == Status::SensorError);
  assert(convertIna(0, 1, 100).status == Status::SensorError);
  Integrator e;
  e.sample(r, 0);
  e.sample(r, 1200);
  assert(e.mwh == 0);
  e.sample(r, 2400);
  assert(e.mwh == 1);
  sensor.fault = true;
  auto bad = sensor.read();
  assert(bad.status == Status::SensorError && bad.voltage == 0 &&
         bad.current == 0 && bad.power == 0);
  e.sample(bad, 3600);
  e.sample(r, 10000);
  assert(e.mwh == 1);
  e.sample(r, 12400);
  assert(e.mwh == 2);
  Integrator wrap;
  wrap.sample(r, 0xffffff00);
  wrap.sample(r, uint32_t(0xffffff00u + 2400));
  assert(wrap.mwh == 1);
  MockMqtt broker;
  Message m;
  m.type = Type::Telemetry;
  m.status = Status::Simulated;
  m.voltage = r.voltage;
  m.power = r.power;
  m.energy = 2;
  assert(forwardTelemetry(broker, m) && broker.calls == 1);
  assert(!strcmp(broker.topic, "energy/node01/telemetry"));
  assert(strstr(broker.payload, "\"sensor_status\":1") &&
         strstr(broker.payload, "\"power_mw\":1500"));
  broker.success = false;
  assert(!forwardTelemetry(broker, m));
  m.type = Type::Command;
  assert(!forwardTelemetry(broker, m) && broker.calls == 2);
  puts("PASS sensing/MQTT: simulated/error states, INA units, energy "
       "integration/gaps/wrap, actual shared forwarding to mock broker");
}
int main() {
  framing();
  sequences();
  commands();
  sensing();
  puts("ALL ENERGY HOST TESTS PASS (no physical radio or sensor verified)");
}
