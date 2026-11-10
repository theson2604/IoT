from types import SimpleNamespace
from unittest.mock import Mock
from dataclasses import replace
from gateway.app.config import Settings
from gateway.app.mqtt.transport import PahoTransport, TOPIC
from tests.python.test_gateway import ready
from tests.python.test_contracts import SAMPLE
import json
import pytest

def test_paho_subscribes_on_each_reconnect():
    adapter = PahoTransport(Settings())
    fake = Mock();fake.subscribe.return_value=(0,1)
    reason = SimpleNamespace(is_failure=False)
    adapter._connect(fake,None,None,reason,None)
    assert adapter.connected and fake.subscribe.call_count==1
    adapter._disconnect(fake,None,None,'lost',None)
    assert not adapter.connected
    assert not adapter.publish(TOPIC+'command',b'{}')
    adapter._connect(fake,None,None,reason,None)
    assert adapter.connected and fake.subscribe.call_count==2
    adapter._connect(fake,None,None,SimpleNamespace(is_failure=True),None)
    assert not adapter.connected
    with pytest.raises(ValueError):
        adapter.publish(TOPIC+'command',b'{}',retain=True)

def test_callback_queue_bounded():
    adapter=PahoTransport(Settings())
    message=SimpleNamespace(topic=TOPIC+'telemetry',payload=b'{}',retain=False)
    for _ in range(300):
        adapter._message(None,None,message)
    assert len(adapter.drain())==256 and adapter.dropped==44
    adapter._message(None,None,SimpleNamespace(topic=TOPIC+'telemetry',payload=b'x'*4097,retain=False))
    assert not adapter.drain() and adapter.dropped==45

def test_physical_mode_rejects_simulated(system):
    service,_,_=system
    service.settings=replace(service.settings,simulation_mode=False)
    assert not service.handle(TOPIC+'telemetry',json.dumps(SAMPLE).encode())
    assert not service.store.telemetry()
