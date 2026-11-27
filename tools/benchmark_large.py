#!/usr/bin/env python3
"""Serial, resource-limited CSV workloads in disposable storage; no live API/BLE."""
import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.common.storage import FIELDS,chart_data,csv_text
from backend.common.csv_download import prepared_csv,CHUNK_BYTES
from backend.common.statistics import summarize
from backend.common.risk import analyze

MODES=('chart','statistics','risk','export','spooled_export')
CRITERIA={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':60,'surface_mode':'none','surface_value':None}


def rows(path):
    with path.open(encoding='utf-8',newline='') as stream:yield from csv.DictReader(stream,delimiter=';')


def worker(mode,path):
    resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    started=time.perf_counter()
    if mode=='spooled_export':
        digest=hashlib.sha256()
        with prepared_csv(rows(path),FIELDS,path.parent) as (stream,size):
            assert stream.read(3)==b'\xef\xbb\xbf'
            for chunk in iter(lambda:stream.read(CHUNK_BYTES),b''):digest.update(chunk)
        print(json.dumps({'mode':mode,'seconds':round(time.perf_counter()-started,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          'result_sha256':digest.hexdigest(),'export_bytes':size}));return
    if mode=='chart':
        result=chart_data(rows(path),1);summary={'rows':result['raw_count'],'points':len(result['points'])}
    elif mode=='statistics':
        result=summarize(rows(path),1);summary={'rows':result['raw_count']}
    elif mode=='risk':
        result=analyze(rows(path),1,CRITERIA);summary={'rows':result['air']['sample_count']}
    else:
        result=csv_text(rows(path));summary={'export_bytes':len(result.encode('utf-8-sig'))}
    payload=(result if isinstance(result,str) else json.dumps(result,sort_keys=True,allow_nan=False)).encode('utf-8')
    print(json.dumps({'mode':mode,'seconds':round(time.perf_counter()-started,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      'result_sha256':hashlib.sha256(payload).hexdigest(),**summary}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows',type=int,default=1000000)
    parser.add_argument('--modes',default=','.join(MODES))
    parser.add_argument('--output',type=Path)
    parser.add_argument('--worker',choices=MODES,help=argparse.SUPPRESS)
    parser.add_argument('--input',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:worker(args.worker,args.input);return
    modes=args.modes.split(',')
    if not 1<=args.rows<=1000000 or not modes or len(set(modes))!=len(modes) or set(modes)-set(MODES):parser.error('1–1.000.000 Zeilen und eindeutige bekannte Modi erforderlich.')
    with tempfile.TemporaryDirectory(prefix='bt06-large-bench-') as temporary:
        path=Path(temporary)/'synthetic.csv';started=time.perf_counter();start=datetime(2024,1,1,tzinfo=timezone.utc)
        if os.statvfs(temporary).f_bavail*os.statvfs(temporary).f_frsize<args.rows*256:raise RuntimeError('Nicht genügend freier temporärer Speicher für den begrenzten Benchmark.')
        with path.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,FIELDS,delimiter=';',lineterminator='\n');writer.writeheader()
            for index in range(args.rows):
                stamp=start+timedelta(minutes=index+(60 if index>=args.rows//2 else 0))
                writer.writerow({'Schema':'1','DatensatzID':'benchmark-'+str(index),'Zeitstempel':stamp.isoformat(),
                    'Temperatur':'' if index%10007==137 else f'{20+(index%401)/100:.2f}'.replace('.',','),
                    'Feuchte':f'{50+(index%4000)/100:.2f}'.replace('.',','),'Batterie':'','RSSI':'',
                    'Quelle':'Simulation','Messstelle':'benchmark-test','Qualitaet':'SYNTHETISCH'})
        generated=time.perf_counter()-started;digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        measurements=[]
        for mode in modes:
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',mode,'--input',str(path)],capture_output=True,text=True,timeout=150)
            if completed.returncode:raise RuntimeError(f'Benchmark {mode} fehlgeschlagen ({completed.returncode}): '+completed.stderr[-1000:])
            result=json.loads(completed.stdout)
            if mode not in ('export','spooled_export') and result['rows']!=args.rows:raise RuntimeError('Zeilenanzahl stimmt nicht.')
            measurements.append(result);print(json.dumps(result),flush=True)
        report={'platform':platform.machine(),'python':platform.python_version(),'rows':args.rows,'csv_bytes':path.stat().st_size,'dataset_sha256':digest.hexdigest(),
                'generate_seconds':round(generated,3),'scope':'isolated synthetic CSV; serial fresh workers; warm page cache; not HTTP, BLE, SMApi or endurance',
                'worker_limit_mib':768,'worker_cpu_limit_seconds':120,'measurements':measurements}
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({key:value for key,value in report.items() if key!='measurements'}),flush=True)


if __name__=='__main__':main()
