import argparse
import logging
import math
import time
from gateway.app.config import Settings
from gateway.app.mqtt.transport import PahoTransport
from simulator.core import Options, Simulation, SCENARIOS

log = logging.getLogger(__name__)

def load_change(value):
    try:
        at,current = value.split(':')
        return float(at),int(current)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use SECONDS:CURRENT_MA') from exc

def main():
    parser = argparse.ArgumentParser(description='Application-level two-node simulator; not ESP-NOW RF emulation')
    parser.add_argument('--scenario', choices=SCENARIOS, default='normal')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--loss', type=float, default=0)
    parser.add_argument('--duplicate', type=float, default=0)
    parser.add_argument('--delay-ms', type=int, default=0)
    parser.add_argument('--jitter-ms', type=int, default=0)
    parser.add_argument('--fault-at', type=float, default=5)
    parser.add_argument('--fault-duration', type=float, default=5)
    parser.add_argument('--current-ma', type=int, default=125)
    parser.add_argument('--changed-current-ma', type=int, default=1000)
    parser.add_argument('--fluctuation-ma', type=int, default=5)
    parser.add_argument('--load-change', type=load_change, action='append', default=[])
    parser.add_argument('--sensor-disconnect-at', type=float)
    parser.add_argument('--collector-disconnect-at', type=float)
    parser.add_argument('--duration', type=float, default=0, help='Seconds, 0 runs until Ctrl+C')
    args = parser.parse_args()
    duration = args.duration
    if not math.isfinite(duration) or duration < 0:
        parser.error('duration must be nonnegative')
    values = vars(args).copy();values.pop('duration');values['load_changes'] = tuple(values.pop('load_change'))
    try:
        options = Options(**values)
    except ValueError as exc:
        parser.error(str(exc))
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    log.info('SIMULATED scenario=%s seed=%d; no real ESP-NOW RF', options.scenario,options.seed)
    transport = PahoTransport(settings,role='collector')
    simulation = Simulation(transport,options)
    transport.start()
    start = time.monotonic()
    try:
        while not duration or time.monotonic()-start < duration:
            elapsed = round(time.monotonic()-start,3)
            simulation.tick(elapsed)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        simulation.publish('state',{'collector_online':False},retain=True)
        transport.stop()

if __name__ == '__main__':
    main()
