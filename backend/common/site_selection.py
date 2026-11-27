"""Filter original host rows without inferring past locations or device time."""
from bisect import bisect_right
from copy import deepcopy
from .sites import SITE_ID
from .storage import parse_time


class SiteRow(dict):
    """Keep internal continuity metadata out of original CSV columns."""


def select_site(store,logger,site_id,rows):
    if not isinstance(site_id,str) or not SITE_ID.fullmatch(site_id):raise ValueError('Ungültige Messstellenkennung.')
    with store.lock:
        site=next((deepcopy(item) for item in store.value['sites'] if item['id']==site_id),None)
        if site is None:raise ValueError('Unbekannte Messstelle.')
        intervals=deepcopy([item for item in store.value['assignments'] if item['logger']==logger and item['site_id']==site_id])
        revision=store.value['revision']
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
