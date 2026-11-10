"""Explicit .env loading; no import-time network or filesystem writes."""
from dataclasses import dataclass, field
from pathlib import Path
import os
import math
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_username: str = ''
    mqtt_password: str = field(default='', repr=False)
    mongodb_uri: str = field(default='mongodb://127.0.0.1:27017/', repr=False)
    mongodb_database: str = 'energy_gateway'
    log_level: str = 'INFO'
    simulation_mode: bool = True
    offline_seconds: float = 20
    command_timeout: float = 5
    retention_days: int = 7
    max_telemetry: int = 100000
    max_events: int = 10000
    max_commands: int = 10000

    def __post_init__(self):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_]{1,63}', self.mongodb_database) or self.mongodb_database in ('admin','local','config'):
            raise ValueError('Use a dedicated application MongoDB database')
        if not self.mongodb_uri.startswith(('mongodb://','mongodb+srv://')):
            raise ValueError('Invalid MongoDB URI')
        if not self.mqtt_host or not 1 <= self.mqtt_port <= 65535:
            raise ValueError('Invalid MQTT host/port')
        if not all(math.isfinite(t) and t > 0 for t in (self.offline_seconds, self.command_timeout)):
            raise ValueError('Timeouts must be positive')
        if min(self.retention_days, self.max_telemetry, self.max_events, self.max_commands) < 1:
            raise ValueError('Retention limits must be positive')

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
        simulation = os.getenv('SIMULATION_MODE', 'true').lower()
        if simulation not in ('true', 'false'):
            raise ValueError('SIMULATION_MODE must be true or false')
        return cls(
            mqtt_host=os.getenv('LOCAL_MQTT_HOST', '127.0.0.1'),
            mqtt_port=int(os.getenv('LOCAL_MQTT_PORT', '1883')),
            mqtt_username=os.getenv('LOCAL_MQTT_USERNAME', ''),
            mqtt_password=os.getenv('LOCAL_MQTT_PASSWORD', ''),
            mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017/'),
            mongodb_database=os.getenv('MONGODB_DATABASE', 'energy_gateway'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'), simulation_mode=simulation == 'true',
            offline_seconds=float(os.getenv('DEVICE_OFFLINE_SECONDS', '20')),
            command_timeout=float(os.getenv('COMMAND_TIMEOUT_SECONDS', '5')),
            retention_days=int(os.getenv('RETENTION_DAYS', '7')),
            max_telemetry=int(os.getenv('MAX_TELEMETRY_ROWS', '100000')),
            max_events=int(os.getenv('MAX_EVENT_ROWS', '10000')),
            max_commands=int(os.getenv('MAX_COMMAND_ROWS', '10000')),
        )
