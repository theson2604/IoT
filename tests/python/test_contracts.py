import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from gateway.app.models.contracts import Telemetry, CommandRequest, Ack
from simulator.wire import Frame, Sequence

SAMPLE = dict(schema_version=1,device_id='node01',available=True,sequence_number=42,
    sender_uptime_ms=1000,voltage_mv=12000,current_ma=125,power_mw=1500,energy_mwh=2,sensor_status=1)

def test_units_and_legacy():
    normalized = Telemetry.model_validate(SAMPLE).normalize(1700000000)
    assert normalized['voltage_v']==12 and normalized['current_a']==0.125
    assert normalized['power_w']==1.5 and normalized['energy_wh']==0.002
    assert normalized['sender_uptime_ms']==1000 and normalized['received_at']==1700000000
    assert normalized['simulated'] is True and normalized['valid'] is True
    legacy = {k:v for k,v in SAMPLE.items() if k not in ('schema_version','device_id','sender_uptime_ms')}
    assert Telemetry.model_validate(legacy).sender_uptime_ms is None

@pytest.mark.parametrize('key,value', [('sequence_number',-1),('sequence_number',2**32),('current_ma',True),
    ('power_mw',1.5),('energy_mwh',-1),('sensor_status',3),('schema_version',2),('schema_version',True),('available',1),('device_id','node02'),
    ('voltage_mv',-1),('sender_uptime_ms',-1)])
def test_invalid_telemetry(key,value):
    with pytest.raises(ValidationError):
        Telemetry.model_validate({**SAMPLE,key:value})

def test_error_is_missing_not_zero_load():
    data = Telemetry.model_validate({**SAMPLE,'sensor_status':2,'voltage_mv':0,'power_mw':0,'current_ma':0}).normalize(5)
    assert data['voltage_v'] is None and data['current_a'] is None and data['power_w'] is None
    assert data['energy_wh']==0.002 and data['valid'] is False

@pytest.mark.parametrize('interval',[0,99,60001,'1000',True])
def test_invalid_commands(interval):
    with pytest.raises(ValidationError):
        CommandRequest.model_validate(dict(method='set_sampling_interval',params=dict(interval_ms=interval)))

def test_command_ack_validation():
    with pytest.raises(ValidationError):
        CommandRequest.model_validate(dict(method='get_status',params=dict(interval_ms=1000)))
    with pytest.raises(ValidationError):
        Ack(command_id=1,result='acknowledged',code=-1)

def test_cpp_generated_vectors():
    vectors = json.loads((Path(__file__).parents[1]/'fixtures/firmware-vectors.json').read_text())
    values = [(12000,125,1500,2,1),(7,1,2000),(7,0,2000),(1,2000,0),(1,)]
    for kind, ((name, hex_packet), payload) in enumerate(zip(vectors.items(),values),1):
        frame = Frame(kind,2 if kind==2 else 1,42,1000,payload)
        assert frame.encode().hex()==hex_packet,name
        assert Frame.decode(bytes.fromhex(hex_packet))==frame
    raw = bytearray(bytes.fromhex(vectors['telemetry']))
    for i in range(len(raw)):
        raw[i] ^= 1
        with pytest.raises(ValueError):
            Frame.decode(raw)
        raw[i] ^= 1
    for length in range(len(raw)):
        with pytest.raises(ValueError):
            Frame.decode(raw[:length])

def test_wraparound():
    s = Sequence()
    assert s.accept(0xfffffffe) and s.accept(0xffffffff) and s.accept(0)
    assert not s.accept(0) and not s.accept(0xffffffff)

@pytest.mark.parametrize('name',['telemetry','state','command','ack','event'])
def test_documented_examples(name):
    from gateway.app.models.contracts import State, WireCommand, Event
    models = dict(telemetry=Telemetry,state=State,command=WireCommand,ack=Ack,event=Event)
    payload = json.loads((Path(__file__).parents[2]/'docs/examples'/(name+'.json')).read_text())
    models[name].model_validate(payload)
