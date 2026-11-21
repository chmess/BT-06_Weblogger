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
from history_fixture import capture
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
        print(json.dumps({'count':args.count,'create_decode_store_seconds':round(imported-started,3),
            'reimport_seconds':round(deduped-imported,3),'verify_read_chart_seconds':round(queried-deduped,3),
            'chart_points':len(chart['points']),'csv_bytes':sum(p.stat().st_size for p in Path(temp).rglob('*.csv')),
            'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


if __name__=='__main__':main()
