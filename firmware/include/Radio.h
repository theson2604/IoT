#pragma once
#include <Arduino.h>
#include <Protocol.h>
#include <WiFi.h>
#include <atomic>
#include <esp_now.h>
#include <esp_wifi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
// Arduino-ESP32 2.0.17 / ESP-IDF 4.4 callback signatures.
class Radio : public energy::Transport {
  struct Packet {
    uint8_t bytes[energy::MaxPacket];
    uint8_t length;
  };
  QueueHandle_t queue = nullptr;
  uint8_t peer[6]{};
  bool ready = false;
  static Radio *instance;
  static void received(const uint8_t *mac, const uint8_t *data, int len) {
    Radio *r = instance;
    if (!r)
      return;
    if (memcmp(mac, r->peer, 6) || len < 1 || len > int(energy::MaxPacket)) {
      ++r->rejected;
      return;
    }
    Packet p{};
    p.length = len;
    memcpy(p.bytes, data, len);
    if (xQueueSend(r->queue, &p, 0) != pdTRUE)
      ++r->dropped;
  }
  static void sent(const uint8_t *, esp_now_send_status_t status) {
    if (!instance)
      return;
    if (status == ESP_NOW_SEND_SUCCESS)
      ++instance->macSuccess;
    else
      ++instance->macFailure;
  }

public:
  std::atomic<uint32_t> enqueued{0}, sendFailure{0}, macSuccess{0},
      macFailure{0}, dropped{0}, rejected{0};
  bool begin(const char *mac) {
    unsigned a[6];
    if (strlen(mac) != 17 || sscanf(mac, "%2x:%2x:%2x:%2x:%2x:%2x", &a[0],
                                    &a[1], &a[2], &a[3], &a[4], &a[5]) != 6)
      return false;
    uint8_t any = 0;
    for (int i = 0; i < 6; ++i) {
      peer[i] = a[i];
      any |= peer[i];
    }
    if (!any || (peer[0] & 1))
      return false;
    queue = xQueueCreate(8, sizeof(Packet));
    if (!queue)
      return false;
    if (esp_now_init() != ESP_OK) {
      vQueueDelete(queue);
      queue = nullptr;
      return false;
    }
    esp_now_peer_info_t info{};
    memcpy(info.peer_addr, peer, 6);
    info.channel = 0;
    info.ifidx = WIFI_IF_STA;
    info.encrypt = false;
    if (esp_now_add_peer(&info) != ESP_OK) {
      esp_now_deinit();
      vQueueDelete(queue);
      queue = nullptr;
      return false;
    }
    instance = this;
    if (esp_now_register_recv_cb(received) != ESP_OK ||
        esp_now_register_send_cb(sent) != ESP_OK) {
      instance = nullptr;
      esp_now_deinit();
      vQueueDelete(queue);
      queue = nullptr;
      return false;
    }
    ready = true;
    return true;
  }
  bool send(const uint8_t *data, size_t n) override {
    if (!ready || n > energy::MaxPacket ||
        esp_now_send(peer, data, n) != ESP_OK) {
      ++sendFailure;
      return false;
    }
    ++enqueued;
    return true; // Enqueued != MAC success != application ACK.
  }
  bool receive(energy::Message &m, bool &valid) {
    Packet p{};
    if (!queue || xQueueReceive(queue, &p, 0) != pdTRUE)
      return false;
    valid = energy::deserialize(p.bytes, p.length, m);
    return true;
  }
  bool sendMessage(energy::Message m, uint16_t device, uint32_t &sequence) {
    m.device = device;
    m.sequence = sequence++;
    m.uptime = millis();
    uint8_t p[energy::MaxPacket];
    size_t n = energy::serialize(m, p, sizeof p);
    return n && send(p, n);
  }
};
Radio *Radio::instance = nullptr;
