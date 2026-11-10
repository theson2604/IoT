import json
import pytest
from gateway.app.models.contracts import CommandRequest
from gateway.app.mqtt.transport import TOPIC
from gateway.app.services.gateway import Gateway, Conflict, Unavailable
from tests.python.test_contracts import SAMPLE

def publish(collector,suffix,body):
    collector.publish(TOPIC+suffix,json.dumps(body).encode())

def ready(system):
    service,collector,clock = system
    publish(collector,'telemetry',SAMPLE)
    service.tick()
    return service,collector,clock

def test_database_and_routing(system):
    service,collector,clock = ready(system)
    assert service.status()['online'] is True
    assert service.store.telemetry()[0]['voltage_v']==12
    assert service.handle('energy/node02/telemetry',b'{}') is False
    assert service.handle(TOPIC+'telemetry',b'{bad') is False
    assert service.invalid_messages==1
    assert service.handle(TOPIC+'telemetry',json.dumps(SAMPLE).encode()) is False
    assert service.duplicate_messages==1
    publish(collector,'event',{'error':'SENSOR_ERROR'});service.tick()
    assert service.store.events()[0]['data']['error']=='SENSOR_ERROR'
    assert service.store.events()[1]['kind']=='invalid_payload'

def test_offline_and_retained_state(system):
    service,collector,clock = ready(system)
    clock.now += 21
    assert service.status()['online'] is False
    service.handle(TOPIC+'state',b'{"sensor_online":true,"mqtt_connected":true}',True)
    assert service.status()['online'] is False
    publish(collector,'state',{'sensor_online':True,'mqtt_connected':True});service.tick()
    assert service.status()['online'] is True
    publish(collector,'state',{'collector_online':False});service.tick()
    assert service.status()['online'] is False
    assert not service.handle(TOPIC+'telemetry',json.dumps(SAMPLE).encode(),True)

def test_commands_ack_and_idempotency(system):
    service,collector,clock = ready(system)
    request = CommandRequest(command_id='cmd-001',method='set_sampling_interval',params={'interval_ms':2000})
    command = service.create_command(request)
    messages = collector.drain();assert len(messages)==1 and messages[0].retained is False
    wire = json.loads(messages[0].payload)
    assert wire=={'command_id':command['wire_id'],'command_type':1,'command_parameter':2000}
    assert command['status']=='pending'
    assert service.create_command(request)['wire_id']==command['wire_id'] and not collector.drain()
    with pytest.raises(Conflict):
        service.create_command(CommandRequest(command_id='cmd-001',method='get_status'))
    with pytest.raises(Conflict):
        service.create_command(CommandRequest(command_id='another',method='get_status'))
    publish(collector,'ack',{'command_id':999,'result':'acknowledged','code':0});service.tick()
    assert service.store.command('cmd-001')['status']=='pending'
    publish(collector,'ack',{'command_id':command['wire_id'],'result':'acknowledged','code':0});service.tick()
    assert service.store.command('cmd-001')['status']=='success'
    publish(collector,'ack',{'command_id':command['wire_id'],'result':'timeout','code':-1});service.tick()
    assert service.store.command('cmd-001')['status']=='success'

@pytest.mark.parametrize('code,expected',[(0,'success'),(1,'failed'),(2,'failed'),(3,'failed'),(-1,'timeout')])
def test_ack_codes(system,code,expected):
    service,collector,_ = ready(system)
    command = service.create_command(CommandRequest(method='get_status'))
    publish(collector,'ack',{'command_id':command['wire_id'],'result':'timeout' if code==-1 else 'acknowledged','code':code})
    service.tick()
    assert service.store.command(command['command_id'])['status']==expected

def test_timeout_retained_and_late_ack(system):
    service,collector,clock = ready(system)
    command = service.create_command(CommandRequest(command_id='timeout',method='get_status'))
    ack = json.dumps(dict(command_id=command['wire_id'],result='acknowledged',code=0)).encode()
    assert not service.handle(TOPIC+'ack',ack,True)
    assert service.store.command('timeout')['status']=='pending'
    clock.now += 6;service.tick()
    assert service.store.command('timeout')['status']=='timeout'
    service.handle(TOPIC+'ack',ack)
    assert service.store.command('timeout')['status']=='timeout'

def test_offline_publish_failure(system):
    service,collector,clock = system
    with pytest.raises(Unavailable):
        service.create_command(CommandRequest(method='get_status'))
    ready(system)
    service.transport.publish = lambda *a,**kw: False
    command = service.create_command(CommandRequest(method='get_status'))
    assert command['status']=='publish_failed'

def test_restart_pending_no_replay(system):
    service,collector,clock = ready(system)
    command = service.create_command(CommandRequest(command_id='restart',method='get_status'))
    collector.drain()
    second = Gateway(service.settings,service.transport,clock=clock)
    try:
        assert second.store.command('restart')['status']=='interrupted'
        assert not second.status()['online']
        assert second.create_command(CommandRequest(command_id='restart',method='get_status'))['status']=='interrupted'
        assert not collector.drain()
    finally:
        second.close()

def test_retention_and_pagination(system):
    from dataclasses import replace
    service,collector,clock = ready(system)
    service.settings = replace(service.settings,max_telemetry=2,max_events=2,max_commands=2)
    for seq in range(43,48):
        clock.now += 1
        publish(collector,'telemetry',{**SAMPLE,'sequence_number':seq})
        publish(collector,'event',{'event':'test'})
        service.tick()
    rows = service.store.telemetry()
    assert len(rows)==2 and rows[0]['sequence_number']==47
    assert len(service.store.events())==2
    assert service.store.telemetry(before_id=rows[0]['id'])[0]['sequence_number']==46
    clock.now += 8*86400;service.tick()
    assert not service.store.telemetry() and not service.store.events()
