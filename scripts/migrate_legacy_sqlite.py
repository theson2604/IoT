"""Offline, one-time legacy import ONLY. Not imported by the running gateway.
Source read-only; consistent backup retained; target must be empty. Never deletes data.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from gateway.app.config import Settings
from gateway.app.storage import mongodb


def migrate(source, settings, backup):
    source, backup = Path(source).resolve(), Path(backup).resolve()
    if not source.is_file() or backup.exists() or source == backup:
        raise ValueError('Existing source and new, distinct backup path required')
    client=mongodb.MongoClient(settings.mongodb_uri,serverSelectionTimeoutMS=2000)
    try:
        client.admin.command('ping')
        db=client[settings.mongodb_database]
        if any(db[name].find_one() is not None for name in db.list_collection_names()):
            raise ValueError('Destination is not empty; no data was overwritten')
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as original:
            # Reserve without overwriting any existing backup.
            with backup.open('xb'): pass
            with sqlite3.connect(backup) as snapshot: original.backup(snapshot)
        with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as old:
            old.row_factory=sqlite3.Row
            expected={'devices','telemetry','commands','events'}
            tables={x[0] for x in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not expected <= tables: raise ValueError('Unknown legacy schema; backup retained')
            store=mongodb.Store(settings,initialize_device=False)
            try:
                counts={}
                epochs={}
                for table in ('devices','telemetry','commands','events'):
                    key='device_id' if table=='devices' else ('wire_id' if table=='commands' else 'id')
                    count=0
                    for row in old.execute(f'SELECT * FROM {table} ORDER BY {key}'):
                        row=dict(row)
                        if table=='devices': doc=dict(json.loads(row['data']),_id=row['device_id'])
                        elif table=='telemetry':
                            doc=dict(json.loads(row['data']),id=row['id'],_id=row['id'])
                            device=doc['device_id']; seq=doc['sequence_number']
                            epoch,previous=epochs.get(device,(0,None))
                            if previous is not None and not 0 < (seq-previous)&0xffffffff < 0x80000000: epoch+=1
                            epochs[device]=(epoch,seq);doc['_epoch']=epoch
                        elif table=='commands': doc=dict(row,_id=row['wire_id'])
                        else:
                            doc=dict(row,_id=row['id']);doc['data']=json.loads(row['data'])
                        store.db[table].replace_one({'_id':doc['_id']},doc,upsert=True)
                        if store.db[table].find_one({'_id':doc['_id']}) != doc:
                            raise RuntimeError('Record verification failed; source/backup retained')
                        count+=1
                    counts[table]=count
                    if store.db[table].count_documents({}) != count:
                        raise RuntimeError('Count verification failed')
                for table in ('telemetry','events','commands'):
                    key='wire_id' if table=='commands' else 'id'
                    maximum=old.execute(f'SELECT MAX({key}) FROM {table}').fetchone()[0] or 0
                    sequence=old.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(table,)).fetchone()
                    maximum=max(maximum,sequence[0] if sequence else 0)
                    store.db.counters.update_one({'_id':table},{'$max':{'value':maximum}},upsert=True)
                store.db.counters.insert_one(dict(_id='legacy_import',completed_at=datetime.now(timezone.utc),
                    backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),counts=counts))
                return counts
            finally: store.close()
    finally: client.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--backup',required=True)
    parser.add_argument('--database',required=True,help='New empty destination database')
    args=parser.parse_args()
    settings=replace(Settings.from_env(),mongodb_database=args.database)
    print(json.dumps(migrate(args.source,settings,args.backup),indent=2))

if __name__=='__main__': main()
