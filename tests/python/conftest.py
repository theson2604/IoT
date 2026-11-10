import pytest
import uuid
import mongomock
from dataclasses import replace
import os
from pymongo import MongoClient
from gateway.app.config import Settings
from gateway.app.mqtt.transport import MemoryBroker
from gateway.app.services.gateway import Gateway

class Clock:
    def __init__(self):
        self.now = 100000.0
    def __call__(self):
        return self.now

@pytest.fixture
def mongo_settings(monkeypatch):
    from gateway.app.storage import mongodb
    settings = Settings(mongodb_database='energy_test_'+uuid.uuid4().hex)
    if os.getenv('RUN_MONGODB_TESTS') == '1':
        settings = replace(Settings.from_env(), mongodb_database=settings.mongodb_database)
        client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=2000)
        try:
            client.admin.command('ping')
            if client[settings.mongodb_database].list_collection_names():
                raise RuntimeError('Generated test database already contains collections')
        except Exception:
            client.close()
            raise
    else:
        client = mongomock.MongoClient()
        monkeypatch.setattr(mongodb, 'MongoClient', lambda *a, **kw: client)
    test_database = settings.mongodb_database
    try:
        yield settings
    finally:
        try:
            assert test_database.startswith('energy_test_') and len(test_database) == 44
            client.drop_database(test_database)
        finally:
            client.close()

@pytest.fixture
def system(mongo_settings):
    broker = MemoryBroker()
    gateway_transport = broker.endpoint('gateway')
    collector_transport = broker.endpoint('collector')
    clock = Clock()
    settings = mongo_settings
    service = Gateway(settings,gateway_transport,clock=clock)
    yield service,collector_transport,clock
    service.close()
