# Gateway setup — MongoDB only

Requires Python 3.11+, MongoDB Atlas Free (preferred on this Windows 10 host)
or a supported existing MongoDB server, and local Mosquitto. Atlas is now an
explicit Phase 2.1 option, not a fallback. No unsupported Windows 10 MongoDB,
WSL/Docker replacement, service/security/firewall changes are made automatically.

## Phase 2.1 Atlas setup (operator actions)

1. In Atlas, create/select a dedicated disposable testing project and Free cluster;
   wait until it is available. Do not reuse a production cluster for these tests.
2. Security → Database Access: create/manage a SCRAM database user yourself,
   separate from the Atlas account login. Keep its password private. For the
   application, readWrite on energy_gateway is sufficient. Existing tests generate
   energy_test_<UUID> databases, create indexes and drop those databases afterward:
   a single-database application user cannot run them. On the disposable test
   cluster only, a temporary test user needs readWriteAnyDatabase and
   dbAdminAnyDatabase (including dropDatabase), restricted to that cluster.
   Revoke the temporary test access after testing; do not grant production access.
3. Security → Network Access: authorize this PC's CURRENT public egress IP as a
   single /32 entry (temporary if available). Do not use 0.0.0.0/0. This is Atlas
   project access, not a Windows firewall change; operator authorization is required.
4. Cluster → Connect → Drivers → Python/PyMongo: copy the mongodb+srv URI privately.
   Replace its username/password locally; percent-encode reserved credential
   characters. Retain Atlas TLS/authSource options. Never paste credentials into
   chat, shell history, reports, Git, or CLI arguments. Do not disable TLS validation.
5. If gateway/.env does not exist, copy .env.example without overwriting an existing
   file. In a local editor set MONGODB_URI to the Atlas driver URI and
   MONGODB_DATABASE=energy_gateway. No real URI/password is included here.
   Ensure no stale process-level MONGODB_URI overrides .env; environment wins.
   PyMongo 4.19 + dnspython are installed; SRV DNS resolution, TLS/SNI and outbound
   reachability to the Atlas nodes are required. No local mongod service is needed.

```powershell
if (!(Test-Path gateway/.env)) { Copy-Item gateway/.env.example gateway/.env }
# Edit gateway/.env privately, then:
./.venv/Scripts/python.exe -m scripts.check_integration_services
```

The default probe reports redacted connectivity results and exits 1 for missing
services. Use `--mongo-crud` to verify write access separately. The test user
needs access to the dedicated `energy_integration_probe` database. The probe
inserts, reads and updates one UUID-tagged document and deletes only that document.
If a connection fails during cleanup, inspect the `phase21_probes` collection in
that database before removing a leftover probe. For server selection timeouts,
check Atlas cluster availability, the current IP allowlist, SRV DNS and TLS.
For authentication errors, check the database user and its permissions.

```powershell
./.venv/Scripts/python.exe -m scripts.check_integration_services --mongo-crud
```

Run the real tests after the MongoDB checks and broker setup succeed.

```powershell
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
try { ./.venv/Scripts/python.exe -m pytest -q tests/python/test_mosquitto_integration.py } finally {
    Remove-Item Env:RUN_MONGODB_TESTS
    Remove-Item Env:RUN_MQTT_INTEGRATION
}
```

The fixture now reads the same .env as the gateway, while overriding ONLY the
MongoDB database with a generated isolated test name. Real mode never uses mocks.
This integration test runs FastAPI through TestClient lifespan and a deterministic
in-process Sensor/Collector simulator with REAL Paho/Mosquitto and MongoDB. It
checks telemetry values and ordering, stored device state, both REST command
methods, duplicate and unknown ACKs, negative ACKs, timeout, MQTT reconnect and
persistence after Gateway recreation. For the full regression
suite against MongoDB, use the same flags with `python -m pytest -q`.

After the test, run the actual gateway and simulator CLI in separate terminals,
using existing startup commands below. Do not run either concurrently with the
isolated integration test (fixed MQTT topics). Pending commands and app DB records
are not created merely by the read-only connectivity probe.

Official references: [Atlas connection requirements](https://www.mongodb.com/docs/atlas/driver-connection/),
[IP access list](https://www.mongodb.com/docs/atlas/security/ip-access-list/),
[database users](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/).

## Native Windows MongoDB

Use the official [Community installer](https://www.mongodb.com/try/download/community)
and [Windows instructions](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-windows/).
Install the chosen supported release with the interactive MSI wizard. If it asks
for elevation, the operator must approve manually; do not bypass it. Optional
Windows service installation is an explicit operator choice. Preserve any existing
service/data and do not modify unrelated services. Verify:

```powershell
Get-Service MongoDB
Test-NetConnection 127.0.0.1 -Port 27017
```

For a manually launched server (after installing binaries), create a NEW data
directory and run in an operator-controlled terminal; replace the binary path:

```powershell
New-Item -ItemType Directory -Force data/mongodb
& '<installed MongoDB path>/bin/mongod.exe' --dbpath "$PWD/data/mongodb" --bind_ip 127.0.0.1 --port 27017
```

Do not share a data directory between server processes. Loopback binding is
mandatory for the unauthenticated local development example. For an authenticated
server, provision a dedicated energy_gateway user with readWrite only on that
database using MongoDB's access-control instructions; keep its URI in ignored .env,
never source or logs. Do not use admin credentials for the running gateway.
Test UUID databases require separate test-only privileges on a disposable server.
No credentials were generated and no local server was installed on this unsupported OS.
Prefer the explicitly configured Atlas option above on Windows 10.

## Python and broker

```powershell
Set-Location G:\slides\261\IOT\Project
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r gateway/requirements-dev.txt
Copy-Item gateway/.env.example gateway/.env
```

Set MONGODB_URI=mongodb://127.0.0.1:27017/ and MONGODB_DATABASE=energy_gateway.
LOCAL_MQTT_HOST/PORT/USERNAME/PASSWORD remain unchanged. GATEWAY_DB_PATH is removed.
Paths for the MongoDB server data directory are managed by mongod, not the gateway.

Install Mosquitto using the Windows x64 package. Leave service installation
unchecked for a foreground test broker. [Official downloads](https://mosquitto.org/download/).
In separate PowerShell terminals, start the broker and verify delivery on a test topic.

```powershell
& 'C:/Program Files/mosquitto/mosquitto.exe' -c scripts/mosquitto-local.conf -v
./scripts/check-broker.ps1
& 'C:/Program Files/mosquitto/mosquitto_sub.exe' -h 127.0.0.1 -p 1883 -t 'phase21/connectivity' -C 1 -W 10
& 'C:/Program Files/mosquitto/mosquitto_pub.exe' -h 127.0.0.1 -p 1883 -t 'phase21/connectivity' -m 'ready'
```

After the real integration test, run the Gateway and Simulator in separate terminals.

```powershell
./.venv/Scripts/python.exe -m gateway
./.venv/Scripts/python.exe -m simulator --scenario normal
```

Run only one simulator or physical Collector on node01 topics. No Docker needed.
API binds 127.0.0.1:8000; /docs documents unchanged REST request/response schemas.
MongoDB startup/connectivity failure aborts startup. Runtime database failure
returns HTTP 503 and maintenance failures are logged, not silently redirected.
Run a single Gateway process: startup interrupts old pending commands as before.
Do not expose the unauthenticated HTTP API publicly.

## Inspect data

```powershell
./.venv/Scripts/python.exe -c "from gateway.app.config import Settings; from pymongo import MongoClient; s=Settings.from_env(); c=MongoClient(s.mongodb_uri,serverSelectionTimeoutMS=2000); d=c[s.mongodb_database]; print(d.command('ping')); print(d.telemetry.count_documents({})); print(d.commands.find_one({}, {'_id':0})); c.close()"
```

Collections: devices, telemetry, commands (including atomic matched ACK record),
events and counters. Counters preserve integer API pagination and numeric wire IDs.
No ObjectId is exposed through existing APIs. Unique telemetry epoch/sequence and
command/pending-slot indexes enforce deduplication. Received timestamps, identity,
unit conversions and MQTT contract remain unchanged. Retention uses explicit
bounded deletion batches (7 days and row caps); counters are never pruned.
Standalone MongoDB is supported; no multi-document transactions are assumed.
Telemetry/state span documents, so catastrophic partial writes are not a
cross-collection transaction guarantee. Unknown/duplicate ACKs only log events;
terminal command updates require status=pending and an unexpired deadline.

## Tests and reset safety

```powershell
./.venv/Scripts/python.exe -m pytest -q
# Only with actual dedicated test MongoDB and Mosquitto available:
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
./.venv/Scripts/python.exe -m pytest -q
Remove-Item Env:RUN_MQTT_INTEGRATION
Remove-Item Env:RUN_MONGODB_TESTS
./scripts/test.ps1
./scripts/check-wire-vectors.ps1
```

Default tests use explicit mongomock injection; production never imports mongomock.
Real-mode fixtures create a unique energy_test_<UUID> DB, assert the exact name,
and drop only that generated database after the test. Do not reset energy_gateway
to rerun tests; no application reset command is provided. Never delete counters
or replace a live DB while nodes may return old ACKs. Application data deletion
requires separate user approval/backups, not an automatic test cleanup.

If MongoDB is unreachable, check service/logs, bind address, port and credentials.
Do not disable authentication/firewall or substitute an embedded database. If MQTT
is unavailable, use check-broker.ps1 and the broker logs. Old online snapshots
alone never prove current liveness. For physical ESP32 migration, set Collector's
broker host to the PC's actual LAN address (not ESP32 localhost), authenticate the
broker, and follow hardware-validation.md. Hardware/cloud remain unverified.
Historical persistence migration and remaining references: mongodb-migration.md.
