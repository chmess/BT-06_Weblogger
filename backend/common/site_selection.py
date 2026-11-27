"""Filter original host rows without inferring past locations or device time."""
from bisect import bisect_right
from copy import deepcopy
from heapq import merge
from .sites import SITE_ID
from .storage import parse_time


class SiteRow(dict):
    """Keep internal continuity metadata out of original CSV columns."""


def site_snapshot(store,site_id):
    if not isinstance(site_id,str) or not SITE_ID.fullmatch(site_id):raise ValueError('Ungültige Messstellenkennung.')
    with store.lock:
        site=next((deepcopy(item) for item in store.value['sites'] if item['id']==site_id),None)
        if site is None:raise ValueError('Unbekannte Messstelle.')
        intervals=deepcopy([item for item in store.value['assignments'] if item['site_id']==site_id])
        revision=store.value['revision']
    return site,intervals,revision


def select_site(store,logger,site_id,rows,*,snapshot=None):
    site,assignments,revision=snapshot if snapshot is not None else site_snapshot(store,site_id)
    intervals=[item for item in assignments if item['logger']==logger]
    intervals.sort(key=lambda item:parse_time(item['start']))
    starts=[parse_time(item['start']) for item in intervals]
    ends=[parse_time(item['end']) if item['end'] else None for item in intervals]
    def filtered():
        for row in rows:
            # The persisted original ID is mandatory: never reassign older rows.
            if row['Messstelle']!=site_id:continue
            stamp=parse_time(row['Zeitstempel']);index=bisect_right(starts,stamp)-1
            if index<0 or ends[index] is not None and stamp>=ends[index]:continue
            selected=SiteRow(row);selected.site_segment=intervals[index]['id'];yield selected
    return filtered(),{'site_id':site_id,'current_name':site['name'],'logger':logger,'revision':revision,
                       'assignment_intervals':len(intervals),'basis':'stored_id_and_host_assignment',
                       'criteria_automatic':False}


MAX_LOGGERS=64


def select_all_loggers(store,live,site_id,start=None,end=None):
    snapshot=site_snapshot(store,site_id);site,intervals,revision=snapshot
    lower=parse_time(start) if start else None;upper=parse_time(end) if end else None
    if lower and upper and lower>upper:raise ValueError('Beginn liegt nach dem Ende.')
    relevant=[item for item in intervals if (upper is None or parse_time(item['start'])<=upper)
              and (lower is None or item['end'] is None or parse_time(item['end'])>lower)]
    loggers=sorted({item['logger'] for item in relevant})
    if len(loggers)>MAX_LOGGERS:raise ValueError('Mehr als 64 Logger im Messstellenzeitraum; Zeitraum eingrenzen.')
    def combined():
        originals=[];streams=[]
        try:
            for logger in loggers:
                rows=live.rows(logger,start,end);originals.append(rows)
                filtered,_=select_site(store,logger,site_id,rows,snapshot=snapshot)
                def tagged(source,logger_id):
                    for row in source:row['Logger']=logger_id;yield row
                streams.append(tagged(filtered,logger))
            yield from merge(*streams,key=lambda row:parse_time(row['Zeitstempel']))
        finally:
            for stream in streams:stream.close()
            for rows in originals:
                if hasattr(rows,'close'):rows.close()
    return combined(),{'site_id':site_id,'current_name':site['name'],'logger':'all','loggers':loggers,
                       'revision':revision,'assignment_intervals':len(relevant),
                       'basis':'stored_id_and_host_assignment','criteria_automatic':False}
