#include "Config.h"
#include "Radio.h"
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <Runtime.h>
#include <WebServer.h>
#ifndef NODE_ROLE_COLLECTOR
#error Wrong node role
#endif
using namespace energy;
Radio radio;
PendingCommand pending(radio);
Sequence incoming;
WiFiClient tcp;
PubSubClient client(tcp);
WebServer web(80);
uint32_t sequence = 0, lastSeen = 0, lastWifiAttempt = 0, lastMqttAttempt = 0,
         lastState = 0;
uint32_t invalid = 0, duplicates = 0, received = 0, mqttFailures = 0,
         mqttPublished = 0, commandRejected = 0;
uint32_t usedIds[8]{};
size_t usedCount = 0, usedNext = 0;
bool seen = false, online = false, haveTelemetry = false, radioReady = false,
     wasWifi = false;
Message latest;
Status sensorStatus = Status::SensorError;
char result[192]{};
bool resultPending = false;
class Broker : public MqttTransport {
public:
  bool publish(const char *topic, const char *payload, bool retained) override {
    bool ok = client.connected() && client.publish(topic, payload, retained);
    if (ok)
      ++mqttPublished;
    else
      ++mqttFailures;
    return ok;
  }
} broker;
void publishEvent(const char *text) {
  broker.publish("energy/node01/event", text, false);
}
void commandResult(uint32_t id, const char *state, int code) {
  snprintf(result, sizeof result,
           "{\"command_id\":%lu,\"result\":\"%s\",\"code\":%d}",
           (unsigned long)id, state, code);
  resultPending = true;
}
bool used(uint32_t id) {
  for (size_t i = 0; i < usedCount; ++i)
    if (usedIds[i] == id)
      return true;
  return false;
}
void mqttCommand(char *topic, uint8_t *payload, unsigned int length) {
  if (strcmp(topic, "energy/node01/command"))
    return;
  // MQTT cannot signal retained deliveries to this callback. Only safe
  // diagnostics accepted.
  StaticJsonDocument<256> doc;
  if (length > 192 || deserializeJson(doc, payload, length) ||
      !doc["command_id"].is<uint32_t>() || !doc["command_type"].is<uint8_t>() ||
      !doc["command_parameter"].is<uint32_t>()) {
    ++commandRejected;
    publishEvent("{\"error\":\"invalid_command_schema\"}");
    return;
  }
  uint32_t id = doc["command_id"];
  unsigned type = doc["command_type"];
  if (type < 1 || type > 2 ||
      (type == 1 && !validInterval(doc["command_parameter"])) ||
      (type == 2 && doc["command_parameter"].as<uint32_t>() != 0)) {
    ++commandRejected;
    publishEvent("{\"error\":\"unsupported_or_invalid_parameter\"}");
    return;
  }
  if (pending.active || resultPending || used(id) || !online) {
    ++commandRejected;
    publishEvent("{\"error\":\"busy_duplicate_or_offline\"}");
    return;
  }
  Message m;
  m.type = Type::Command;
  m.device = 2;
  m.sequence = sequence++;
  m.uptime = millis();
  m.commandId = id;
  m.command = CommandType(type);
  m.parameter = doc["command_parameter"];
  if (pending.start(m, millis())) {
    usedIds[usedNext++ % 8] = id;
    if (usedCount < 8)
      ++usedCount;
  }
}
void telemetryJson(char *out, size_t size) {
  if (!haveTelemetry) {
    snprintf(out, size, "{\"available\":false}");
    return;
  }
  energy::telemetryJson(latest, out, size);
}
void statusJson(char *out, size_t size) {
  snprintf(out, size,
           "{\"wifi_connected\":%s,\"wifi_channel\":%d,\"espnow_ready\":%s,"
           "\"mqtt_connected\":%s,\"sensor_seen\":%s,\"sensor_online\":%s,"
           "\"sensor_status\":%u,\"age_ms\":%lu,\"command_pending\":%s}",
           WiFi.status() == WL_CONNECTED ? "true" : "false", WiFi.channel(),
           radioReady ? "true" : "false", client.connected() ? "true" : "false",
           seen ? "true" : "false", online ? "true" : "false",
           unsigned(sensorStatus),
           (unsigned long)(seen ? uint32_t(millis() - lastSeen) : 0),
           pending.active ? "true" : "false");
}
void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  if (strlen(WIFI_SSID))
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(mqttCommand);
  client.setBufferSize(512);
  client.setSocketTimeout(1);
  tcp.setTimeout(1000);
  web.on("/", HTTP_GET, [] {
    web.send(
        200, "text/html",
        "<h1>Energy Collector</h1><p>Read-only diagnostics</p><a "
        "href='/api/status'>Status</a> <a href='/api/telemetry'>Telemetry</a> "
        "<a href='/api/diagnostics'>Diagnostics</a>");
  });
  web.on("/api/status", HTTP_GET, [] {
    char out[512];
    statusJson(out, sizeof out);
    web.send(200, "application/json", out);
  });
  web.on("/api/telemetry", HTTP_GET, [] {
    char out[384];
    telemetryJson(out, sizeof out);
    web.send(200, "application/json", out);
  });
  web.on("/api/diagnostics", HTTP_GET, [] {
    char out[512];
    snprintf(out, sizeof out,
             "{\"received\":%lu,\"invalid\":%lu,\"duplicates\":%lu,\"rx_"
             "dropped\":%lu,\"peer_rejected\":%lu,\"tx_queued\":%lu,\"send_"
             "failed\":%lu,\"mac_success\":%lu,\"mac_failed\":%lu,\"mqtt_"
             "published\":%lu,\"mqtt_failed\":%lu,\"command_rejected\":%lu}",
             (unsigned long)received, (unsigned long)invalid,
             (unsigned long)duplicates, (unsigned long)radio.dropped.load(),
             (unsigned long)radio.rejected.load(),
             (unsigned long)radio.enqueued.load(),
             (unsigned long)radio.sendFailure.load(),
             (unsigned long)radio.macSuccess.load(),
             (unsigned long)radio.macFailure.load(),
             (unsigned long)mqttPublished, (unsigned long)mqttFailures,
             (unsigned long)commandRejected);
    web.send(200, "application/json", out);
  });
  web.begin();
  Serial.printf("COLLECTOR mac=%s; waiting for configured WiFi/AP channel\n",
                WiFi.macAddress().c_str());
}
void loop() {
  uint32_t now = millis();
  bool wifi = WiFi.status() == WL_CONNECTED;
  if (!wifi && uint32_t(now - lastWifiAttempt) >= 10000 && strlen(WIFI_SSID)) {
    lastWifiAttempt = now;
    WiFi.reconnect();
  }
  if (wifi && !wasWifi) {
    Serial.printf("WiFi connected channel=%d ip=%s\n", WiFi.channel(),
                  WiFi.localIP().toString().c_str());
    if (!radioReady)
      radioReady = radio.begin(SENSOR_MAC);
  }
  if (!wifi && wasWifi) {
    client.disconnect();
    Serial.println("WiFi disconnected; commands may timeout");
  }
  wasWifi = wifi;
  // STA determines channel. Never call esp_wifi_set_channel on Collector.
  if (wifi && strlen(MQTT_HOST) && !client.connected() &&
      uint32_t(now - lastMqttAttempt) >= 5000) {
    lastMqttAttempt = now;
    char id[40];
    uint64_t chip = ESP.getEfuseMac();
    snprintf(id, sizeof id, "energy-collector-%llx", (unsigned long long)chip);
    if (client.connect(id, MQTT_USER, MQTT_PASSWORD, "energy/node01/state", 0,
                       true, "{\"collector_online\":false}")) {
      client.subscribe("energy/node01/command");
      publishEvent("{\"event\":\"collector_connected\"}");
      lastState = now - 5000;
    } else
      ++mqttFailures;
  }
  client.loop();
  web.handleClient();
  online = seen && uint32_t(now - lastSeen) < 15000;
  if (!online)
    incoming.reset();
  Message m;
  bool valid;
  while (radio.receive(m, valid)) {
    if (!valid || m.device != 1 || m.type == Type::Command) {
      ++invalid;
      continue;
    }
    if (!incoming.accept(m.sequence)) {
      ++duplicates;
      continue;
    }
    ++received;
    seen = true;
    lastSeen = now;
    online = true;
    switch (m.type) {
    case Type::Telemetry: {
      latest = m;
      haveTelemetry = true;
      sensorStatus = m.status;
      forwardTelemetry(broker, m);
      break;
    }
    case Type::Ack:
      if (!pending.ack(m)) {
        ++invalid;
      }
      break;
    case Type::Heartbeat:
      sensorStatus = m.status;
      break;
    case Type::Error:
      publishEvent("{\"error\":\"SENSOR_ERROR\"}");
      break;
    default:
      break;
    }
  }
  pending.tick(now);
  if (pending.completion != Completion::None) {
    commandResult(
        pending.id,
        pending.completion == Completion::Timeout ? "timeout" : "acknowledged",
        pending.completion == Completion::Timeout ? -1 : int(pending.code));
    pending.completion = Completion::None;
  }
  if (resultPending && client.connected() &&
      broker.publish("energy/node01/ack", result, false))
    resultPending = false;
  if (uint32_t(now - lastState) >= 5000) {
    lastState = now;
    char out[512];
    statusJson(out, sizeof out);
    broker.publish("energy/node01/state", out, true);
    Serial.println(out);
  }
  delay(1);
}
