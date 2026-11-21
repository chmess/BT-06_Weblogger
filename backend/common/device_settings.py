"""Independently decoded, read-only BT06 2.05 settings. Unknowns stay unknown."""
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone

from .bt06_gatt import ProtocolError, ReadCommand, device_clock, read_reply, read_request
from .history_store import CAPTURE_FIELDS, durable_file, sync_directory
from .settings import atomic_json
from .storage import csv_text, parse_time
import csv
import io

POWER_CODES = {1:-20, 2:-16, 3:-12, 4:-8, 5:-4, 6:0, 7:4, 8:6, 9:8}
UNVERIFIED = ['long_range_mapping', 'start_delay', 'memory_policy', 'stop_button_policy', 'start_mode', 'description', 'access_key']
SETTINGS_QUERIES=(('device_info',ReadCommand.DEVICE_INFO),('device_clock',ReadCommand.DEVICE_CLOCK),
                 ('log_status',ReadCommand.LOG_STATUS),('log_settings',ReadCommand.LOG_SETTINGS),
                 ('broadcast_settings',ReadCommand.BROADCAST_SETTINGS),('transmit_rate',ReadCommand.TRANSMIT_RATE),
                 ('temperature_alarm',ReadCommand.TEMPERATURE_ALARM),('humidity_alarm',ReadCommand.HUMIDITY_ALARM))


def settings_capture(rows):
    requests={read_request(command):(name,command) for name,command in SETTINGS_QUERIES}
    expected=None;payloads={};errors={};observed=None;total=0
    for row in rows:
        if set(row)!=set(CAPTURE_FIELDS) or any(not isinstance(v,str) for v in row.values()):
            raise ValueError('Ungültige Einstellungs-Capture-Zeile.')
        parse_time(row['Hostzeit'])
        raw=bytes.fromhex(row['DatenHex']);total+=len(raw)
        if total>65536:raise ValueError('Einstellungs-Capture zu groß.')
        if row['Richtung']=='TX':
            if expected is not None or raw not in requests:raise ProtocolError('Unerwartete Einstellungsabfrage.')
            expected=requests[raw]
        elif row['Richtung']=='RX' and expected is not None:
            name,command=expected
            if len(raw)<5 or raw[:3]!=b'\x26'+command.value or raw[-1]!=35:raise ProtocolError('Ungültige Einstellungsantwort.')
            if raw[3]==1:payloads[name]=read_reply(command,raw)
            else:errors[name]={'status':raw[3],'notice':'Abfrage abgewiesen; Wert unbekannt.'}
            expected=None;observed=row['Hostzeit']
        else:raise ProtocolError('Unerwartete Einstellungs-Capture-Richtung.')
    if expected is not None or observed is None:raise ProtocolError('Einstellungsabfrage unvollständig.')
    return payloads,errors,observed


def decode_settings(payloads):
    values, errors = {}, {}
    def parse(name, decoder):
        raw = payloads.get(name)
        if raw is None:
            return
        try:
            values.update(decoder(bytes(raw)))
        except (ValueError, UnicodeError, IndexError):
            errors[name] = 'Antwortformat oder Feldwert nicht verifiziert.'
    def name(raw):
        if len(raw)!=15:
            raise ProtocolError('Name: unbekannte Länge.')
        text=raw.rstrip(b'\xff\x00').decode('utf-8')
        if not text or any(ord(c)<32 or ord(c)==127 for c in text):
            raise ProtocolError('Name: ungültiger Text.')
        return {'name':text}
    def log(raw):
        if len(raw)!=15 or not int.from_bytes(raw[:2],'little') or raw[6] not in (0,1):
            raise ProtocolError('Aufzeichnungsformat unbekannt.')
        return {'record_interval_seconds':int.from_bytes(raw[:2],'little'),'temperature_unit':'F' if raw[6] else 'C'}
    def broadcast(raw):
        if len(raw)!=3 or raw[0] not in POWER_CODES or not int.from_bytes(raw[1:3],'little'):
            raise ProtocolError('Funkparameterformat unbekannt.')
        return {'broadcast_interval_seconds':int.from_bytes(raw[1:3],'little')/10,
                'transmit_power_dbm':POWER_CODES[raw[0]],'transmit_power_code':raw[0]}
    def rate(raw):
        if len(raw)!=1:
            raise ProtocolError('Funkmodusformat unbekannt.')
        return {'transmit_rate_code':raw[0], 'long_range':None}
    def alarm(raw):
        if len(raw)!=12 or any(raw[i] not in (0,26) for i in (0,1,6,7)):
            raise ProtocolError('Alarmformat unbekannt.')
        result={}
        for label,offset in (('low',0),('high',6)):
            result[label]={'enabled':raw[offset]==26,'type_code':raw[offset+1],
                           'delay_raw':int.from_bytes(raw[offset+2:offset+4],'little'),
                           'limit':int.from_bytes(raw[offset+4:offset+6],'little',signed=True)/10}
        return result
    def status(raw):
        if len(raw)!=30 or raw[:3]!=b'\x16\x00\x02':
            raise ProtocolError('Statusformat unbekannt.')
        code=raw[3]
        return {'recording_code':code,'recording':{1:'gestoppt',2:'USB-Stopp',4:'Speicher-voll-Stopp',5:'App-Stopp',16:'zeichnet auf',17:'Startverzögerung'}.get(code,'nicht verifiziert')}
    def clock(raw):
        return {'clock_calendar_2000':device_clock(raw,year_base=2000).isoformat(),
                'clock_calendar_1980':device_clock(raw,year_base=1980).isoformat(),'clock_verified':False}
    for key,decoder in (('device_info',name),('log_settings',log),('broadcast_settings',broadcast),('transmit_rate',rate),
                        ('temperature_alarm',lambda raw:{'temperature_alarm':alarm(raw)}),
                        ('humidity_alarm',lambda raw:{'humidity_alarm':alarm(raw)}),('log_status',status),('device_clock',clock)):
        parse(key,decoder)
    return {'values':values,'decode_errors':errors,'unverified':list(UNVERIFIED)}


class DeviceSettingsStore:
    def __init__(self, root):
        self.root=root
        self.lock=threading.RLock()
    def _folder(self, device_id):
        if not isinstance(device_id,str) or not re.fullmatch(r'[0-9]{8}',device_id):
            raise ValueError('Ungültige BT06-Gerätekennung.')
        return self.root/('bt06-'+device_id)
    def latest(self, device_id):
        with self.lock:
            folder=self._folder(device_id);path=folder/'latest.json'
            if not path.exists():return None
            data=json.loads(path.read_text())
            if data.get('schema_version')!=1 or data.get('device_id')!=device_id or not re.fullmatch(r'[0-9a-f]{32}\.csv',data.get('capture','')):
                raise ValueError('Geräteeinstellungsbeleg beschädigt.')
            raw=(folder/data['capture']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=data.get('capture_sha256'):
                raise ValueError('Geräteeinstellungs-Capture beschädigt; Original erhalten.')
            reader=csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter=';')
            if reader.fieldnames!=CAPTURE_FIELDS:raise ValueError('Geräteeinstellungs-Capture-Schemafehler.')
            payloads,errors,observed=settings_capture(reader)
            decoded=decode_settings(payloads)
            if (data.get('values')!=decoded['values'] or data.get('decode_errors')!=decoded['decode_errors']
                    or data.get('read_errors')!=errors or data.get('observed_at')!=observed):
                raise ValueError('Geräteeinstellungs-Zusammenfassung widerspricht dem Originalbeleg.')
            return data
    def save(self, device_id, observation):
        payloads,errors,observed=settings_capture(observation['capture'])
        if payloads!=observation['payloads'] or errors!=observation['read_errors']:
            raise ValueError('Geräteeinstellungen widersprechen dem Lese-Capture.')
        decoded=decode_settings(payloads)
        if not decoded['values']:
            raise ValueError('Keine verifizierten Geräteeinstellungen gelesen.')
        with self.lock:
            folder=self._folder(device_id);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            capture=csv_text(observation['capture'],CAPTURE_FIELDS).encode('utf-8')
            filename=uuid.uuid4().hex+'.csv'
            data={'schema_version':1,'kind':'device-settings','device_id':device_id,'firmware':'2.05','read_only':True,
                  'observed_at':observed,'saved_at':datetime.now(timezone.utc).isoformat(),'capture':filename,
                  'capture_sha256':hashlib.sha256(capture).hexdigest(),**decoded,'read_errors':errors}
            durable_file(folder/filename,capture)
            for location in (folder,self.root,self.root.parent):sync_directory(location)
            atomic_json(folder/'latest.json',data)
            return data
