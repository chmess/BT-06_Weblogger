#!/usr/bin/env python3
"""Inspect actual flock ownership; signal only an identified portable server."""
import argparse
import fcntl
import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.linux.runtime import process_start_ticks

OPTIONS={'--root','--port','--base-path','--public-origin','--days','--interval-minutes','--seed','--scenario','--end'}
PYTHON_FLAGS={'-u','-B','-E','-I','-s','-S','-O','-OO'}


def process_identity(pid):
    proc=Path('/proc')/str(pid);raw=(proc/'cmdline').read_bytes().split(b'\0')
    if raw and raw[-1]==b'':raw.pop()
    argv=[value.decode(errors='surrogateescape') for value in raw]
    if not argv or not (proc/'exe').resolve().name.startswith('python'):return None
    args=argv[1:]
    while args and args[0] in PYTHON_FLAGS:args=args[1:]
    if not args:return None
    cwd=(proc/'cwd').resolve();script=Path(args.pop(0));script=script if script.is_absolute() else cwd/script
    if script.resolve()!=ROOT/'app.py':return None
    command=None;data_root=ROOT
    while args:
        token=args.pop(0)
        if command is None and token in ('serve','generate'):command=token;continue
        name,equal,value=token.partition('=')
        if name not in OPTIONS:return None
        if not equal:
            if not args:return None
            value=args.pop(0)
        if name=='--root':
            path=Path(value);data_root=(path if path.is_absolute() else cwd/path).resolve()
    if command is None:return None
    return {'command':command,'data_root':data_root}


def flock_owner(stream):
    stat=os.fstat(stream.fileno());device=(os.major(stat.st_dev),os.minor(stat.st_dev),stat.st_ino)
    for line in Path('/proc/locks').read_text().splitlines():
        fields=line.split()
        if len(fields)<6 or fields[1]!='FLOCK' or fields[3]!='WRITE':continue
        major,minor,inode=fields[5].split(':')
        if (int(major,16),int(minor,16),int(inode))==device:return int(fields[4])
    raise RuntimeError('Sperrbesitzer nicht eindeutig nachweisbar. Kein Signal gesendet.')


def require_all_stopped():
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:
            if proc.stat().st_uid!=os.getuid():continue
            if process_identity(int(proc.name)) is not None:raise RuntimeError('Eine Instanz dieses Programmstands läuft noch; vor Update alle Datenverzeichnisse beenden.')
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError:raise RuntimeError('Eigene Prozesse nicht vollständig prüfbar; Update nicht freigegeben.') from None


def managed_unit(pid):
    units=set()
    for line in (Path('/proc')/str(pid)/'cgroup').read_text().splitlines():
        group=line.split(':',2)[-1];unit=group.rsplit('/',1)[-1]
        if unit.endswith('.service'):units.add((unit,'/user@' in group and not unit.startswith('user@')))
    for unit,user in units:
        try:
            result=subprocess.run(['systemctl',*(['--user'] if user else []),'show',unit,'-p','MainPID','--value'],capture_output=True,text=True,timeout=3)
            if result.returncode or not result.stdout.strip().isdecimal():raise RuntimeError('Dienstzuordnung nicht prüfbar. Kein Signal gesendet.')
            if int(result.stdout.strip())==pid:return unit
        except subprocess.TimeoutExpired:raise RuntimeError('Dienstzuordnung nicht rechtzeitig prüfbar. Kein Signal gesendet.') from None
    return None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['status','stop','require-stopped']);parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();data_root=args.root.resolve()
    if args.command=='require-stopped':require_all_stopped()
    lock=data_root/'runtime/app.lock'
    if lock.is_symlink():raise RuntimeError('Symbolische Prozesssperre nicht zulässig. Kein Signal gesendet.')
    if not lock.exists():print('BT-06 Weblogger ist beendet.');return
    with lock.open() as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            if args.command=='require-stopped':raise RuntimeError('Datenverzeichnis ist belegt; Update nicht freigegeben.')
            record=json.load(stream)
            if not isinstance(record,dict) or (set(record)!={'pid'} and (type(record.get('schema_version')) is not int or record['schema_version']!=2 or type(record.get('start_ticks')) is not int)):
                raise RuntimeError('Unbekannter oder ungültiger Prozessbeleg. Kein Signal gesendet.')
            pid=record.get('pid')
            if type(pid) is not int or pid<=0 or flock_owner(stream)!=pid:raise RuntimeError('PID und tatsächlicher Sperrbesitzer widersprechen sich. Kein Signal gesendet.')
            fd=os.pidfd_open(pid)
            try:
                identity=process_identity(pid)
                if identity is None or identity['data_root']!=data_root:raise RuntimeError('Programm-/Datenverzeichnis des Prozesses stimmt nicht. Kein Signal gesendet.')
                if record.get('schema_version')==2 and (record.get('start_ticks')!=process_start_ticks(pid) or record.get('code_root')!=str(ROOT) or record.get('data_root')!=str(data_root) or record.get('command')!=identity['command']):raise RuntimeError('Prozessfingerabdruck stimmt nicht. Kein Signal gesendet.')
                print(f"BT-06 Weblogger aktiv (PID {pid}, {identity['command']}).")
                if args.command=='stop':
                    if identity['command']!='serve':raise RuntimeError('Kein Webserver; laufende CLI-Aufgabe nicht automatisch abbrechen.')
                    if managed_unit(pid):raise RuntimeError('Systemd-verwalteter Hauptprozess: über systemctl stoppen; kein direktes Signal gesendet.')
                    # Check the owner again immediately before signalling through the pidfd.
                    if flock_owner(stream)!=pid:raise RuntimeError('Sperrbesitzer inzwischen geändert. Kein Signal gesendet.')
                    signal.pidfd_send_signal(fd,signal.SIGTERM)
                    poll=select.poll();poll.register(fd,select.POLLIN)
                    if not poll.poll(10000):raise RuntimeError('Beenden noch nicht abgeschlossen; keine erzwungene Terminierung.')
                    print('Programm geordnet beendet.')
            finally:os.close(fd)
        else:print('BT-06 Weblogger ist beendet.')


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as exc:
        print(f'Statusprüfung fehlgeschlagen: {exc}',file=sys.stderr);sys.exit(1)
