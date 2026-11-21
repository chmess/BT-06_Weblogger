"""Synthetic configuration replies; no real device identifiers or settings."""
from datetime import datetime,timedelta,timezone
from backend.common.device_settings import SETTINGS_QUERIES
from backend.common.bt06_gatt import read_request


def observation(rejected=None):
    name=b'Demo BT06'+bytes([255])*6
    status=bytearray(30);status[:4]=bytes.fromhex('16000210')
    log=bytearray(15);log[:2]=(1230).to_bytes(2,'little')
    alarm=bytes([26,0,2,0])+(-45).to_bytes(2,'little',signed=True)+bytes([0,26,5,0])+(317).to_bytes(2,'little',signed=True)
    humidity=bytes([0,0,0,0])+(350).to_bytes(2,'little')+bytes([26,0,0,0])+(650).to_bytes(2,'little')
    payloads={'device_info':name,'device_clock':bytes([44,6,22,11,12,13]),'log_status':bytes(status),'log_settings':bytes(log),
              'broadcast_settings':bytes([6,125,0]),'transmit_rate':bytes([255]),'temperature_alarm':alarm,'humidity_alarm':humidity}
    rows=[];errors={}
    def add(direction,raw):rows.append({'Hostzeit':(datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=len(rows))).isoformat(),'Richtung':direction,'DatenHex':raw.hex()})
    for key,command in SETTINGS_QUERIES:
        add('TX',read_request(command))
        if key==rejected:
            add('RX',b'\x26'+command.value+b'\x05\x23');payloads.pop(key)
            errors[key]={'status':5,'notice':'Abfrage abgewiesen; Wert unbekannt.'}
        else:add('RX',b'\x26'+command.value+b'\x01'+payloads[key]+b'\x23')
    return {'payloads':payloads,'capture':rows,'read_errors':errors}
