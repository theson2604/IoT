"""Firmware MQTT boundary and normalized API contract. All units explicit."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

U32 = Annotated[int, Field(ge=0, le=0xffffffff)]
I32 = Annotated[int, Field(ge=-0x80000000, le=0x7fffffff)]
U64 = Annotated[int, Field(ge=0, le=0xffffffffffffffff)]

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)

class Telemetry(StrictModel):
    # Defaults accept earlier firmware; uptime remains explicitly unknown.
    schema_version: Literal[1] = 1
    device_id: Literal['node01'] = 'node01'
    available: Literal[True] = True
    sequence_number: U32
    sender_uptime_ms: U32 | None = None
    voltage_mv: I32
    current_ma: I32
    power_mw: I32
    energy_mwh: U64
    sensor_status: Annotated[int, Field(ge=0, le=2)]

    @field_validator('schema_version', mode='before')
    @classmethod
    def version_integer(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer, not a boolean')
        return value

    @field_validator('available', mode='before')
    @classmethod
    def available_boolean(cls, value):
        if type(value) is not bool:
            raise ValueError('available must be a boolean')
        return value

    @model_validator(mode='after')
    def valid_voltage(self):
        if self.sensor_status != 2 and self.voltage_mv < 0:
            raise ValueError('Bus voltage cannot be negative')
        return self

    def normalize(self, received_at: float):
        bad = self.sensor_status == 2
        return dict(schema_version=1, device_id=self.device_id,
                    sequence_number=self.sequence_number, sender_uptime_ms=self.sender_uptime_ms,
                    received_at=received_at, voltage_v=None if bad else self.voltage_mv / 1000,
                    current_a=None if bad else self.current_ma / 1000,
                    power_w=None if bad else self.power_mw / 1000, energy_wh=self.energy_mwh / 1000,
                    sensor_status=self.sensor_status,
                    simulated=self.sensor_status == 1, valid=not bad)

class State(StrictModel):
    wifi_connected: bool | None = None
    wifi_channel: Annotated[int, Field(ge=0, le=14)] | None = None
    espnow_ready: bool | None = None
    mqtt_connected: bool | None = None
    sensor_seen: bool | None = None
    sensor_online: bool | None = None
    sensor_status: Annotated[int, Field(ge=0, le=2)] | None = None
    age_ms: U32 | None = None
    command_pending: bool | None = None
    collector_online: bool | None = None  # Firmware last-will form.

    @model_validator(mode='after')
    def meaningful(self):
        if not self.model_fields_set:
            raise ValueError('Empty state')
        return self

class WireCommand(StrictModel):
    command_id: U32
    command_type: Literal[1, 2]
    command_parameter: U32

    @model_validator(mode='after')
    def parameters(self):
        if self.command_type == 1 and not 100 <= self.command_parameter <= 60000:
            raise ValueError('interval_ms must be 100..60000')
        if self.command_type == 2 and self.command_parameter != 0:
            raise ValueError('GET_STATUS parameter must be zero')
        return self

class Ack(StrictModel):
    command_id: U32
    result: Literal['acknowledged', 'timeout']
    code: Annotated[int, Field(ge=-1, le=3)]

    @model_validator(mode='after')
    def result_code(self):
        if (self.result == 'timeout') != (self.code == -1):
            raise ValueError('Timeout must have code -1')
        return self

class Event(StrictModel):
    error: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    event: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @model_validator(mode='after')
    def meaningful(self):
        if not self.error and not self.event:
            raise ValueError('Event requires error or event')
        return self

class Params(StrictModel):
    interval_ms: Annotated[int, Field(ge=100, le=60000)] | None = None

class CommandRequest(StrictModel):
    command_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')] | None = None
    method: Literal['get_status', 'set_sampling_interval']
    params: Params = Field(default_factory=Params)

    @model_validator(mode='after')
    def parameters(self):
        if (self.method == 'set_sampling_interval') != (self.params.interval_ms is not None):
            raise ValueError('Only set_sampling_interval requires interval_ms')
        return self
