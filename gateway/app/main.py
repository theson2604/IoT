import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from bson.errors import InvalidDocument
from gateway.app.config import Settings
from gateway.app.models.contracts import CommandRequest
from gateway.app.models.responses import Health, Devices, DeviceStatus, Measurement, History, Events, CommandResult
from gateway.app.mqtt.transport import PahoTransport
from gateway.app.services.gateway import Gateway, Conflict, Unavailable

log = logging.getLogger(__name__)

def create_app(settings=None, transport=None, *, clock=None, background=True):
    settings = settings or Settings.from_env()
    transport = transport or PahoTransport(settings)

    @asynccontextmanager
    async def lifespan(app):
        service = Gateway(settings, transport, **({'clock': clock} if clock else {}))
        app.state.gateway = service
        transport.start()
        stopping = asyncio.Event()
        async def worker():
            while not stopping.is_set():
                try:
                    await asyncio.to_thread(service.tick)
                except Exception:
                    log.exception('Gateway maintenance failed')
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=0.1)
                except TimeoutError:
                    pass
        task = asyncio.create_task(worker()) if background else None
        try:
            yield
        finally:
            if task:
                stopping.set()
                await task
            transport.stop()
            # Synchronize with any tick still completing in a thread.
            await asyncio.to_thread(service.close)

    app = FastAPI(title='Energy PC Gateway', version='0.2.0', lifespan=lifespan)
    @app.exception_handler(PyMongoError)
    async def database_error(request, exc):
        log.error('MongoDB operation failed (%s)', type(exc).__name__)
        return JSONResponse(status_code=503, content={'detail':'MongoDB unavailable or operation failed'})

    @app.exception_handler(InvalidDocument)
    async def document_error(request, exc):
        return JSONResponse(status_code=500, content={'detail':'Invalid persistence document'})

    def service():
        return app.state.gateway
    def device(device_id):
        if device_id != 'node01':
            raise HTTPException(404, 'Unknown device')

    @app.get('/health', response_model=Health)
    def health():
        service().store.ping()
        return {'status':'ok', 'mqtt_connected':transport.connected, 'schema_version':1}

    @app.get('/api/devices', response_model=Devices)
    def devices():
        return {'items':[service().status()]}

    @app.get('/api/devices/{device_id}/status', response_model=DeviceStatus)
    def status(device_id: str):
        device(device_id)
        return service().status()

    @app.get('/api/devices/{device_id}/telemetry/latest', response_model=Measurement)
    def latest(device_id: str):
        device(device_id)
        with service().lock:
            rows = service().store.telemetry(limit=1)
        if not rows:
            raise HTTPException(404, 'No telemetry yet')
        return rows[0]

    @app.get('/api/devices/{device_id}/telemetry/history', response_model=History)
    def history(device_id: str, limit: int = Query(100, ge=1, le=1000), before_id: int | None = Query(None, ge=1, le=0x7fffffffffffffff)):
        device(device_id)
        with service().lock:
            return {'items': service().store.telemetry(limit=limit, before_id=before_id)}

    @app.get('/api/events', response_model=Events)
    def events(limit: int = Query(100, ge=1, le=1000), before_id: int | None = Query(None, ge=1, le=0x7fffffffffffffff)):
        with service().lock:
            return {'items': service().store.events(limit, before_id)}

    @app.post('/api/devices/{device_id}/commands', status_code=202, response_model=CommandResult)
    def command(device_id: str, request: CommandRequest):
        device(device_id)
        try:
            return service().create_command(request)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except Unavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get('/api/commands/{command_id}', response_model=CommandResult)
    def result(command_id: str):
        with service().lock:
            service().store.expire(service().clock())
            row = service().store.command(command_id)
        if not row:
            raise HTTPException(404, 'Unknown command')
        return row

    return app
