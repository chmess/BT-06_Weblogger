"""Fixed SDK read sequence: logger status immediately before whole-history scope."""
import asyncio
from datetime import datetime,timezone

from backend.common.bt06_gatt import ReadCommand,TX_UUID,RX_UUID,SERVICE_UUID,ProtocolError,read_request,read_reply
from backend.common.recording_store import decode_inventory


async def inventory(client,progress,on_failure=None):
    progress('reading_inventory')
    service=client.services.get_service(SERVICE_UUID)
    tx=service.get_characteristic(TX_UUID);rx=service.get_characteristic(RX_UUID)
    queue=asyncio.Queue(maxsize=1);capture=[];overflow=False
    def note(direction,raw):capture.append({'Hostzeit':datetime.now(timezone.utc).isoformat(),'Richtung':direction,'DatenHex':raw.hex()})
    def notify(sender,raw):
        nonlocal overflow
        if queue.full() or len(raw)>64:overflow=True;return
        raw=bytes(raw);note('RX',raw);queue.put_nowait(raw)
    async def query(command):
        raw=read_request(command);note('TX',raw)
        await asyncio.wait_for(client.write_gatt_char(tx,raw,response=True),8)
        response=await asyncio.wait_for(queue.get(),8)
        if overflow:raise ProtocolError('Historienumfang mehrdeutig; kein Start.')
        return read_reply(command,response)
    await asyncio.wait_for(client.start_notify(rx,notify),8)
    try:
        status=await query(ReadCommand.LOG_STATUS)
        metadata=await query(ReadCommand.SELECT_ALL_HISTORY)
        decode_inventory(metadata)
        return {'metadata':metadata,'status':status,'capture':capture}
    except (ProtocolError,TimeoutError) as error:
        if on_failure:on_failure(capture,str(error))
        raise
    finally:
        await asyncio.wait_for(client.stop_notify(rx),8)
