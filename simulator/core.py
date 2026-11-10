"""Deterministic, clock-driven two-node simulation; no threads, sleeps or RF claims."""
from collections import OrderedDict
from dataclasses import dataclass
import heapq
import json
import math
import random
from gateway.app.models.contracts import WireCommand
from gateway.app.mqtt.transport import TOPIC
from gateway.app.services.gateway import decode
from simulator.wire import Frame, Sequence

SCENARIOS = ('normal','load_change','high_power','sensor_error','link_failure','mqtt_disconnect','command_timeout')

@dataclass
class Options:
    scenario: str = 'normal'
    seed: int = 1
    loss: float = 0
    duplicate: float = 0
    delay_ms: int = 0
    jitter_ms: int = 0
    fault_at: float = 5
    fault_duration: float = 5
    current_ma: int = 125
    changed_current_ma: int = 1000
    fluctuation_ma: int = 5
    load_changes: tuple = ()  # (elapsed seconds, current mA)
    sensor_disconnect_at: float | None = None
    collector_disconnect_at: float | None = None

    def __post_init__(self):
        times = [self.fault_at,self.fault_duration] + [v for v in (self.sensor_disconnect_at,self.collector_disconnect_at) if v is not None]
        if any(not math.isfinite(t) or t < 0 for t in times):
            raise ValueError('Fault/disconnection times must be finite and nonnegative')
        if self.scenario not in SCENARIOS or not 0 <= self.loss <= 1 or not 0 <= self.duplicate <= 1:
            raise ValueError('Invalid scenario or link probabilities')
        if min(self.delay_ms,self.jitter_ms,self.fault_at,self.fault_duration,self.current_ma,self.changed_current_ma,self.fluctuation_ma) < 0:
            raise ValueError('Scenario parameters must be nonnegative')
        if max(self.current_ma,self.changed_current_ma) > 1000000:
            raise ValueError('Simulation current exceeds bounds')
        for at, current in self.load_changes:
            if at < 0 or not 0 <= current <= 1000000:
                raise ValueError('Invalid load change')

    def fault(self, elapsed):
        return self.fault_at <= elapsed < self.fault_at + self.fault_duration

class Link:
    def __init__(self, options):
        self.options = options
        self.rng = random.Random(options.seed)
        self.queue = []
        self.counter = 0
        self.dropped = 0
        self.delivered = 0

    def send(self, destination, frame, now, *, disconnected=False):
        loss = self.options.loss
        if self.options.scenario == 'link_failure' and self.options.fault(now):
            disconnected = True
        if disconnected or self.rng.random() < loss or len(self.queue) >= 256:
            self.dropped += 1
            return False
        payload = frame.encode()
        copies = 2 if self.rng.random() < self.options.duplicate else 1
        for _ in range(copies):
            if len(self.queue) >= 256:
                self.dropped += 1
                break
            delay = self.options.delay_ms + self.rng.randint(0,self.options.jitter_ms)
            self.counter += 1
            heapq.heappush(self.queue,(now+delay/1000,self.counter,destination,payload))
        return True

    def due(self, now):
        while self.queue and self.queue[0][0] <= now:
            _,_,destination,payload = heapq.heappop(self.queue)
            self.delivered += 1
            yield destination, Frame.decode(payload)

class Sensor:
    def __init__(self, options):
        self.options = options
        self.rng = random.Random(options.seed+1)
        self.interval = 1000
        self.sequence = 0
        self.next_sample = 0
        self.next_heartbeat = 0
        self.energy = 0
        self.remainder = 0
        self.previous_time = None
        self.previous_power = 0
        self.previous_valid = False
        self.status = 1
        self.errors = 0
        self.cache = OrderedDict()
        self.command_sequence = Sequence()
        self.last_command = None

    def frame(self, kind, values, now):
        frame = Frame(kind,1,self.sequence,int(now*1000)&0xffffffff,tuple(values))
        self.sequence = (self.sequence+1)&0xffffffff
        return frame

    def read(self, now):
        error = self.options.scenario == 'sensor_error' and self.options.fault(now)
        current = self.options.current_ma
        if self.options.scenario in ('high_power','load_change') and now >= self.options.fault_at:
            current = self.options.changed_current_ma
        for at, value in sorted(self.options.load_changes):
            if now >= at:
                current = value
        current = max(0,current+self.rng.randint(-self.options.fluctuation_ma,self.options.fluctuation_ma))
        voltage = 12000 if not error else 0
        current = current if not error else 0
        power = voltage*current//1000
        timestamp = int(now*1000)
        if self.previous_time is not None and self.previous_valid and not error:
            total = self.previous_power*(timestamp-self.previous_time)+self.remainder
            delta,self.remainder = divmod(total,3600000)
            self.energy = min(0xffffffffffffffff,self.energy+delta)
        self.previous_time,self.previous_power,self.previous_valid = timestamp,power,not error
        self.status = 2 if error else 1  # Even error-free synthetic data is SIMULATED.
        return voltage,current,power,self.energy,self.status

    def tick(self, now):
        frames = []
        if now >= self.next_sample:
            self.next_sample = now+self.interval/1000
            frames.append(self.frame(1,self.read(now),now))
            if self.status == 2:
                self.errors += 1
                frames.append(self.frame(5,(1,),now))
        if now >= self.next_heartbeat:
            self.next_heartbeat = now+5
            frames.append(self.frame(4,(self.status,self.interval,self.errors),now))
        return frames

    def command(self, frame, now):
        if frame.type != 2 or frame.device != 2:
            return []
        identifier,kind,parameter = frame.values
        if self.last_command is None or now-self.last_command > 15:
            self.command_sequence.reset()
        fresh = self.command_sequence.accept(frame.sequence)
        if not fresh and identifier not in self.cache:
            return []
        self.last_command = now
        request_status = False
        if identifier in self.cache:
            old_kind,old_parameter,code,interval = self.cache[identifier]
            if (kind,parameter) != (old_kind,old_parameter):
                code = 3
        else:
            code = 2
            if kind == 1:
                code = 0 if 100 <= parameter <= 60000 else 1
                if code == 0:
                    self.interval = parameter
                    self.next_sample = min(self.next_sample,now+self.interval/1000)
            elif kind == 2:
                code = 0 if parameter == 0 else 1
                request_status = code == 0
            interval = self.interval
            self.cache[identifier] = (kind,parameter,code,interval)
            if len(self.cache)>8:
                self.cache.popitem(last=False)
        frames = [self.frame(3,(identifier,code,interval),now)]
        if request_status:
            frames.append(self.frame(4,(self.status,self.interval,self.errors),now))
        return frames

class Simulation:
    def __init__(self, transport, options=None):
        self.transport = transport
        self.options = options or Options()
        self.sensor = Sensor(self.options)
        self.link = Link(self.options)
        self.sequence = 0
        self.incoming = Sequence()
        self.last_seen = None
        self.pending = None
        self.used_ids = []
        self.result = None
        self.next_state = 0
        self.duplicates = 0
        self.mqtt_fault = False

    def sensor_down(self, now):
        return self.options.sensor_disconnect_at is not None and now >= self.options.sensor_disconnect_at

    def collector_down(self, now):
        return self.options.collector_disconnect_at is not None and now >= self.options.collector_disconnect_at

    def online(self, now):
        return self.last_seen is not None and now-self.last_seen < 15

    def publish(self, suffix, body, retain=False):
        return self.transport.publish(TOPIC+suffix,json.dumps(body,separators=(',',':')).encode(),retain=retain)

    def command(self, payload, now, retained=False):
        try:
            if retained:
                raise ValueError('Retained command')
            command = WireCommand.model_validate(decode(payload))
        except ValueError:
            self.publish('event', {'error':'invalid_command_schema'})
            return
        if self.pending or self.result or command.command_id in self.used_ids or not self.online(now):
            self.publish('event',{'error':'busy_duplicate_or_offline'})
            return
        frame = Frame(2,2,self.sequence,int(now*1000)&0xffffffff,
                      (command.command_id,command.command_type,command.command_parameter))
        self.sequence = (self.sequence+1)&0xffffffff
        self.pending = dict(frame=frame,attempts=1,last=now)
        self.used_ids = (self.used_ids+[command.command_id])[-8:]
        self.link.send('sensor',frame,now,disconnected=self.sensor_down(now))

    def _receive_collector(self, frame, now):
        if frame.device != 1 or frame.type == 2:
            return
        if not self.incoming.accept(frame.sequence):
            self.duplicates += 1
            return
        self.last_seen = now
        if frame.type == 1:
            voltage,current,power,energy,status = frame.values
            self.publish('telemetry',dict(schema_version=1,device_id='node01',available=True,
                sequence_number=frame.sequence,sender_uptime_ms=frame.uptime,
                voltage_mv=voltage,current_ma=current,power_mw=power,energy_mwh=energy,sensor_status=status))
        elif frame.type == 3 and self.pending and frame.values[0] == self.pending['frame'].values[0]:
            self.result = dict(command_id=frame.values[0],result='acknowledged',code=frame.values[1])
            self.pending = None
        elif frame.type == 5:
            self.publish('event',{'error':'SENSOR_ERROR'})

    def tick(self, now):
        # now is elapsed simulation seconds, not UTC and not a fake Unix device timestamp.
        fault = self.options.scenario == 'mqtt_disconnect' and self.options.fault(now)
        if fault and not self.mqtt_fault:
            self.publish('state',{'collector_online':False},retain=True)
            self.transport.stop()
        elif self.mqtt_fault and not fault:
            self.transport.start()
            self.next_state = now
        self.mqtt_fault = fault
        if self.collector_down(now):
            self.publish('state',{'collector_online':False},retain=True)
            self.transport.stop()
            return
        for message in self.transport.drain():
            if message.topic == TOPIC+'command':
                self.command(message.payload,now,message.retained)
        if not self.online(now):
            self.incoming.reset()
        if not self.sensor_down(now):
            for frame in self.sensor.tick(now):
                self.link.send('collector',frame,now)
        # Bounded processing of zero-delay command -> sensor -> ACK chains.
        for _ in range(4):
            deliveries = list(self.link.due(now))
            if not deliveries:
                break
            for destination,frame in deliveries:
                if destination == 'sensor' and not self.sensor_down(now):
                    for reply in self.sensor.command(frame,now):
                        suppress = reply.type == 3 and self.options.scenario == 'command_timeout'
                        self.link.send('collector',reply,now,disconnected=suppress)
                elif destination == 'collector':
                    self._receive_collector(frame,now)
        if self.pending and now-self.pending['last'] >= 0.8-1e-9:
            if self.pending['attempts'] >= 3:
                self.result = dict(command_id=self.pending['frame'].values[0],result='timeout',code=-1)
                self.pending = None
            else:
                self.pending['attempts'] += 1
                self.pending['last'] = now
                self.link.send('sensor',self.pending['frame'],now,disconnected=self.sensor_down(now))
        if self.result and self.publish('ack',self.result):
            self.result = None
        if now >= self.next_state:
            self.next_state = now+5
            self.publish('state',dict(wifi_connected=True,wifi_channel=1,espnow_ready=True,
                mqtt_connected=self.transport.connected,sensor_seen=self.last_seen is not None,
                sensor_online=self.online(now),sensor_status=self.sensor.status,
                age_ms=int((now-self.last_seen)*1000) if self.last_seen is not None else 0,
                command_pending=self.pending is not None),retain=True)
