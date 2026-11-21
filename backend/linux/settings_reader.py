"""Explicit read-only BT06 settings queries; no save/unlock/start/stop opcodes."""
import asyncio
from datetime import datetime,timezone
from backend.common.bt06_gatt import SERVICE_UUID,TX_UUID,RX_UUID,ReadCommand,ProtocolError,read_request,read_reply
from .history_reader import known_device
from backend.common.device_settings import SETTINGS_QUERIES

QUERIES=SETTINGS_QUERIES


async def retrieve_settings(config,progress,*,client=None):
    owned=client is None
    if owned:
        from bleak import BleakClient
        progress('finding_device')
        target=await known_device(config)
        client=BleakClient(target,pair=False,timeout=45)
    queue=asyncio.Queue(maxsize=32);capture=[];overflow=False
    def note(direction,data):
        capture.append({'Hostzeit':datetime.now(timezone.utc).isoformat(),'Richtung':direction,'DatenHex':data.hex()})
    def notify(sender,data):
        nonlocal overflow
        raw=bytes(data)
        if len(raw)>4096 or queue.full() or len(capture)>64:
            overflow=True;return
        note('RX',raw);queue.put_nowait(raw)
    try:
        if owned:
            progress('connecting');await asyncio.wait_for(client.connect(),50)
        service=client.services.get_service(SERVICE_UUID)
        tx=service.get_characteristic(TX_UUID) if service else None
        rx=service.get_characteristic(RX_UUID) if service else None
        if tx is None or rx is None or 'write' not in tx.properties or 'notify' not in rx.properties:
            raise ProtocolError('GATT-Service nicht als BT06-Lesepfad verifiziert.')
        await asyncio.wait_for(client.start_notify(rx,notify),8)
        payloads={};errors={}
        for index,(name,command) in enumerate(QUERIES):
            progress('reading_settings',received=index,expected=len(QUERIES))
            wire=read_request(command);note('TX',wire)
            await asyncio.wait_for(client.write_gatt_char(tx,wire,response=True),8)
            reply=await asyncio.wait_for(queue.get(),8)
            if overflow or len(reply)<5 or reply[0]!=38 or reply[1:3]!=command.value or reply[-1]!=35:
                raise ProtocolError('Unerwartete Geräteeinstellungsantwort; keine Parameteränderung.')
            if reply[3]!=1:
                errors[name]={'status':reply[3],'notice':'Abfrage abgewiesen; Wert unbekannt.'}
                continue
            payloads[name]=read_reply(command,reply)
        progress('reading_settings',received=len(QUERIES),expected=len(QUERIES))
        if not queue.empty():raise ProtocolError('Zusätzliche unerwartete Einstellungsantwort.')
        await asyncio.wait_for(client.stop_notify(rx),8)
        return {'payloads':payloads,'capture':capture,'read_errors':errors}
    finally:
        if owned:await asyncio.wait_for(client.disconnect(),10)
