# MongoDB replacement audit and validation

Status: **PARTIAL**. MongoDB-only application implemented; mocked software tests
pass. Real MongoDB persistence/restart and MQTT+MongoDB integration remain BLOCKED.
No new commits, firmware changes, user-data deletion, services or firewall changes.

## Audit and plan executed

Audited tracked source/docs and Phase 2 Python modules/tests. Original persistence
was standard-library sqlite3 in gateway/app/storage/sqlite.py, initialized on
Gateway construction; service also directly executed command SQL. FastAPI history/
events/results used Store. Config used GATEWAY_DB_PATH/db_path. Four tables held
devices, normalized telemetry, commands/status/ACK code, and events.

1. Replaced storage and direct SQL with PyMongo collections, integer counters,
   unique indexes and conditional command updates.
2. Replaced configuration with MONGODB_URI / MONGODB_DATABASE, retained REST/MQTT
   schemas and deterministic simulator behavior.
3. Migrated tests to explicit MongoDB mocks and isolated real-server opt-in mode;
   retained firmware/C++ behavior. Added atomic race, connection/document failure,
   dedup, persistence and migration checks.
4. Updated active setup docs; archived old setup rather than erase history.

## Environment and installation blocker

Detected Windows 10 Home 10.0.19045 x64. No MongoDB/Mosquitto executable in PATH or
standard Program Files location, and no matching services. TCP 27017 and 1883
closed; real PyMongo ping raises ServerSelectionTimeoutError. No application DB
could be accessed. MongoDB 7.0 official Windows support lists Windows 11 and Server
2019/2022, not Windows 10:
https://www.mongodb.com/docs/v7.0/tutorial/install-mongodb-on-windows/

No unsupported/obsolete MongoDB release was installed, and no WSL/Docker/Atlas
substitution was used. Use a supported Windows machine/server and follow
[gateway setup](gateway-setup.md). Elevation/interactive MSI approval remains an
operator action; no permission bypass. URI defaults to loopback and a dedicated
energy_gateway database; authenticated deployments should use a readWrite user
limited to that DB. Test-only UUID databases need separate disposable test-server
privileges. Actual installation, service state and server access are NOT claimed PASS.

## Data preservation and removal

Workspace scan excluding .venv found **no pre-existing .db/.sqlite/.sqlite3 files**.
No user database was deleted or declared disposable without inspection. Existing
virtualenv contained no third-party SQLite-only packages; none needed uninstalling.
No standalone sqlite3 executable/project-owned installation was found. Python's
built-in sqlite3 remains untouched. No shared/system software was removed.

Removed only gateway/app/storage/sqlite.py. No fallback backend remains. The
migration-only utility below uses sqlite3 explicitly, outside every gateway/runtime
import path. Historical reports/setup and temporary synthetic importer-test data
are the only functional remnants. No obsolete generated user databases were found.

## Optional one-time historical import

For an old database found later, stop Gateway and snapshot/import into a NEW EMPTY
MongoDB database. The tool refuses a nonempty destination, reserves a new backup
file without overwriting, opens source read-only, uses SQLite backup for a
consistent snapshot, preserves numeric IDs/timestamps/status/relationships and
counter high-water marks, and verifies every record plus collection counts.
It never deletes source or backup. Partial failures retain imported records for
inspection; it does not delete or silently overwrite a previously used target.

```powershell
New-Item -ItemType Directory -Force backups
./.venv/Scripts/python.exe -m scripts.migrate_legacy_sqlite '<old database path>' --backup backups/legacy-before-mongo.sqlite3 --database energy_gateway_imported
```

After reviewing printed counts/records, point MONGODB_DATABASE to the imported DB.
Keep source and backup until explicitly confirmed. Original data never stored raw
ACK packets: legacy command status/code is preserved, not fabricated ACK detail.
Existing pending commands are imported unchanged, then marked interrupted on
normal Gateway startup (same no-replay policy). Only a synthetic migration test
was run here; no real-user import is claimed. Import failure is not auto-rollback:
standalone MongoDB does not provide cross-collection transactions.

## Results and commands

- Python: **63 PASS**, explicitly mocked MongoDB semantics; **1 SKIPPED** real
  MQTT+MongoDB integration. One existing Starlette/httpx deprecation warning.
- MongoDB ACK race: only one of 16 concurrent conditional updates wins; terminal
  status stays immutable. Unique pending-command/public-ID constraints and atomic
  integer counters are tested. Matched ACK data is embedded atomically in commands;
  unmatched/duplicate ACKs do not reapply state and are logged as events.
- C++: existing Modbus and energy suites PASS; five wire-vector comparisons PASS.
- Sensor / Collector / legacy PlatformIO builds PASS, unchanged by this migration.
- Database connection failure is fail-closed; runtime DB errors return HTTP 503.
- Real MongoDB restart durability: BLOCKED (not established by mongomock).
- Real Mosquitto+MongoDB telemetry/REST/ACK/timeout/restart: BLOCKED, test prepared
  but not claimed PASS. Both services must be supplied first.

```powershell
./.venv/Scripts/python.exe -m pip install -r gateway/requirements-dev.txt
./.venv/Scripts/python.exe -m pytest -q
./scripts/test.ps1
./scripts/check-wire-vectors.ps1
python -m platformio run -d firmware -e sensor_node -e collector_node -e yolo_uno
git diff --check
```

Installed in project .venv: pymongo 4.19.0 (+dnspython), mongomock 4.3.0
(+pytz/sentinels, dev tests only). requirements-tested.txt refreshed.
For real tests, on a dedicated disposable MongoDB+Mosquitto environment:

```powershell
$env:RUN_MONGODB_TESTS='1'
$env:RUN_MQTT_INTEGRATION='1'
./.venv/Scripts/python.exe -m pytest -q
Remove-Item Env:RUN_MONGODB_TESTS
Remove-Item Env:RUN_MQTT_INTEGRATION
```

Real test names are generated energy_test_<32 UUID hex>; cleanup asserts the exact
fixture-generated name and drops only that DB. No application reset/drop command
is provided. Explicit real mode fails on unavailable MongoDB instead of mocking.

## Remaining SQLite references

| Location | Classification |
|---|---|
| scripts/migrate_legacy_sqlite.py | Read-only source/backup, migration-only standard library |
| tests/python/test_mongodb.py importer test | Synthetic migration-only legacy fixture |
| docs/history/phase2-sqlite-setup.md | Historical setup, explicitly superseded |
| docs/phase2-validation.md | Historical execution evidence, preserved |
| README/setup/test-plan/this audit | Removal/no-fallback/migration explanations |
| gateway runtime modules | NONE: no sqlite imports, SQL, db_path or fallback |
| Python distribution's sqlite3 | Standard library, intentionally untouched |

## Files

Added: gateway/app/storage/mongodb.py, scripts/migrate_legacy_sqlite.py,
tests/python/test_mongodb.py, docs/mongodb-migration.md and historical setup archive.
Removed: gateway/app/storage/sqlite.py.
Modified: Gateway service/config/main, .env.example and dependency manifests;
MongoDB fixtures/live-HTTP/real-MQTT tests; README, architecture, protocol, test-plan
and setup guides. Existing firmware, MQTT payloads and C++ tests were not changed
by this task. Pre-existing working-tree changes were preserved.
