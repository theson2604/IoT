"""Stable REST response schemas, exposed in /docs."""
from typing import Literal
from pydantic import BaseModel

class Health(BaseModel):
    status: str
    mqtt_connected: bool
    schema_version: int

class DeviceStatus(BaseModel):
    device_id: str
    online: bool
    collector_online: bool
    mqtt_connected: bool
    sensor_status: int | None
    last_telemetry_at: float | None
    last_state_at: float | None
    state: dict
    simulation_mode: bool

class Devices(BaseModel):
    items: list[DeviceStatus]

class Measurement(BaseModel):
    id: int
    schema_version: Literal[1]
    device_id: str
    sequence_number: int
    sender_uptime_ms: int | None
    received_at: float
    voltage_v: float | None
    current_a: float | None
    power_w: float | None
    energy_wh: float
    sensor_status: int
    simulated: bool
    valid: bool

class History(BaseModel):
    items: list[Measurement]

class CommandResult(BaseModel):
    command_id: str
    wire_id: int
    device_id: str
    created_at: float
    deadline: float
    status: Literal['pending','success','failed','timeout','publish_failed','interrupted']
    code: int | None

class EventRecord(BaseModel):
    id: int
    received_at: float
    kind: str
    data: dict

class Events(BaseModel):
    items: list[EventRecord]
