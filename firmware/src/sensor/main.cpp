#include "Config.h"
#include "INA219EnergySensor.h"
#include "Radio.h"
#ifndef NODE_ROLE_SENSOR
#error Wrong node role
#endif
using namespace energy;
Radio radio;
#if USE_MOCK_SENSOR
MockEnergySensor sensor;
#else
INA219EnergySensor sensor;
#endif
Commands commands;
Integrator integrator;
Sequence commandSequence;
uint32_t sequence = 0, lastSample = 0, lastHeartbeat = 0, lastCommand = 0,
         sensorErrors = 0, acknowledged = 0, invalid = 0, duplicates = 0;
Status sensorStatus = Status::SensorError;
void heartbeat() {
  Message m;
  m.type = Type::Heartbeat;
  m.status = sensorStatus;
  m.interval = commands.interval;
  m.sensorErrors = sensorErrors;
  radio.sendMessage(m, 1, sequence);
}
void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  bool channel =
      SENSOR_CHANNEL >= 1 && SENSOR_CHANNEL <= 13 &&
      esp_wifi_set_channel(SENSOR_CHANNEL, WIFI_SECOND_CHAN_NONE) == ESP_OK;
  bool initialized = sensor.begin();
  bool ready = channel && radio.begin(COLLECTOR_MAC);
  Serial.printf("SENSOR mac=%s channel=%d radio=%d mock=%d sensor_init=%d\n",
                WiFi.macAddress().c_str(), SENSOR_CHANNEL, ready,
                USE_MOCK_SENSOR, initialized);
}
void loop() {
  uint32_t now = millis();
  Message cmd;
  bool valid;
  while (radio.receive(cmd, valid)) {
    if (!valid || cmd.device != 2 || cmd.type != Type::Command) {
      ++invalid;
      continue;
    }
    if (uint32_t(now - lastCommand) > 15000)
      commandSequence.reset();
    bool fresh = commandSequence.accept(cmd.sequence);
    if (!fresh && !commands.cached(cmd.commandId)) {
      ++duplicates;
      continue;
    }
    lastCommand = now;
    Message ack = commands.handle(cmd);
    if (radio.sendMessage(ack, 1, sequence))
      ++acknowledged;
  }
  if (uint32_t(now - lastSample) >= commands.interval) {
    lastSample = now;
    Reading r = sensor.read();
    sensorStatus = r.status;
    Message m;
    m.type = Type::Telemetry;
    m.status = r.status;
    m.voltage = r.voltage;
    m.current = r.current;
    m.power = r.power;
    m.energy = integrator.sample(r, now);
    if (r.status == Status::SensorError) {
      ++sensorErrors;
      Message e;
      e.type = Type::Error;
      e.error = 1;
      radio.sendMessage(e, 1, sequence);
    }
    radio.sendMessage(m, 1, sequence);
  }
  if (commands.requestStatus || uint32_t(now - lastHeartbeat) >= 5000) {
    commands.requestStatus = false;
    lastHeartbeat = now;
    heartbeat();
    Serial.printf("sensor status=%u interval=%lu queued=%lu failed=%lu "
                  "mac_ok=%lu mac_fail=%lu ack_queued=%lu sensor_errors=%lu "
                  "invalid=%lu duplicate=%lu dropped=%lu\n",
                  unsigned(sensorStatus), (unsigned long)commands.interval,
                  (unsigned long)radio.enqueued.load(),
                  (unsigned long)radio.sendFailure.load(),
                  (unsigned long)radio.macSuccess.load(),
                  (unsigned long)radio.macFailure.load(),
                  (unsigned long)acknowledged, (unsigned long)sensorErrors,
                  (unsigned long)invalid, (unsigned long)duplicates,
                  (unsigned long)radio.dropped.load());
  }
  delay(1);
}
