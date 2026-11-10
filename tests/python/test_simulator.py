import pytest
from gateway.app.models.contracts import CommandRequest
from simulator.core import Options, Sensor, Link, Simulation
from simulator.wire import Frame

def run(system,options=None,duration=2,step=0.1):
    service,collector,clock = system
    simulation = Simulation(collector,options)
    start = clock.now
    for i in range(round(duration/step)+1):
        clock.now = start+i*step
        simulation.tick(round(i*step,6));service.tick()
    return simulation,start

def test_simulated_energy():
    sensor = Sensor(Options(fluctuation_ma=0))
    assert sensor.read(0)==(12000,125,1500,0,1)
    assert sensor.read(1.2)[3]==0
    assert sensor.read(2.4)[3]==1
    assert sensor.read(4.8)[3]==2

def test_sensor_error_gap():
    sensor = Sensor(Options(scenario='sensor_error',fault_at=1,fault_duration=2,fluctuation_ma=0))
    sensor.read(0)
    assert sensor.read(1)==(0,0,0,0,2)
    assert sensor.read(3)[3]==0
    assert sensor.read(5.4)[3]==1

def test_normal_and_commands(system):
    simulation,start = run(system)
    service,_,clock = system
    assert service.status()['online'] and service.store.telemetry()[0]['simulated']
    command = service.create_command(CommandRequest(command_id='sim',method='set_sampling_interval',params={'interval_ms':2000}))
    clock.now = start+2.1;simulation.tick(2.1);service.tick()
    assert service.store.command('sim')['status']=='success'
    assert simulation.sensor.interval==2000
    assert simulation.pending is None

@pytest.mark.parametrize('scenario',['high_power','load_change'])
def test_load_change(system,scenario):
    run(system,Options(scenario=scenario,fault_at=1,fluctuation_ma=0),duration=3)
    rows = system[0].store.telemetry()
    assert rows[0]['power_w']==12 and rows[-1]['power_w']==1.5

def test_sensor_failure_event(system):
    run(system,Options(scenario='sensor_error',fault_at=1,fault_duration=5),duration=2)
    rows = system[0].store.telemetry()
    assert rows[0]['power_w'] is None and rows[0]['sensor_status']==2
    assert any(e['data'].get('error')=='SENSOR_ERROR' for e in system[0].store.events())

def test_loss_is_deterministic_and_bounded():
    options = Options(seed=123,loss=0.5,duplicate=0.5,delay_ms=100,jitter_ms=1000)
    def exercise():
        link = Link(options)
        for seq in range(100):
            link.send('collector',Frame(5,1,seq,0,(1,)),0)
        return link.dropped,[(f.sequence,d) for d,f in link.due(2)]
    assert exercise()==exercise()
    assert exercise()[0]>0
    sequences = [seq for seq,d in exercise()[1]]
    assert len(sequences)!=len(set(sequences)) and sequences!=sorted(sequences)
    link = Link(Options())
    for seq in range(300):
        link.send('collector',Frame(5,1,seq,0,(1,)),0)
    assert len(link.queue)==256 and link.dropped==44

def test_link_failure_offline_and_recovery(system):
    simulation,start = run(system,Options(scenario='link_failure',fault_at=1,fault_duration=25),duration=23)
    assert not system[0].status()['online']
    for i in range(24,29):
        system[2].now=start+i;simulation.tick(i);system[0].tick()
    assert system[0].status()['online']

def test_command_timeout(system):
    simulation,start = run(system,Options(scenario='command_timeout'))
    service,_,clock = system
    service.create_command(CommandRequest(command_id='lost',method='get_status'))
    for i in range(21,51):
        clock.now=start+i/10;simulation.tick(i/10);service.tick()
    assert service.store.command('lost')['status']=='timeout'
    assert simulation.pending is None

def test_mqtt_disconnect_reconnect(system):
    simulation,start = run(system,Options(scenario='mqtt_disconnect',fault_at=1,fault_duration=3),duration=2)
    assert system[1].connected is False and not system[0].status()['online']
    for i in range(3,7):
        system[2].now=start+i;simulation.tick(i);system[0].tick()
    assert system[1].connected is True and system[0].status()['online']
    assert system[0].store.telemetry()[0]['received_at']>=start+4

@pytest.mark.parametrize('kind',['sensor','collector'])
def test_node_disconnection(system,kind):
    opts = Options(**{kind+'_disconnect_at':1})
    run(system,opts,duration=23)
    assert not system[0].status()['online']
