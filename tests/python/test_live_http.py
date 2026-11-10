"""Real loopback HTTP smoke, still no real MQTT broker or ESP32."""
import json
import socket
import threading
import time
import urllib.request
import uvicorn
from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.mqtt.transport import MemoryBroker

def test_live_http_and_shutdown(mongo_settings):
    transport=MemoryBroker().endpoint('gateway')
    app=create_app(mongo_settings,transport)
    listener=socket.socket()
    listener.bind(('127.0.0.1',0))
    listener.listen(16)
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='warning'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started:
            assert thread.is_alive() and time.monotonic()<deadline
            time.sleep(.01)
        for path in ['/health','/api/devices','/docs']:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=1) as response:
                assert response.status==200
                if path=='/api/devices':
                    assert json.load(response)['items'][0]['online'] is False
    finally:
        server.should_exit=True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()
