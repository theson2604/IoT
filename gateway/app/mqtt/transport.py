"""Paho adapter: callbacks only copy to a bounded queue. No queued command replay."""
import logging
import queue
import threading
import uuid
from dataclasses import dataclass
from typing import Protocol
import paho.mqtt.client as mqtt
from gateway.app.config import Settings

log = logging.getLogger(__name__)
TOPIC = 'energy/node01/'

@dataclass(frozen=True)
class Incoming:
    topic: str
    payload: bytes
    retained: bool = False

class Transport(Protocol):
    connected: bool
    def publish(self, topic: str, payload: bytes, *, retain: bool = False) -> bool: ...
    def drain(self) -> list[Incoming]: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

class PahoTransport:
    def __init__(self, settings: Settings, role: str = 'gateway'):
        self.connected = False
        self.queue = queue.Queue(maxsize=256)
        self.dropped = 0
        self.lock = threading.Lock()
        self.settings = settings
        self.role = role
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f'energy-{role}-{uuid.uuid4().hex[:12]}',
                                  protocol=mqtt.MQTTv311, clean_session=True)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.max_queued_messages_set(1)
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self._connect
        self.client.on_connect_fail = self._connect_fail
        self.client.on_disconnect = self._disconnect
        self.client.on_message = self._message
        if role == 'collector':
            self.client.will_set(TOPIC + 'state', '{"collector_online":false}', qos=0, retain=True)

    def _connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if self.connected:
            topics = ['command'] if self.role == 'collector' else ['telemetry', 'state', 'ack', 'event']
            result, _ = client.subscribe([(TOPIC + t, 0) for t in topics])
            if result != mqtt.MQTT_ERR_SUCCESS:
                self.connected = False
                log.error('MQTT subscription failed')
            else:
                log.info('MQTT connected and subscribed (%s)', self.role)
        else:
            log.warning('MQTT connection refused: %s', reason_code)

    def _connect_fail(self, client, userdata):
        self.connected = False
        log.warning("MQTT broker unreachable; retrying (%s)", self.role)

    def _disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        log.warning('MQTT disconnected (%s): %s', self.role, reason_code)

    def _message(self, client, userdata, message):
        if len(message.payload) > 4096:
            self.dropped += 1
            return
        try:
            self.queue.put_nowait(Incoming(message.topic, bytes(message.payload), bool(message.retain)))
        except queue.Full:
            self.dropped += 1

    def publish(self, topic, payload, *, retain=False):
        if topic.endswith('/command') and retain:
            raise ValueError('Commands must never be retained')
        # QoS0 deliberately avoids Paho's QoS1 offline replay queue. Firmware also uses QoS0.
        with self.lock:
            if not self.connected:
                return False
            return self.client.publish(topic, payload, qos=0, retain=retain).rc == mqtt.MQTT_ERR_SUCCESS

    def drain(self):
        messages = []
        for _ in range(256):
            try:
                messages.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def start(self):
        self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=15)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()
        self.connected = False

class MemoryBroker:
    """Synchronous bounded transport fixture, not a real MQTT broker."""
    def __init__(self):
        self.clients = []

    def endpoint(self, role):
        endpoint = MemoryTransport(self, role)
        self.clients.append(endpoint)
        return endpoint

class MemoryTransport:
    def __init__(self, broker, role):
        self.broker, self.role = broker, role
        self.connected = True
        self.queue = queue.Queue(maxsize=256)
        self.dropped = 0

    def publish(self, topic, payload, *, retain=False):
        if topic.endswith('/command') and retain:
            raise ValueError('Commands must never be retained')
        if not self.connected:
            return False
        for c in self.broker.clients:
            accepts = topic == TOPIC+'command' if c.role == 'collector' else topic in [TOPIC+t for t in ('telemetry','state','ack','event')]
            if c.connected and accepts:
                try:
                    c.queue.put_nowait(Incoming(topic, bytes(payload), False))
                except queue.Full:
                    c.dropped += 1
        return True

    def drain(self):
        out = []
        while not self.queue.empty():
            out.append(self.queue.get_nowait())
        return out

    def start(self):
        self.connected = True

    def stop(self):
        self.connected = False
