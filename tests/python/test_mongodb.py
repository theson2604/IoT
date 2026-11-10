"""Mocked MongoDB semantics unless RUN_MONGODB_TESTS=1 explicitly selects a real server."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from gateway.app.storage.mongodb import Store
from gateway.app.models.contracts import Ack, CommandRequest
from tests.python.test_gateway import ready
from tests.python.test_contracts import SAMPLE
from gateway.app.mqtt.transport import TOPIC
from gateway.app.config import Settings
import json


def test_atomic_ack_race(system):
    service,_,clock=ready(system)
    command=service.create_command(CommandRequest(method='get_status'))
    ack=Ack(command_id=command['wire_id'],result='acknowledged',code=0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:service.store.acknowledge(ack,'success',clock()),range(16)))
    assert sum(results)==1
    assert service.store.command(command['command_id'])['ack']['command_id']==command['wire_id']
    service.store.expire(clock()+100)
    assert service.store.command(command['command_id'])['status']=='success'


def test_ack_timeout_race(system):
    service, _, clock = ready(system)
    command = service.create_command(CommandRequest(method='get_status'))
    ack = Ack(command_id=command['wire_id'], result='acknowledged', code=0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = pool.submit(service.store.acknowledge, ack, 'success', clock())
        expired = pool.submit(service.store.expire, command['deadline'])
        won = accepted.result(timeout=10)
        expired.result(timeout=10)
    saved = service.store.command(command['command_id'])
    assert saved['status'] == ('success' if won else 'timeout')
    assert saved['code'] == (0 if won else -1)
    assert ('ack' in saved) == won


def test_unique_command_and_counter(system):
    service,_,clock=ready(system)
    store=service.store
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(lambda _:store.next_id('probe'),range(32)))
    assert len(set(ids))==32
    indexes = store.db.commands.index_information()
    assert indexes['one_pending_per_device']['unique']
    assert indexes['one_pending_per_device']['partialFilterExpression'] == {'status': 'pending'}
    assert indexes['wire_id_1']['unique'] and indexes['command_id_1']['unique']
    assert store.db.telemetry.index_information()['device_id_1__epoch_1_sequence_number_1']['unique']
    store.new_command('one','a',clock(),5)
    with pytest.raises(DuplicateKeyError): store.new_command('one','a',clock(),5)
    with pytest.raises(DuplicateKeyError): store.new_command('two','a',clock(),5)


def test_store_telemetry_dedup_and_restart(system):
    service,collector,clock=ready(system)
    row=service.store.telemetry()[0].copy();row.pop('id')
    assert not service.store.measurement(row,20)
    from gateway.app.services.gateway import Gateway
    second=Gateway(service.settings,service.transport,clock=clock)
    try:
        assert second.store.telemetry()==service.store.telemetry()
        assert second.store.device()==service.store.device()
    finally: second.close()


def test_connection_fails_closed(monkeypatch):
    from gateway.app.storage import mongodb
    fake=Mock();fake.admin.command.side_effect=ServerSelectionTimeoutError('test')
    monkeypatch.setattr(mongodb,'MongoClient',lambda *a,**kw:fake)
    with pytest.raises(ServerSelectionTimeoutError): Store(Settings())
    fake.close.assert_called_once()


def test_api_database_failure(system,monkeypatch):
    from fastapi.testclient import TestClient
    from gateway.app.main import create_app
    service,_,clock=system
    with TestClient(create_app(service.settings,service.transport,clock=clock,background=False)) as api:
        monkeypatch.setattr(api.app.state.gateway.store,'ping',Mock(side_effect=ServerSelectionTimeoutError('test')))
        response=api.get('/health')
        assert response.status_code==503 and 'test' not in response.text


def test_invalid_document(system):
    from bson.errors import InvalidDocument
    with pytest.raises(InvalidDocument): system[0].store.db.events.insert_one({'bad':object()})


def test_legacy_migration_only(mongo_settings,tmp_path):
    # Synthetic migration-only source, not an active gateway backend/test fixture.
    import sqlite3
    from scripts.migrate_legacy_sqlite import migrate
    path=tmp_path/'legacy.sqlite3'; backup=tmp_path/'backup.sqlite3'
    with sqlite3.connect(path) as old:
        old.executescript("""
        CREATE TABLE devices(device_id TEXT PRIMARY KEY,data TEXT);
        CREATE TABLE telemetry(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT,received_at REAL,sequence_number INTEGER,data TEXT);
        CREATE TABLE commands(wire_id INTEGER PRIMARY KEY AUTOINCREMENT,command_id TEXT,device_id TEXT,fingerprint TEXT,created_at REAL,deadline REAL,status TEXT,code INTEGER);
        CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,received_at REAL,kind TEXT,data TEXT);
        """)
        old.execute('INSERT INTO devices VALUES(?,?)',('node01',json.dumps({'sequence':42})))
        old.execute('INSERT INTO telemetry VALUES(?,?,?,?,?)',(7,'node01',100,42,json.dumps(dict(device_id='node01',received_at=100,sequence_number=42,energy_wh=1))))
        old.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(9,'old','node01','fingerprint',99,104,'success',0))
        old.execute('INSERT INTO events VALUES(?,?,?,?)',(3,100,'device_event','{"event":"old"}'))
    counts=migrate(path,mongo_settings,backup)
    assert counts==dict(devices=1,telemetry=1,commands=1,events=1)
    assert path.exists() and backup.exists()
    with pytest.raises(ValueError): migrate(path,mongo_settings,tmp_path/'another.sqlite3')
    store=Store(mongo_settings)
    try:
        assert store.telemetry()[0]['id']==7 and store.command('old')['wire_id']==9
        assert store.next_id('commands')==10
    finally: store.close()
