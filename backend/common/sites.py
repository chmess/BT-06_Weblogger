"""Versioned local measuring-site assignments for host-timestamped observations."""
import json
import re
import threading
import unicodedata
import uuid
from copy import deepcopy
from datetime import datetime,timezone
from .risk import validate_options
from .settings import atomic_json
from .storage import parse_time

SITE_ID=re.compile(r'^site-[0-9a-f]{32}$')
LOGGER=re.compile(r'^bt06-[0-9]{8}$')
ATTRIBUTES={'name','room','description','criteria'}


def validate_attributes(value):
    if not isinstance(value,dict) or set(value)!=ATTRIBUTES:raise ValueError('Name, Raum, Beschreibung und Kriterien vollständig angeben.')
    for key,maximum,required in (('name',80,True),('room',80,False),('description',2000,False)):
        text=value[key]
        if (not isinstance(text,str) or len(text)>maximum or text!=text.strip() or required and not text
                or any(unicodedata.category(c).startswith('C') and not (key=='description' and c=='\n') for c in text)):
            raise ValueError('Ungültige Messstellenangabe: '+key)
    validate_options(value['criteria'])
    return deepcopy(value)


class SiteStore:
    def __init__(self,path,events=None,clock=None):
        self.path=path;self.events=events;self.clock=clock or (lambda:datetime.now(timezone.utc));self.lock=threading.RLock()
        self.value=json.loads(path.read_text()) if path.exists() else {'schema_version':1,'revision':0,'sites':[],'assignments':[]}
        self.validate(self.value)

    @staticmethod
    def validate_site(site):
        if not isinstance(site,dict) or set(site)!=ATTRIBUTES|{'id','created_at','updated_at'} or not isinstance(site['id'],str) or not SITE_ID.fullmatch(site['id']):raise ValueError('Ungültige Messstellenkennung.')
        validate_attributes({key:site[key] for key in ATTRIBUTES})
        if not isinstance(site['created_at'],str) or not isinstance(site['updated_at'],str):raise ValueError('Ungültige Messstellenzeit.')
        if parse_time(site['updated_at'])<parse_time(site['created_at']):raise ValueError('Messstellenzeitfolge ungültig.')

    @classmethod
    def validate(cls,value):
        if (not isinstance(value,dict) or set(value)!={'schema_version','revision','sites','assignments'}
                or type(value['schema_version']) is not int or value['schema_version']!=1 or type(value['revision']) is not int or value['revision']<0
                or not isinstance(value['sites'],list) or len(value['sites'])>200
                or not isinstance(value['assignments'],list) or len(value['assignments'])>10000):raise ValueError('Messstellenkonfiguration ungültig; Original erhalten.')
        ids=set()
        for site in value['sites']:
            cls.validate_site(site)
            if site['id'] in ids:raise ValueError('Doppelte Messstelle.')
            ids.add(site['id'])
        assignment_ids=set();groups={}
        for assignment in value['assignments']:
            if (not isinstance(assignment,dict) or set(assignment)!={'id','logger','site_id','start','end','site_snapshot'}
                    or not isinstance(assignment['id'],str) or not re.fullmatch('[0-9a-f]{32}',assignment['id']) or assignment['id'] in assignment_ids
                    or not isinstance(assignment['logger'],str) or not LOGGER.fullmatch(assignment['logger']) or not isinstance(assignment['site_id'],str) or assignment['site_id'] not in ids):raise ValueError('Ungültige Zuordnungshistorie.')
            assignment_ids.add(assignment['id']);cls.validate_site(assignment['site_snapshot'])
            if not isinstance(assignment['start'],str) or assignment['end'] is not None and not isinstance(assignment['end'],str):raise ValueError('Ungültige Zuordnungszeit.')
            begin=parse_time(assignment['start']);end=parse_time(assignment['end']) if assignment['end'] is not None else None
            if (assignment['site_snapshot']['id']!=assignment['site_id'] or parse_time(assignment['site_snapshot']['updated_at'])>begin
                    or end is not None and end<=begin):raise ValueError('Ungültiges Zuordnungsintervall.')
            for key in (('logger',assignment['logger']),('site',assignment['site_id'])):groups.setdefault(key,[]).append((begin,end))
        for intervals in groups.values():
            previous=None
            for begin,end in sorted(intervals,key=lambda item:item[0]):
                if previous is not None and (previous[1] is None or begin<previous[1]):raise ValueError('Überlappende Zuordnungshistorie.')
                previous=(begin,end)

    def snapshot(self):
        with self.lock:
            return {'schema_version':1,'revision':self.value['revision'],'sites':deepcopy(self.value['sites']),
                    'active_assignments':deepcopy([item for item in self.value['assignments'] if item['end'] is None]),
                    'assignment_count':len(self.value['assignments'])}

    def history(self,logger=None,site_id=None,limit=100):
        if logger is not None and not LOGGER.fullmatch(logger):raise ValueError('Ungültige Loggerkennung.')
        if site_id is not None and not SITE_ID.fullmatch(site_id):raise ValueError('Ungültige Messstellenkennung.')
        if type(limit) is not int or not 1<=limit<=500:raise ValueError('Zuordnungslimit: 1 bis 500.')
        with self.lock:
            result=[item for item in reversed(self.value['assignments']) if (logger is None or item['logger']==logger) and (site_id is None or item['site_id']==site_id)]
            return {'assignments':deepcopy(result[:limit]),'truncated':len(result)>limit}

    def resolve(self,logger,at):
        stamp=parse_time(at)
        with self.lock:
            for item in reversed(self.value['assignments']):
                if item['logger']==logger and parse_time(item['start'])<=stamp and (item['end'] is None or stamp<parse_time(item['end'])):return deepcopy(item)
        return None

    def _revision(self,revision):
        if type(revision) is not int or revision!=self.value['revision']:raise ValueError('Messstellenstand ersetzt. Neu laden und Änderung erneut prüfen.')

    def _stamp(self):
        now=self.clock()
        if now.utcoffset() is None:raise ValueError('Hostzeit benötigt UTC-Offset.')
        previous=[parse_time(site['updated_at']) for site in self.value['sites']]
        previous += [parse_time(item['end'] or item['start']) for item in self.value['assignments']]
        if previous and now<=max(previous):raise ValueError('Hostzeit nicht vorwärts fortgeschritten; keine Zuordnungsänderung.')
        return now.astimezone(timezone.utc).isoformat()

    def _commit(self,value):
        value['revision']+=1;self.validate(value);atomic_json(self.path,value);self.value=value

    def _emit(self,kind,message,logger='',details=None,at=None):
        if self.events:self.events.emit(kind,'info',message,logger=logger,details=details,at=at)

    @staticmethod
    def _assignment(logger,site,stamp):
        return {'id':uuid.uuid4().hex,'logger':logger,'site_id':site['id'],'start':stamp,'end':None,'site_snapshot':deepcopy(site)}

    def save(self,request):
        if not isinstance(request,dict) or set(request)!={'revision','id','values'}:raise ValueError('Ungültiger Messstellenauftrag.')
        attributes=validate_attributes(request['values'])
        with self.lock:
            self._revision(request['revision']);stamp=self._stamp();value=deepcopy(self.value);site_id=request['id']
            if site_id is None:
                site={**attributes,'id':'site-'+uuid.uuid4().hex,'created_at':stamp,'updated_at':stamp};value['sites'].append(site);kind='site.created'
            else:
                site=next((item for item in value['sites'] if item['id']==site_id),None)
                if site is None:raise ValueError('Messstelle nicht gefunden.')
                if all(site[key]==attributes[key] for key in ATTRIBUTES):raise ValueError('Keine Messstellenänderung.')
                site.update(**attributes,updated_at=stamp);kind='site.updated'
                active=[item for item in value['assignments'] if item['site_id']==site_id and item['end'] is None]
                for item in active:item['end']=stamp;value['assignments'].append(self._assignment(item['logger'],site,stamp))
            self._commit(value);result=deepcopy(site);snapshot=self.snapshot()
        self._emit(kind,'Messstelle gespeichert: '+site['name'],details={'site_id':site['id']},at=stamp)
        return {'site':result,**snapshot}

    def assign(self,request):
        if (not isinstance(request,dict) or set(request)!={'revision','logger','site_id'}
                or not isinstance(request['logger'],str) or not LOGGER.fullmatch(request['logger'])):raise ValueError('Ungültiger Zuordnungsauftrag.')
        with self.lock:
            self._revision(request['revision']);value=deepcopy(self.value);logger=request['logger'];site_id=request['site_id']
            site=next((item for item in value['sites'] if item['id']==site_id),None) if site_id is not None else None
            if site_id is not None and site is None:raise ValueError('Messstelle nicht gefunden.')
            active=[item for item in value['assignments'] if item['end'] is None]
            if any(item['logger']==logger and item['site_id']==site_id for item in active):raise ValueError('Diese Zuordnung ist bereits aktiv.')
            closed=[item for item in active if item['logger']==logger or site_id is not None and item['site_id']==site_id]
            if site_id is None and not closed:raise ValueError('Keine aktive Zuordnung für diesen Logger.')
            stamp=self._stamp()
            for item in closed:item['end']=stamp
            if site is not None:value['assignments'].append(self._assignment(logger,site,stamp))
            self._commit(value);snapshot=self.snapshot()
        for item in closed:self._emit('site.unassigned','Zuordnung ab Hostzeit beendet; Loggeraufzeichnung unverändert.',logger=item['logger'],details={'site_id':item['site_id'],'assignment_id':item['id']},at=stamp)
        if site:self._emit('site.assigned','Zuordnung ab Hostzeit zu Messstelle: '+site['name'],logger=logger,details={'site_id':site_id},at=stamp)
        return snapshot
