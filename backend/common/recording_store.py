"""Read-only whole-history inventory evidence; zero count is not a fake CSV."""
import csv
import hashlib
import io
import json
import re
import uuid

from .bt06_gatt import ReadCommand, ProtocolError, read_request, read_reply
from .history_store import CAPTURE_FIELDS, durable_file, sync_directory
from .settings import atomic_json
from .storage import csv_text, parse_time


def decode_inventory(raw):
    if len(raw)!=10:
        raise ProtocolError('Historienumfang hat ein unbekanntes Format; kein Start.')
    count=int.from_bytes(raw[:2],'little')
    first=int.from_bytes(raw[2:6],'little');last=int.from_bytes(raw[6:],'little')
    if (not count and raw!=bytes(10)) or (count and first>last):
        raise ProtocolError('Historienzähler und Zeitgrenzen widersprechen sich; kein Start.')
    return {'count':count,'first_device_seconds':first,'last_device_seconds':last}


def inventory_capture(rows):
    if len(rows)==4:
        tx,rx=rows[:2]
        if (set(tx)!=set(CAPTURE_FIELDS) or set(rx)!=set(CAPTURE_FIELDS) or tx['Richtung']!='TX' or rx['Richtung']!='RX'
                or bytes.fromhex(tx['DatenHex'])!=read_request(ReadCommand.LOG_STATUS)):
            raise ValueError('Ungültige vorangehende Statusabfrage.')
        parse_time(tx['Hostzeit']);parse_time(rx['Hostzeit'])
        read_reply(ReadCommand.LOG_STATUS,bytes.fromhex(rx['DatenHex']))
        rows=rows[2:]
    if len(rows)!=2 or any(set(row)!=set(CAPTURE_FIELDS) for row in rows):
        raise ValueError('Historienumfang benötigt genau eine Anfrage und Antwort.')
    for row in rows:parse_time(row['Hostzeit'])
    tx,rx=rows
    if tx['Richtung']!='TX' or rx['Richtung']!='RX' or bytes.fromhex(tx['DatenHex'])!=read_request(ReadCommand.SELECT_ALL_HISTORY):
        raise ValueError('Kein belegter vollständiger Historienumfang.')
    raw=read_reply(ReadCommand.SELECT_ALL_HISTORY,bytes.fromhex(rx['DatenHex']))
    return raw,decode_inventory(raw),rx['Hostzeit']


class RecordingProofStore:
    def __init__(self,root):self.root=root

    def read_diagnostic(self,key,device_id):
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{32}',key):raise ValueError('Ungültiger Diagnosebeleg.')
        folder=self.root/'diagnostics';data=json.loads((folder/(key+'.json')).read_text());raw=(folder/(key+'.csv')).read_bytes()
        if data.get('device_id')!=device_id or hashlib.sha256(raw).hexdigest()!=data.get('capture_sha256'):
            raise ValueError('Diagnosebeleg beschädigt.')
        return list(csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter=';'))

    def diagnostic(self,device_id,rows,error):
        if not re.fullmatch('[0-9]{8}',device_id) or not 1<=len(rows)<=4:raise ValueError('Ungültiger Diagnosebeleg.')
        for row in rows:
            if set(row)!=set(CAPTURE_FIELDS):raise ValueError('Ungültige Diagnosezeile.')
            parse_time(row['Hostzeit'])
            if len(bytes.fromhex(row['DatenHex']))>64:raise ValueError('Diagnosebeleg zu groß.')
        folder=self.root/'diagnostics';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        key=uuid.uuid4().hex;content=csv_text(rows,CAPTURE_FIELDS).encode('utf-8')
        data={'id':key,'device_id':device_id,'error':error,'observed_at':rows[-1]['Hostzeit'],
              'capture_sha256':hashlib.sha256(content).hexdigest(),'valid_inventory_proof':False}
        durable_file(folder/(key+'.csv'),content)
        atomic_json(folder/(key+'.json'),data);atomic_json(folder/'latest.json',data)
        for path in (folder,self.root,self.root.parent):sync_directory(path)
        return data

    def save(self,device_id,observation):
        if not isinstance(device_id,str) or not re.fullmatch('[0-9]{8}',device_id):
            raise ValueError('Ungültige Gerätekennung.')
        raw,values,observed=inventory_capture(observation['capture'])
        if raw!=observation['metadata']:
            raise ValueError('Historienumfang widerspricht dem Original.')
        folder=self.root/'proofs';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        key=uuid.uuid4().hex;content=csv_text(observation['capture'],CAPTURE_FIELDS).encode('utf-8')
        data={'id':key,'device_id':device_id,'firmware':'2.05','schema_version':1,'observed_at':observed,
              **values,'metadata_hex':raw.hex(),'capture_sha256':hashlib.sha256(content).hexdigest()}
        durable_file(folder/(key+'.csv'),content)
        atomic_json(folder/(key+'.json'),data)
        for path in (folder,self.root,self.root.parent):sync_directory(path)
        return data

    def read(self,key,device_id):
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{32}',key):raise ValueError('Ungültiger Umfangsbeleg.')
        folder=self.root/'proofs';data=json.loads((folder/(key+'.json')).read_text());raw=(folder/(key+'.csv')).read_bytes()
        if (data.get('schema_version')!=1 or data.get('id')!=key or data.get('device_id')!=device_id
                or data.get('firmware')!='2.05' or hashlib.sha256(raw).hexdigest()!=data.get('capture_sha256')):
            raise ValueError('Historienumfangsbeleg beschädigt.')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter=';')
        if reader.fieldnames!=CAPTURE_FIELDS:raise ValueError('Ungültiges Umfangsbelegschema.')
        metadata,values,observed=inventory_capture(list(reader))
        if any(data.get(key)!=value for key,value in {**values,'observed_at':observed,'metadata_hex':metadata.hex()}.items()):
            raise ValueError('Umfangszusammenfassung widerspricht dem Original.')
        return data
