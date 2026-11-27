"""Bounded structural checks of a completed synthetic run, without regeneration."""
import csv
import json
import math
import os
import re
import time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from .simulation import validate_options
from .storage import FIELDS,identifier,parse_time


class BudgetReached(Exception):pass


def inspect_simulation(root,run,*,max_files=100,max_bytes=32*1024*1024,max_rows=250000,max_seconds=5):
    if not isinstance(run,str) or not re.fullmatch(r'demo-[0-9a-f]{12}',run):raise ValueError('Ungültige Testlaufkennung.')
    started=time.monotonic();deadline=started+max_seconds;folder=root/run;files=0;entries=0
    result={'scope':'selected_simulation_run','run':run,'checked_at':datetime.now(timezone.utc).isoformat(),
            'state':'partial','complete':False,'checksums_available':False,'loggers_checked':0,'files_checked':0,'rows_checked':0,
            'bytes_checked':0,'reason':None,'limits':{'files':max_files,'bytes':max_bytes,'rows':max_rows,'seconds':max_seconds,'directory_entries':10000}}
    def budget():
        if time.monotonic()>=deadline:raise BudgetReached('Zeitbudget erreicht; nur teilweise geprüft.')
    def file_size(path):
        nonlocal files
        budget()
        if path.is_symlink() or not path.is_file():raise ValueError('Ungültiger Dateipfad.')
        size=path.stat().st_size;files+=1
        if files>max_files or result['bytes_checked']+size>max_bytes:raise BudgetReached('Datei-/Byte-Limit erreicht; nur teilweise geprüft.')
        result['bytes_checked']+=size;return size
    def children(path):
        nonlocal entries
        with os.scandir(path) as items:
            for item in items:
                budget();entries+=1
                if entries>10000:raise BudgetReached('Verzeichniseintragslimit erreicht; nur teilweise geprüft.')
                if item.is_symlink():raise ValueError('Symbolischer Pfad.')
                yield item
    def expected(options):
        end=parse_time(options['end']);stamp=end-timedelta(days=options['days']);step=timedelta(minutes=options['interval_minutes']);zone=ZoneInfo('Europe/Berlin')
        while stamp<=end:
            if options['scenario']!='gaps' or not 11<=stamp.astimezone(zone).hour<14:yield stamp
            stamp+=step
    try:
        if root.is_symlink() or folder.is_symlink():raise ValueError('Symbolischer Testlaufpfad.')
        manifest=folder/'manifest.json'
        if file_size(manifest)>256*1024:raise BudgetReached('Manifest zu groß für diese Diagnose.')
        meta=json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(meta,dict) or type(meta.get('schema_version')) is not int or meta['schema_version']!=1 or meta.get('id')!=run or meta.get('source')!='Simulation':raise ValueError('Ungültiges Testlaufmanifest.')
        if not isinstance(meta.get('created_at'),str) or not isinstance(meta.get('options'),dict) or not isinstance(meta['options'].get('end'),str):raise ValueError('Ungültige Zeit-/Generatorangaben.')
        parse_time(meta['created_at']);options=validate_options(meta['options'])
        if options!=meta['options']:raise ValueError('Nicht kanonische Generatoroptionen.')
        loggers=meta['loggers']
        if not isinstance(loggers,list) or not 1<=len(loggers)<=3:raise ValueError('Ungültige Testmessstellen.')
        ids=set()
        for logger in loggers:
            identifier(logger['id'])
            if logger['id'] in ids or type(logger['count']) is not int or logger['count']<=0:raise ValueError('Ungültige Messstellenkennung oder Zeilenanzahl.')
            ids.add(logger['id'])
        for entry in children(folder):
            if entry.name=='manifest.json' and entry.is_file(follow_symlinks=False):continue
            if entry.name not in ids or not entry.is_dir(follow_symlinks=False):raise ValueError('Unerwarteter Inhalt im Testlauf.')
        result['files_checked']=1
        for logger in loggers:
            count=0;sequence=expected(options);paths=[]
            for year in children(folder/logger['id']):
                if not re.fullmatch('[0-9]{4}',year.name) or not year.is_dir(follow_symlinks=False):raise ValueError('Ungültige Jahresablage.')
                for entry in children(folder/logger['id']/year.name):
                    if not re.fullmatch('[0-9]{4}-[0-9]{2}\\.csv',entry.name) or not entry.is_file(follow_symlinks=False):raise ValueError('Ungültige Monatsablage.')
                    paths.append(folder/logger['id']/year.name/entry.name)
                    if len(paths)>max_files:raise BudgetReached('Dateilimit erreicht; nur teilweise geprüft.')
            for path in sorted(paths):
                size=file_size(path)
                if not size:raise ValueError('Leere CSV-Datei.')
                with path.open('rb') as tail:
                    tail.seek(-1,2)
                    if tail.read(1)!=b'\n':raise ValueError('Unvollständiger Dateischluss.')
                with path.open(encoding='utf-8',newline='') as stream:
                    reader=csv.DictReader(stream,delimiter=';',strict=True)
                    if reader.fieldnames!=FIELDS:raise ValueError('Falsches CSV-Schema.')
                    for row in reader:
                        budget()
                        if result['rows_checked']>=max_rows:raise BudgetReached('Zeilenlimit erreicht; nur teilweise geprüft.')
                        if None in row or any(value is None for value in row.values()):raise ValueError('Ungültige Spaltenzahl.')
                        stamp=parse_time(row['Zeitstempel']);wanted=next(sequence,None)
                        if stamp!=wanted or stamp.astimezone(timezone.utc).strftime('%Y/%Y-%m')!=path.parent.name+'/'+path.stem:raise ValueError('Zeitfolge, Monatsablage oder Szenariozeitpunkt falsch.')
                        if (row['Schema']!='1' or row['Quelle']!='Simulation' or row['Qualitaet']!='SYNTHETISCH' or row['Messstelle']!=logger['id']
                                or row['DatensatzID']!=logger['id']+'-'+str(int(stamp.timestamp())) or row['Batterie'] or row['RSSI']):raise ValueError('Quellen-/Kennzeichnungsfehler.')
                        temperature=float(row['Temperatur'].replace(',','.'));humidity=float(row['Feuchte'].replace(',','.'))
                        if not math.isfinite(temperature) or not math.isfinite(humidity) or not 1<=humidity<=100:raise ValueError('Ungültige Klimawerte.')
                        count+=1;result['rows_checked']+=1
                result['files_checked']+=1
            if count!=logger['count'] or next(sequence,None) is not None:raise ValueError('Testdatenbestand unvollständig.')
            result['loggers_checked']+=1
        budget();result.update(state='ok',complete=True,reason='Struktur, Kennzeichnung, Zeitraster und Anzahlen ohne Befund. Keine Referenz-Prüfsummen vorhanden; kein Nachweis unveränderter Klimawerte.')
    except BudgetReached as exc:result['reason']=str(exc)
    except (OSError,ValueError,TypeError,KeyError,OverflowError,UnicodeError,csv.Error,RecursionError):
        result.update(state='error',reason='Testlaufmanifest, CSV-Struktur, Quelle, Zeitraster, Werte oder Vollständigkeit fehlerhaft. Originale unverändert; keine Reparatur.')
    result['elapsed_seconds']=round(time.monotonic()-started,3)
    return result
