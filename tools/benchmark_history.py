#!/usr/bin/env python3
"""Synthetic snapshot import/read benchmark in a temporary directory; no BLE."""
import argparse
import json
import resource
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from history_fixture import capture, range_capture
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
from backend.common.storage import chart_data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=32000)
    args=parser.parse_args()
    if not 1<=args.count<=65535:parser.error('count muss zwischen 1 und 65535 liegen')
    with tempfile.TemporaryDirectory(prefix='bt06-history-bench-') as temp:
        started=time.perf_counter()
        transfer=decode_capture(capture(seconds=[1700000000+i*600 for i in range(args.count)]))
        store=HistoryStore(Path(temp)/'data/history')
        result=store.publish('12345678',**transfer)
        imported=time.perf_counter()
        repeated=store.publish('12345678',**transfer)
        deduped=time.perf_counter()
        chart=chart_data(store.chart_rows(result['logger'],result['id']),10)
        queried=time.perf_counter()
        assert result['count']==args.count and repeated['duplicate'] and chart['raw_count']==args.count
        extra={}
        if args.count>=16 and args.count<=65532:
            seconds=[1700000000+i*600 for i in range(args.count+3)]
            transfer=decode_capture(range_capture(seconds,seconds[args.count-16]-1,seconds[-1]+1))
            delta=store.publish('12345678',**transfer,base_snapshot=result['id'])
            appended=time.perf_counter()
            assert len(store.rows(delta['logger'],delta['id']))==args.count+3
            series=store.series();assert len(series)==1 and series[0]['count']==args.count+3
            indexed=time.perf_counter()
            extra={'append_3_seconds':round(appended-queried,3),'verify_series_seconds':round(indexed-appended,3),
                   'append_measurement_csv_bytes':sum((store.root/delta['logger']/delta['id']/name).stat().st_size for name in delta['files'] if name!='capture.csv'),
                   'append_received_count':delta['received_count'],'append_new_count':delta['new_count']}
        print(json.dumps({'count':args.count,'create_decode_store_seconds':round(imported-started,3),
            'reimport_seconds':round(deduped-imported,3),'verify_read_chart_seconds':round(queried-deduped,3),
            'chart_points':len(chart['points']),'csv_bytes':sum(p.stat().st_size for p in Path(temp).rglob('*.csv')),
            'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**extra}))


if __name__=='__main__':main()
