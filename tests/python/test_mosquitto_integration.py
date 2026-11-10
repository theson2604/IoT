"""Opt-in integration against an isolated loopback broker and real MongoDB."""
from dataclasses import replace
import json
import os
import time

import pytest
from fastapi.testclient import TestClient
from gateway.app.main import create_app
from gateway.app.mqtt.transport import PahoTransport, TOPIC
from simulator.core import Simulation, Options


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv('RUN_MQTT_INTEGRATION') != '1' or os.getenv('RUN_MONGODB_TESTS') != '1',
    reason='Requires real MongoDB and local Mosquitto (enable both integration flags)',
)
def test_real_mosquitto(mongo_settings):
    settings = replace(mongo_settings, mqtt_host='127.0.0.1', mqtt_port=1883)
    collector = PahoTransport(settings, role='collector')
    gateway_transport = PahoTransport(settings)
    simulation = Simulation(collector, Options(seed=13, fluctuation_ma=0))
    app = create_app(settings, gateway_transport)
    start = time.monotonic()
    run_id = settings.mongodb_database.removeprefix('energy_test_')
    set_interval_id = f'{run_id}-interval'
    get_status_id = f'{run_id}-status'
    failed_id = f'{run_id}-failed'
    timeout_id = f'{run_id}-timeout'

    def wait_for(predicate, description, *, tick=True):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if tick:
                simulation.tick(time.monotonic() - start)
            if predicate():
                return
            time.sleep(0.02)
        pytest.fail(description)

    def send_command(api, command_id, method='get_status', **params):
        response = api.post('/api/devices/node01/commands', json={
            'command_id': command_id, 'method': method, 'params': params,
        })
        assert response.status_code == 202
        assert response.json()['status'] == 'pending'
        return response.json()['wire_id']

    def result(api, command_id):
        return api.get(f'/api/commands/{command_id}').json()['status']

    def send_ack(wire_id, code=0):
        assert collector.publish(TOPIC + 'ack', json.dumps({
            'command_id': wire_id, 'result': 'acknowledged', 'code': code,
        }).encode(), retain=False)

    collector.start()
    try:
        with TestClient(app) as api:
            service = app.state.gateway
            store = service.store
            latest_url = '/api/devices/node01/telemetry/latest'
            status_url = '/api/devices/node01/status'
            wait_for(lambda: api.get(latest_url).status_code == 200 and
                     api.get(status_url).json()['online'], 'Telemetry or device state missing')
            sample = api.get(latest_url).json()
            persisted = store.db.telemetry.find_one({'id': sample['id']}, {'_id': 0, '_epoch': 0})
            assert persisted == sample
            assert (sample['voltage_v'], sample['current_a'], sample['power_w']) == (12, 0.125, 1.5)
            assert sample['simulated'] is True
            wait_for(lambda: store.device().get('state', {}).get('sensor_online') is True,
                     'Collector state was not persisted')

            # Freeze simulator publishing while injecting known old and malformed packets.
            previous = store.telemetry(limit=1)[0]
            old_sequences = [previous['sequence_number'], (previous['sequence_number'] - 1) & 0xffffffff]
            old_filter = {'sequence_number': {'$in': old_sequences}}
            previous_count = store.db.telemetry.count_documents(old_filter)
            previous_duplicates = service.duplicate_messages
            for sequence in old_sequences:
                assert simulation.publish('telemetry', {
                    'schema_version': 1, 'device_id': 'node01', 'available': True,
                    'sequence_number': sequence, 'sender_uptime_ms': 0,
                    'voltage_mv': 12000, 'current_ma': 125, 'power_mw': 1500,
                    'energy_mwh': 0, 'sensor_status': 1,
                })
            assert collector.publish(TOPIC + 'telemetry', b'{invalid')
            wait_for(lambda: service.duplicate_messages >= previous_duplicates + 2 and
                     store.db.events.count_documents({'kind': 'invalid_payload'}) > 0,
                     'Invalid/old telemetry was not rejected', tick=False)
            assert store.db.telemetry.count_documents(old_filter) == previous_count

            wire_id = send_command(api, set_interval_id, 'set_sampling_interval', interval_ms=2000)
            wait_for(lambda: result(api, set_interval_id) == 'success', 'Sampling interval ACK missing')
            assert simulation.sensor.interval == 2000
            original_ack = store.command(set_interval_id)['ack']
            assert original_ack['command_id'] == wire_id and original_ack['code'] == 0
            send_ack(wire_id)
            send_ack(0xffffffff)
            wait_for(lambda: store.db.events.count_documents({'kind': 'unmatched_ack',
                        'data.command_id': {'$in': [wire_id, 0xffffffff]}}) >= 2,
                     'Duplicate/unknown ACKs were not accounted for')
            assert store.command(set_interval_id)['ack'] == original_ack

            gateway_transport.stop()
            assert api.get(status_url).json()['online'] is False
            gateway_transport.start()
            old_id = api.get(latest_url).json()['id']
            wait_for(lambda: api.get(latest_url).json()['id'] > old_id,
                     'MQTT subscriptions did not recover after reconnect')
            status_wire = send_command(api, get_status_id)
            wait_for(lambda: result(api, get_status_id) == 'success', 'GET_STATUS ACK missing')
            assert store.command(get_status_id)['ack']['command_id'] == status_wire

            # Inject a negative ACK via MQTT while the simulator is paused.
            failed_wire = send_command(api, failed_id)
            send_ack(failed_wire, code=1)
            wait_for(lambda: result(api, failed_id) == 'failed', 'Negative ACK was not persisted', tick=False)
            assert store.command(failed_id)['ack']['code'] == 1
            # Discard only this test client's queued command before resuming simulation.
            collector.drain()
            simulation.options.scenario = 'command_timeout'
            send_command(api, timeout_id)
            wait_for(lambda: result(api, timeout_id) == 'timeout', 'Missing ACK did not time out')
            assert store.command(timeout_id)['code'] == -1

        with TestClient(create_app(settings, PahoTransport(settings))) as restarted:
            assert restarted.get(latest_url).json()['id'] >= sample['id']
            assert result(restarted, set_interval_id) == 'success'
            assert result(restarted, failed_id) == 'failed'
            assert result(restarted, timeout_id) == 'timeout'
    finally:
        collector.stop()
