"""Explicit, bounded, read-only inspection of native host CSV files."""
import csv
import fcntl
import math
import os
import re
import time
from datetime import datetime,timezone
from itertools import islice
from .live_store import LIVE_FIELDS
from .storage import parse_time

MAX_FILES=100
MAX_BYTES=32*1024*1024
MAX_ROWS=250000
MAX_SECONDS=5


class InspectionError(ValueError):pass

def host_files(root,result,deadline):
    # Explicit directory reads preserve access failures; glob can hide them.
    pending=[(root,0)];visited=0
    while pending:
        folder,depth=pending.pop()
        try:
            if folder.is_symlink():raise InspectionError('Symbolisches Verzeichnis; nicht geprüft.')
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited+=1
                    if visited>10000 or time.monotonic()>=deadline:
                        result['complete']=False;return
                    relevant=bool(re.fullmatch(r'bt06-[0-9]{8}',entry.name)) if depth==0 else bool(re.fullmatch(r'[0-9]{4}',entry.name)) if depth==1 else entry.name.endswith('.csv')
                    if not relevant:continue
                    path=folder/entry.name
                    if entry.is_symlink():
                        result['errors'].append({'file':path.relative_to(root).as_posix(),'reason':'Symbolischer Link; nicht geprüft.'});continue
                    if depth<2 and entry.is_dir(follow_symlinks=False):pending.append((path,depth+1))
                    elif depth==2 and entry.is_file(follow_symlinks=False):yield path
        except FileNotFoundError:
            if folder!=root:result['complete']=False
        except (OSError,InspectionError):
            result['complete']=False;result['errors'].append({'file':folder.relative_to(root).as_posix(),'reason':'Verzeichnis nicht lesbar oder symbolisch; nicht geprüft.'})


def inspect_live(root,*,max_files=MAX_FILES,max_bytes=MAX_BYTES,max_rows=MAX_ROWS,max_seconds=MAX_SECONDS):
    started=time.monotonic();deadline=started+max_seconds
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'host_csv_only',
            'state':'empty','complete':True,'files_checked':0,'rows_checked':0,'bytes_checked':0,
            'errors':[],'skipped':[],'limits':{'files':max_files,'bytes':max_bytes,'rows':max_rows,'seconds':max_seconds,'directory_entries':10000}}
    files=list(islice(host_files(root,result,deadline),max_files+1))
    if len(files)>max_files:result['complete']=False;files=files[:max_files]
    for path in sorted(files):
        relative=path.relative_to(root).as_posix();previous=None;ids=set()
        if time.monotonic()>=deadline:
            result['complete']=False;result['skipped'].append({'file':relative,'reason':'Zeitlimit erreicht.'});break
        try:
            if any(part.is_symlink() for part in (path,path.parent,path.parent.parent)):
                raise InspectionError('Symbolischer Link; nicht geprüft.')
            with path.open('r',encoding='utf-8',newline='') as stream:
                try:fcntl.flock(stream,fcntl.LOCK_SH|fcntl.LOCK_NB)
                except BlockingIOError:
                    result['complete']=False;result['skipped'].append({'file':relative,'reason':'Datei wird geschrieben; später erneut prüfen.'});continue
                size=path.stat().st_size
                if size>max_bytes-result['bytes_checked']:
                    result['complete']=False;result['skipped'].append({'file':relative,'reason':'Byte-Limit erreicht.'});continue
                # The shared lock excludes the native append writer for this file.
                result['bytes_checked']+=size
                if size:
                    with path.open('rb') as tail:
                        tail.seek(-1,2)
                        if tail.read(1)!=b'\n':raise InspectionError('Unvollständiger Dateischluss; keine Reparatur ausgeführt.')
                reader=csv.DictReader(stream,delimiter=';',strict=True)
                if reader.fieldnames!=LIVE_FIELDS:raise InspectionError('CSV-Kopf entspricht nicht dem Host-Schema.')
                for row in reader:
                    if result['rows_checked']>=max_rows or time.monotonic()>=deadline:
                        result['complete']=False;result['skipped'].append({'file':relative,'reason':'Zeilen-/Zeitlimit erreicht; Datei nur teilweise geprüft.'});break
                    if None in row or any(value is None for value in row.values()):raise InspectionError('Unvollständige oder zusätzliche CSV-Spalten.')
                    if row['Schema']!='2' or row['Quelle']!='BLE-Advertising' or row['Zeitbasis']!='Host-Empfang':raise InspectionError('Unpassendes Schema, Quelle oder Zeitbasis.')
                    stamp=parse_time(row['Zeitstempel'])
                    if stamp.astimezone(timezone.utc).strftime('%Y-%m')!=path.stem:raise InspectionError('Zeitstempel passt nicht zum UTC-Monat der Datei.')
                    if previous is not None and stamp<=previous:raise InspectionError('Zeitstempel nicht eindeutig aufsteigend.')
                    if not row['DatensatzID'] or row['DatensatzID'] in ids:raise InspectionError('Fehlende oder doppelte Datensatzkennung.')
                    for key in ('Temperatur','Feuchte'):
                        if row[key]:
                            value=float(row[key].replace(',','.'))
                            if not math.isfinite(value) or key=='Feuchte' and not 0<=value<=100:raise InspectionError('Ungültiger Temperatur-/Feuchtewert.')
                    previous=stamp;ids.add(row['DatensatzID']);result['rows_checked']+=1
                else:
                    result['files_checked']+=1
        except InspectionError as exc:
            result['errors'].append({'file':relative,'reason':str(exc)})
        except (OSError,ValueError,csv.Error,UnicodeError):
            # Never return raw values, exception payloads or absolute host paths.
            result['errors'].append({'file':relative,'reason':'Struktur, Zeitfolge, Messwerte oder Dateizugriff fehlerhaft. Original unverändert.'})
    result['state']='error' if result['errors'] else 'partial' if not result['complete'] else 'ok' if files else 'empty'
    result['elapsed_seconds']=round(time.monotonic()-started,3)
    return result
