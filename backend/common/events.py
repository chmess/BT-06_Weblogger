"""Private, append-only monthly host events. Logging failures never retry actions."""
import csv
import fcntl
import io
import json
import os
import re
import threading
import uuid
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
from .storage import csv_text,identifier,parse_time

FIELDS=['Schema','EreignisID','Zeitstempel','Typ','Stufe','Logger','Quelle','Nachricht','DetailsJSON']
TYPES={'site.created':'Messstelle angelegt','site.updated':'Messstelle geändert','site.assigned':'Logger zugeordnet','site.unassigned':'Zuordnung beendet','application.started':'Dienst gestartet','application.stopped':'Dienst beendet',
       'receiver.started':'Hostempfang gestartet','receiver.stopped':'Hostempfang pausiert',
       'receiver.fresh':'Aktuelles Advertising','receiver.stale':'Advertising veraltet',
       'receiver.error':'Empfangs-/CSV-Fehler','receiver.recovered':'Empfangsfehler behoben',
       'device.recording':'Aufzeichnungsstatus empfangen','device.memory_full':'Speichervollkennzeichnung',
       'task.completed':'Auftrag abgeschlossen','task.failed':'Auftrag fehlgeschlagen'}
LEVELS=('info','warning','error')


class EventStore:
    def __init__(self,root):
        self.root=Path(root);self.lock=threading.RLock();self.error=None;self.failed=0;self.stored=0

    def status(self):
        with self.lock:return {'error':self.error,'failed_this_session':self.failed,'stored_this_session':self.stored,'path':'data/events'}

    def emit(self,event_type,level,message,*,logger='',source='application',details=None,at=None):
        try:return self.append(event_type,level,message,logger=logger,source=source,details=details,at=at)
        except Exception:
            with self.lock:
                self.failed+=1;self.error='Ereignis nicht als dauerhaft gespeichert bestätigt. CSV, Speicherplatz und Dateirechte prüfen; keine automatische Wiederholung.'
            return None

    def append(self,event_type,level,message,*,logger='',source='application',details=None,at=None):
        stamp=parse_time(at).astimezone(timezone.utc) if at else datetime.now(timezone.utc)
        detail=json.dumps({} if details is None else details,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        row={'Schema':'1','EreignisID':uuid.uuid4().hex,'Zeitstempel':stamp.isoformat(),'Typ':event_type,'Stufe':level,
             'Logger':logger,'Quelle':source,'Nachricht':message,'DetailsJSON':detail}
        self.validate(row)
        folder=self.root/stamp.strftime('%Y');path=folder/(stamp.strftime('%Y-%m')+'.csv')
        content=io.StringIO(newline='');csv.DictWriter(content,FIELDS,delimiter=';',lineterminator='\n').writerow(row)
        with self.lock:
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(self.root,0o700)
            fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_APPEND,0o600)
            with os.fdopen(fd,'a+b') as stream:
                fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0,os.SEEK_END);size=stream.tell()
                if size:
                    stream.seek(0)
                    if stream.readline().decode('utf-8').rstrip('\r\n')!=';'.join(FIELDS):raise ValueError('Ereignis-CSV-Schemafehler; Original erhalten.')
                    stream.seek(-1,os.SEEK_END)
                    if stream.read(1)!=b'\n':raise ValueError('Unvollständige Ereignis-CSV; Original erhalten.')
                else:stream.write((';'.join(FIELDS)+'\n').encode('utf-8'))
                stream.write(content.getvalue().encode('utf-8'));stream.flush();os.fsync(stream.fileno())
            if not size:
                for directory in (folder,self.root,self.root.parent):
                    descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
                    try:os.fsync(descriptor)
                    finally:os.close(descriptor)
            self.stored+=1;self.error=None
        return row

    @staticmethod
    def validate(row):
        if set(row)!=set(FIELDS) or not all(isinstance(row[key],str) for key in FIELDS) or row['Schema']!='1' or not re.fullmatch('[0-9a-f]{32}',row['EreignisID']):raise ValueError('Ungültiges Ereignisschema.')
        parse_time(row['Zeitstempel'])
        if row['Typ'] not in TYPES or row['Stufe'] not in LEVELS:raise ValueError('Unbekannter Ereignistyp oder Stufe.')
        if row['Logger']:identifier(row['Logger'])
        if row['Quelle'] not in ('application','receiver','history'):raise ValueError('Unbekannte Ereignisquelle.')
        if not isinstance(row['Nachricht'],str) or not row['Nachricht'] or len(row['Nachricht'])>1000 or any(ord(c)<32 for c in row['Nachricht']):raise ValueError('Ungültige Ereignisnachricht.')
        if len(row['DetailsJSON'])>4000 or not isinstance(json.loads(row['DetailsJSON']),dict):raise ValueError('Ungültige Ereignisdetails.')

    def _rows(self,path):
        with path.open('rb') as raw:
            fcntl.flock(raw,fcntl.LOCK_SH);raw.seek(0,os.SEEK_END)
            if not raw.tell():raise ValueError('Leere Ereignis-CSV; Original erhalten.')
            raw.seek(-1,os.SEEK_END)
            if raw.read(1)!=b'\n':raise ValueError('Unvollständige Ereignis-CSV; Original erhalten.')
            raw.seek(0)
            with io.TextIOWrapper(raw,encoding='utf-8',newline='') as text:
                reader=csv.DictReader(text,delimiter=';',strict=True)
                try:
                    if reader.fieldnames!=FIELDS:raise ValueError('Ereignis-CSV-Schemafehler; Original erhalten.')
                    for row in reader:
                        self.validate(row)
                        if parse_time(row['Zeitstempel']).astimezone(timezone.utc).strftime('%Y-%m')!=path.stem:raise ValueError('Ereigniszeit passt nicht zur Monatsdatei.')
                        yield row
                except (csv.Error,UnicodeError,TypeError) as exc:raise ValueError('Beschädigte Ereignis-CSV; Original erhalten.') from exc

    def rows(self,*,start=None,end=None,logger=None,event_type=None,level=None,reverse_files=False):
        begin=parse_time(start) if start else None;finish=parse_time(end) if end else None
        if begin and finish and begin>finish:raise ValueError('Beginn liegt nach dem Ende.')
        if logger:identifier(logger)
        if event_type is not None and event_type not in TYPES:raise ValueError('Unbekannter Ereignistyp.')
        if level is not None and level not in LEVELS:raise ValueError('Unbekannte Ereignisstufe.')
        lower=begin.astimezone(timezone.utc).strftime('%Y-%m') if begin else '0000-00'
        upper=finish.astimezone(timezone.utc).strftime('%Y-%m') if finish else '9999-99'
        for path in sorted(self.root.glob('*/*.csv'),reverse=reverse_files):
            if not re.fullmatch('[0-9]{4}-[0-9]{2}',path.stem) or not lower<=path.stem<=upper:continue
            for row in self._rows(path):
                stamp=parse_time(row['Zeitstempel'])
                if (begin and stamp<begin or finish and stamp>finish or logger and row['Logger']!=logger
                        or event_type and row['Typ']!=event_type or level and row['Stufe']!=level):continue
                yield row

    def query(self,limit=100,**filters):
        if type(limit) is not int or not 1<=limit<=500:raise ValueError('Ereignislimit: 1 bis 500 erforderlich.')
        # Retain bounded matches; stop before reading older months once enough exist.
        result=[]
        begin=parse_time(filters['start']).astimezone(timezone.utc).strftime('%Y-%m') if filters.get('start') else '0000-00'
        end=parse_time(filters['end']).astimezone(timezone.utc).strftime('%Y-%m') if filters.get('end') else '9999-99'
        # Validate every filter even when the directory contains no rows.
        if filters.get('start') and filters.get('end') and parse_time(filters['start'])>parse_time(filters['end']):raise ValueError('Beginn liegt nach dem Ende.')
        if filters.get('logger'):identifier(filters['logger'])
        if filters.get('event_type') is not None and filters['event_type'] not in TYPES:raise ValueError('Unbekannter Ereignistyp.')
        if filters.get('level') is not None and filters['level'] not in LEVELS:raise ValueError('Unbekannte Ereignisstufe.')
        for path in sorted(self.root.glob('*/*.csv'),reverse=True):
            if not re.fullmatch('[0-9]{4}-[0-9]{2}',path.stem) or not begin<=path.stem<=end:continue
            matches=deque(maxlen=limit+1-len(result))
            for row in self._rows(path):
                stamp=parse_time(row['Zeitstempel'])
                if (filters.get('start') and stamp<parse_time(filters['start']) or filters.get('end') and stamp>parse_time(filters['end'])
                        or filters.get('logger') and row['Logger']!=filters['logger'] or filters.get('event_type') and row['Typ']!=filters['event_type']
                        or filters.get('level') and row['Stufe']!=filters['level']):continue
                matches.append(row)
            result.extend(reversed(matches))
            if len(result)>limit:break
        return {'events':result[:limit],'truncated':len(result)>limit,'event_types':TYPES,'log_status':self.status()}
