"""Check connectivity and optionally verify CRUD on an isolated MongoDB database."""
import argparse
import json
import socket
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import (ConfigurationError, ConnectionFailure, DuplicateKeyError,
                            OperationFailure, ServerSelectionTimeoutError)

from gateway.app.config import Settings

PROBE_DATABASE = 'energy_integration_probe'


def mongo_crud(client):
    collection = client[PROBE_DATABASE].phase21_probes
    identity = {'_id': uuid4().hex, 'owner': uuid4().hex}
    try:
        collection.insert_one({**identity, 'value': 1})
        if collection.find_one(identity) != {**identity, 'value': 1}:
            raise RuntimeError('Inserted document did not match')
        updated = collection.update_one(identity, {'$set': {'value': 2}})
        if updated.modified_count != 1 or collection.find_one(identity) != {**identity, 'value': 2}:
            raise RuntimeError('Updated document did not match')
    except DuplicateKeyError:
        # An existing document won the insert. It belongs to another writer.
        raise
    except Exception:
        # The server may have accepted the insert before the network failed.
        collection.delete_one(identity)
        raise
    else:
        if collection.delete_one(identity).deleted_count != 1:
            raise RuntimeError('Probe document cleanup could not be verified')


def mongo_error(error):
    if isinstance(error, DuplicateKeyError):
        return 'FAIL: duplicate key'
    if isinstance(error, OperationFailure) and error.code in (13, 18, 8000):
        return 'BLOCKED: check database authentication and test database permissions'
    if isinstance(error, ServerSelectionTimeoutError):
        return 'BLOCKED: server selection timed out. Check server availability, DNS, TLS and Atlas IP access'
    if isinstance(error, ConfigurationError):
        return 'BLOCKED: check URI configuration and SRV DNS resolution'
    if isinstance(error, ConnectionFailure):
        return 'BLOCKED: database connection failed or disconnected'
    return 'FAIL: ' + type(error).__name__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mongo-crud', action='store_true',
                        help=f'Insert, read, update and remove a unique probe in {PROBE_DATABASE}')
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
    except ValueError:
        print('BLOCKED: invalid integration configuration')
        return 1
    results = {'mongodb_crud': 'NOT TESTED'}
    stage = 'mongodb_ping'
    try:
        with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000,
                         connectTimeoutMS=2000, timeoutMS=8000) as client:
            client.admin.command('ping')
            results[stage] = 'PASS'
            if args.mongo_crud:
                stage = 'mongodb_crud'
                mongo_crud(client)
                results[stage] = 'PASS'
    except Exception as error:
        results[stage] = mongo_error(error)
        if args.mongo_crud and stage == 'mongodb_ping':
            results['mongodb_crud'] = 'BLOCKED: ping prerequisite failed'
    try:
        with socket.create_connection(('127.0.0.1', 1883), timeout=2):
            results['mqtt_tcp'] = 'PASS'
    except OSError as error:
        results['mqtt_tcp'] = 'BLOCKED: ' + type(error).__name__
    print(json.dumps(results, indent=2))
    required = ['mongodb_ping', 'mqtt_tcp']
    if args.mongo_crud:
        required.append('mongodb_crud')
    return 0 if all(results[check] == 'PASS' for check in required) else 1


if __name__ == '__main__':
    raise SystemExit(main())
