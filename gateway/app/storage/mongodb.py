"""MongoDB-only persistence. Standalone server supported; no cross-document transaction assumption."""
import threading
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

class Store:
    def __init__(self, settings, *, initialize_device=True):
        self.lock = threading.RLock()
        self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=2000,
                                  connectTimeoutMS=2000, socketTimeoutMS=3000,
                                  maxPoolSize=10, retryWrites=False)
        try:
            self.client.admin.command('ping')  # Fail closed; no fallback.
            self.db = self.client[settings.mongodb_database]
            self.db.telemetry.create_index([('device_id',ASCENDING),('_epoch',ASCENDING),('sequence_number',ASCENDING)],unique=True)
            self.db.telemetry.create_index([('device_id',ASCENDING),('id',DESCENDING)])
            self.db.telemetry.create_index('received_at')
            self.db.commands.create_index('command_id',unique=True)
            self.db.commands.create_index('wire_id',unique=True)
            self.db.commands.create_index('device_id',unique=True,partialFilterExpression={'status':'pending'},name='one_pending_per_device')
            self.db.commands.create_index([('status',ASCENDING),('deadline',ASCENDING)])
            self.db.commands.create_index('created_at')
            self.db.events.create_index('received_at')
            if initialize_device:
                self.db.devices.update_one({'_id':'node01'},{'$setOnInsert':{}},upsert=True)
            self.db.commands.update_many({'status':'pending'},{'$set':{'status':'interrupted'}})
        except Exception:
            self.client.close()
            raise

    def next_id(self, name):
        doc=self.db.counters.find_one_and_update({'_id':name},{'$inc':{'value':1}},upsert=True,return_document=ReturnDocument.AFTER)
        return doc['value']

    def device(self):
        doc=self.db.devices.find_one({'_id':'node01'}) or {}
        doc.pop('_id',None)
        return doc

    def save_device(self, data):
        # Patch fields atomically, so telemetry/state writers do not replace each other's keys.
        if data:
            self.db.devices.update_one({'_id':'node01'},{'$set':data},upsert=True)

    def measurement(self, data, offline_seconds):
        last=self.db.telemetry.find_one({'device_id':data['device_id']},sort=[('id',DESCENDING)])
        epoch=last.get('_epoch',0) if last else 0
        if last and data['received_at']-last['received_at'] >= offline_seconds:
            epoch+=1
        identifier=self.next_id('telemetry')
        doc=dict(data,id=identifier,_id=identifier,_epoch=epoch)
        try:
            self.db.telemetry.insert_one(doc)
        except DuplicateKeyError:
            return False
        return True

    def telemetry(self, *, limit=100, before_id=None):
        query={'device_id':'node01'}
        if before_id is not None: query['id']={'$lt':before_id}
        return list(self.db.telemetry.find(query,{'_id':0,'_epoch':0}).sort('id',DESCENDING).limit(limit))

    def event(self, now, kind, data):
        identifier=self.next_id('events')
        self.db.events.insert_one(dict(_id=identifier,id=identifier,received_at=now,kind=kind,data=data))

    def events(self, limit=100, before_id=None):
        query={} if before_id is None else {'id':{'$lt':before_id}}
        return list(self.db.events.find(query,{'_id':0}).sort('id',DESCENDING).limit(limit))

    def command(self, public_id):
        return self.db.commands.find_one({'command_id':public_id},{'_id':0})

    def pending(self):
        return self.db.commands.find_one({'device_id':'node01','status':'pending'}) is not None

    def new_command(self, public_id, fingerprint, now, timeout):
        wire_id=self.next_id('commands')
        if wire_id>0xffffffff: raise ValueError('Firmware command ID space exhausted')
        doc=dict(command_id=public_id,wire_id=wire_id,device_id='node01',fingerprint=fingerprint,
                 created_at=now,deadline=now+timeout,status='pending',code=None)
        self.db.commands.insert_one(dict(doc))
        return wire_id

    def publish_failed(self, wire_id):
        self.db.commands.update_one({'wire_id':wire_id,'status':'pending'},{'$set':{'status':'publish_failed'}})

    def acknowledge(self, ack, status, now):
        # The ACK record and terminal status are one atomic document update.
        result=self.db.commands.update_one({'wire_id':ack.command_id,'device_id':'node01',
                 'status':'pending','deadline':{'$gt':now}},
                 {'$set':{'status':status,'code':ack.code,'ack':dict(ack.model_dump(),received_at=now)}})
        return result.modified_count == 1

    def expire(self, now):
        self.db.commands.update_many({'status':'pending','deadline':{'$lte':now}},
                                     {'$set':{'status':'timeout','code':-1}})

    def prune(self, now, settings):
        for name,cap,column in [('telemetry',settings.max_telemetry,'received_at'),
                                ('events',settings.max_events,'received_at'),
                                ('commands',settings.max_commands,'created_at')]:
            collection=self.db[name]
            base={'status':{'$ne':'pending'}} if name=='commands' else {}
            collection.delete_many(dict(base,**{column:{'$lt':now-settings.retention_days*86400}}))
            key='wire_id' if name=='commands' else 'id'
            # Bounded deletion batches. Counters are never pruned/reused.
            while True:
                ids=[d['_id'] for d in collection.find({}, {'_id':1}).sort(key,DESCENDING).skip(cap).limit(1000)]
                if not ids: break
                result=collection.delete_many(dict(base,_id={'$in':ids}))
                if not result.deleted_count: break

    def ping(self):
        self.db.command('ping')

    def close(self):
        self.client.close()
