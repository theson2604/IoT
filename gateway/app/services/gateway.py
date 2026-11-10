"""MQTT routing, durable command correlation and device state, independently testable."""
import json
import logging
import time
import uuid
from pydantic import ValidationError
from gateway.app.models.contracts import Telemetry, State, Ack, Event, CommandRequest, WireCommand
from gateway.app.mqtt.transport import TOPIC
from gateway.app.storage.mongodb import Store
from pymongo.errors import DuplicateKeyError

log = logging.getLogger(__name__)

class Conflict(ValueError):
    pass

class Unavailable(ValueError):
    pass

def decode(payload):
    if len(payload) > 4096:
        raise ValueError('Payload exceeds 4096 bytes')
    return json.loads(payload, parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))

class Gateway:
    def __init__(self, settings, transport, clock=time.time):
        self.settings, self.transport, self.clock = settings, transport, clock
        self.store = Store(settings)
        self.lock = self.store.lock
        self.last_prune = 0
        self.invalid_messages = 0
        self.duplicate_messages = 0
        # Stored snapshots are informational until fresh evidence arrives this process lifetime.
        self.live_at = None
        self.live_state_at = None

    def handle(self, topic, payload, retained=False):
        if topic not in {TOPIC + t for t in ('telemetry','state','ack','event')}:
            return False
        with self.lock:
            now = self.clock()
            try:
                body = decode(payload)
                suffix = topic.rsplit('/',1)[1]
                if suffix == 'telemetry':
                    if retained:
                        raise ValueError('Retained telemetry is not fresh data')
                    model = Telemetry.model_validate(body)
                    if not self.settings.simulation_mode and model.sensor_status == 1:
                        raise ValueError('Simulated telemetry disabled by configuration')
                    d = self.store.device()
                    previous = d.get('sequence')
                    previous_at = d.get('telemetry_at', 0)
                    if previous is not None and now - previous_at < self.settings.offline_seconds:
                        delta = (model.sequence_number - previous) & 0xffffffff
                        if not 0 < delta < 0x80000000:
                            self.duplicate_messages += 1
                            return False
                    normalized = model.normalize(now)
                    if not self.store.measurement(normalized, self.settings.offline_seconds):
                        self.duplicate_messages += 1
                        return False
                    self.store.save_device(dict(sequence=model.sequence_number, telemetry_at=now, sensor_status=model.sensor_status))
                    self.live_at = now
                elif suffix == 'state':
                    state = State.model_validate(body).model_dump(exclude_none=True)
                    d = self.store.device()
                    self.store.save_device(dict(state=state, state_received_at=now, state_retained=retained))
                    if not retained:
                        self.live_state_at = now
                elif suffix == 'ack':
                    if retained:
                        raise ValueError('Retained ACK rejected')
                    ack = Ack.model_validate(body)
                    self.store.expire(now)
                    status = 'success' if ack.result == 'acknowledged' and ack.code == 0 else ('timeout' if ack.result == 'timeout' else 'failed')
                    if not self.store.acknowledge(ack, status, now):
                        self.store.event(now, 'unmatched_ack', ack.model_dump())
                else:
                    event = Event.model_validate(body)
                    self.store.event(now, 'device_event', event.model_dump(exclude_none=True))
                return True
            except (ValidationError, ValueError, TypeError, UnicodeError) as exc:
                self.invalid_messages += 1
                # No raw payload/credentials in logs or error events.
                log.warning('Rejected MQTT payload on %s (%s)', topic, type(exc).__name__)
                self.store.event(now, 'invalid_payload', {'topic': topic, 'reason': type(exc).__name__})
                return False

    def status(self):
        with self.lock:
            now = self.clock()
            d = self.store.device()
            evidence = max(t for t in (self.live_at, self.live_state_at, -1) if t is not None)
            fresh = evidence >= 0 and 0 <= now - evidence < self.settings.offline_seconds
            state = d.get('state', {})
            state_newer = d.get('state_received_at', -1) >= (self.live_at if self.live_at is not None else -1)
            collector = fresh and self.transport.connected
            sensor = fresh
            if state_newer:
                # A retained last will is useful negative evidence; retained online is never proof of life.
                collector = collector and state.get('collector_online', True) and state.get('wifi_connected', True) and state.get('mqtt_connected', True)
                sensor = sensor and state.get('sensor_online', False)
            return dict(device_id='node01', online=bool(collector and sensor), collector_online=bool(collector),
                        mqtt_connected=self.transport.connected,
                        sensor_status=state.get('sensor_status', d.get('sensor_status')) if state_newer else d.get('sensor_status'),
                        last_telemetry_at=d.get('telemetry_at'),
                        last_state_at=d.get('state_received_at'), state=state,
                        simulation_mode=self.settings.simulation_mode)

    def create_command(self, request: CommandRequest):
        with self.lock:
            now = self.clock()
            public_id = request.command_id or uuid.uuid4().hex
            fingerprint = json.dumps({'method':request.method,'params':request.params.model_dump()}, sort_keys=True)
            existing = self.store.command(public_id)
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise Conflict('Command ID already used with different content')
                return existing  # Idempotent API retry: never republish.
            self.store.expire(now)
            if self.store.pending():
                raise Conflict('One command is already pending')
            if not self.status()['online']:
                raise Unavailable('Device or broker is offline')
            try:
                wire_id = self.store.new_command(public_id, fingerprint, now, self.settings.command_timeout)
            except DuplicateKeyError as exc:
                existing = self.store.command(public_id)
                if existing and existing['fingerprint'] == fingerprint:
                    return existing
                raise Conflict('Duplicate command ID or pending command') from exc
            except ValueError as exc:
                raise Unavailable(str(exc)) from exc
            wire = WireCommand(command_id=wire_id, command_type=1 if request.method=='set_sampling_interval' else 2,
                               command_parameter=request.params.interval_ms or 0)
            if not self.transport.publish(TOPIC+'command', wire.model_dump_json().encode(), retain=False):
                self.store.publish_failed(wire_id)
            return self.store.command(public_id)

    def tick(self):
        with self.lock:
            self.store.expire(self.clock())
            for message in self.transport.drain():
                self.handle(message.topic, message.payload, message.retained)
            now = self.clock()
            if now - self.last_prune >= 1:
                self.store.prune(now, self.settings)
                self.last_prune = now

    def close(self):
        with self.lock:
            self.store.close()
