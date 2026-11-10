from fastapi.testclient import TestClient
from gateway.app.main import create_app
from gateway.app.mqtt.transport import TOPIC
from tests.python.test_contracts import SAMPLE
import json

def test_rest_end_to_end(system):
    service,collector,clock = system
    app = create_app(service.settings,service.transport,clock=clock,background=False)
    with TestClient(app) as api:
        assert api.get('/health').json()['status']=='ok'
        assert api.get('/api/devices').json()['items'][0]['device_id']=='node01'
        assert api.get('/api/devices/node02/status').status_code==404
        assert api.get('/api/devices/node01/telemetry/latest').status_code==404
        collector.publish(TOPIC+'telemetry',json.dumps(SAMPLE).encode())
        app.state.gateway.tick()
        assert api.get('/api/devices/node01/status').json()['online'] is True
        assert api.get('/api/devices/node01/telemetry/latest').json()['power_w']==1.5
        assert len(api.get('/api/devices/node01/telemetry/history').json()['items'])==1
        assert api.get('/api/devices/node01/telemetry/history?limit=1001').status_code==422
        assert api.get('/api/events').json()=={'items':[]}
        assert api.post('/api/devices/node01/commands',json={'method':'set_sampling_interval','params':{'interval_ms':1}}).status_code==422
        response = api.post('/api/devices/node01/commands',json={'command_id':'rest','method':'get_status'})
        assert response.status_code==202 and response.json()['status']=='pending'
        wire_id = response.json()['wire_id']
        collector.publish(TOPIC+'ack',json.dumps(dict(command_id=wire_id,result='acknowledged',code=0)).encode())
        app.state.gateway.tick()
        assert api.get('/api/commands/rest').json()['status']=='success'
        assert api.get('/api/commands/absent').status_code==404
        assert api.post('/api/devices/node01/commands',json={'command_id':'rest','method':'set_sampling_interval','params':{'interval_ms':100}}).status_code==409
        assert api.get('/docs').status_code==200
