"""One atomic configuration for preferences and immutable site-assignment history."""
import json
import secrets
import threading
import time
from copy import deepcopy
from datetime import datetime,timezone
from .settings import Settings,validate_settings,atomic_json
from .sites import SiteStore,ATTRIBUTES
from .storage import parse_time

MAX_BYTES=8*1024*1024
FORMAT='BT06_SETTINGS'


class Configuration:
    def __init__(self,folder,events=None,clock=None):
        self.path=folder/'application.json';self.events=events;self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.lock=threading.RLock();self.pending=None;self.error=None
        if self.path.exists():
            if self.path.stat().st_size>MAX_BYTES:raise ValueError('Gemeinsame Konfiguration zu groß; Original erhalten.')
            value=json.loads(self.path.read_text());self.validate(value)
            settings,sites,revision=value['settings'],value['sites'],value['revision']
        else:
            settings=Settings(folder/'settings.json').get();sites=SiteStore(folder/'sites.json').value;revision=0
        self.revision=revision
        self.settings=Settings(self.path,initial=settings,lock=self.lock,persist=self._save_settings)
        self.sites=SiteStore(self.path,events,clock=self.clock,initial=sites,lock=self.lock,persist=self._save_sites)

    @staticmethod
    def validate(value):
        if (not isinstance(value,dict) or set(value)!={'format','schema_version','revision','settings','sites'}
                or value['format']!='BT06_APPLICATION' or type(value['schema_version']) is not int or value['schema_version']!=1
                or type(value['revision']) is not int or value['revision']<0):raise ValueError('Ungültige gemeinsame Konfiguration; Original erhalten.')
        validate_settings(value['settings']);SiteStore.validate(value['sites'])

    def status(self):
        with self.lock:return {'path':'config/application.json','persisted':self.path.exists(),'revision':self.revision,'error':self.error}

    def _adopt(self,value):
        self.revision=value['revision'];self.settings.value=deepcopy(value['settings']);self.sites.value=deepcopy(value['sites'])

    def _candidate(self,settings,sites):
        value={'format':'BT06_APPLICATION','schema_version':1,'revision':self.revision+1,'settings':deepcopy(settings),'sites':deepcopy(sites)}
        self.validate(value)
        if len(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode())>MAX_BYTES-1024:raise ValueError('Gemeinsame Konfiguration erreicht die 8-MiB-Grenze; keine Historie entfernt.')
        return value

    def _write(self,settings,sites):
        if self.error:raise ValueError('Konfigurationsspeicherung unbestätigt. Aktuellen Stand prüfen und Dienst neu starten; nicht automatisch wiederholen.')
        value=self._candidate(settings,sites)
        try:atomic_json(self.path,value)
        except OSError:
            self.error='Speichern nicht dauerhaft bestätigt. Sichtbare Datei und aktiven Stand prüfen; keine automatische Wiederholung.'
            if self.events:self.events.emit('settings.error','error',self.error)
            # Rename may already have happened before directory fsync failed.
            # Follow a valid visible file without claiming its durability.
            try:
                visible=json.loads(self.path.read_text());self.validate(visible);self._adopt(visible)
            except (OSError,ValueError,TypeError,KeyError):pass
            raise
        self._adopt(value)

    def _save_settings(self,value):
        if self.error:raise ValueError(self.error+' Dienst vor weiteren Änderungen neu starten.')
        if value!=self.settings.value or not self.path.exists():
            self._write(value,self.sites.value)
            if self.events:self.events.emit('settings.saved','info','Programmeinstellungen lokal gespeichert; Messstellenhistorie erhalten.')

    def _save_sites(self,value):self._write(self.settings.value,value)

    def document(self):
        with self.lock:
            stamp=self.clock().astimezone(timezone.utc).isoformat()
            for item in self.sites.value['assignments']:
                if parse_time(item['end'] or item['start'])>parse_time(stamp):raise ValueError('Hostzeit liegt vor Zuordnungshistorie; keine gültige Einstellungsdatei erzeugt.')
            return {'format':FORMAT,'schema_version':2,'exported_at':stamp,'settings':self.settings.get(),'sites':deepcopy(self.sites.value)}

    @staticmethod
    def normalize(document):
        if not isinstance(document,dict):raise ValueError('Einstellungsdatei muss ein Objekt enthalten.')
        if document.get('format')!=FORMAT:
            return {'settings':validate_settings(document),'sites':None,'exported_at':None,'legacy':True}
        if set(document)!={'format','schema_version','exported_at','settings','sites'} or type(document['schema_version']) is not int or document['schema_version']!=2:raise ValueError('Unbekanntes Einstellungsdateiformat.')
        settings=validate_settings(document['settings']);SiteStore.validate(document['sites'])
        if not isinstance(document['exported_at'],str):raise ValueError('Ungültige Dateizeit.')
        stamp=parse_time(document['exported_at'])
        for site in document['sites']['sites']:
            if parse_time(site['updated_at'])>stamp:raise ValueError('Dateizeit liegt vor Messstellenstand.')
        for item in document['sites']['assignments']:
            if parse_time(item['end'] or item['start'])>stamp:raise ValueError('Dateizeit liegt vor Zuordnungshistorie.')
        return {'settings':settings,'sites':deepcopy(document['sites']),'exported_at':document['exported_at'],'legacy':False}

    def _merge_sites(self,source,exported_at,stamp):
        current=self.sites.value;value=deepcopy(current)
        summary={'site_changes':[],'added_sites':0,'updated_sites':0,'added_intervals':0,'checkpointed_open_intervals':0,'versioned_active_intervals':0,
                 'preserved_active_loggers':len([item for item in current['assignments'] if item['end'] is None])}
        if source is None:return value,summary
        checkpoint=parse_time(exported_at)
        if checkpoint>parse_time(stamp):raise ValueError('Dateizeit liegt nach Hostzeit. Messstellenimport nicht möglich; Programmeinstellungen können separat geladen werden.')
        sites={item['id']:item for item in value['sites']}
        for original in source['sites']:
            site=sites.get(original['id'])
            if site is None:
                site=deepcopy(original);value['sites'].append(site);sites[site['id']]=site;summary['added_sites']+=1
                summary['site_changes'].append({'id':site['id'],'before':None,'after':{key:deepcopy(site[key]) for key in ATTRIBUTES}})
            else:
                if site['created_at']!=original['created_at']:raise ValueError('Messstellenidentität widerspricht lokalem Stand.')
                if any(site[key]!=original[key] for key in ATTRIBUTES):
                    summary['site_changes'].append({'id':site['id'],'before':{key:deepcopy(site[key]) for key in ATTRIBUTES},'after':{key:deepcopy(original[key]) for key in ATTRIBUTES}})
                    for key in ATTRIBUTES:site[key]=deepcopy(original[key])
                    site['updated_at']=stamp;summary['updated_sites']+=1
                    active=[item for item in value['assignments'] if item['site_id']==site['id'] and item['end'] is None]
                    for item in active:
                        item['end']=stamp;value['assignments'].append(SiteStore._assignment(item['logger'],site,stamp));summary['versioned_active_intervals']+=1
        existing={item['id']:item for item in value['assignments']}
        for original in source['assignments']:
            old=existing.get(original['id'])
            if old is not None:
                if any(old[key]!=original[key] for key in original if key!='end'):raise ValueError('Zuordnungshistorie widerspricht lokalem Stand.')
                if old['end'] is not None and original['end'] is not None and old['end']!=original['end']:raise ValueError('Geschlossenes Zuordnungsende widerspricht lokalem Stand.')
                continue
            item=deepcopy(original)
            if item['end'] is None:
                if parse_time(item['start'])==checkpoint:continue
                item['end']=exported_at;summary['checkpointed_open_intervals']+=1
            value['assignments'].append(item);existing[item['id']]=item;summary['added_intervals']+=1
        if value!=current:value['revision']=current['revision']+1
        SiteStore.validate(value)
        return value,summary

    def preview(self,request):
        if not isinstance(request,dict) or set(request)!={'document','include_sites','settings'} or type(request['include_sites']) is not bool:raise ValueError('Import benötigt Datei, Messstellenauswahl und Programmeinstellungen.')
        normalized=self.normalize(request['document']);settings=validate_settings(request['settings'])
        with self.lock:
            if self.error:raise ValueError(self.error+' Dienst vor weiteren Änderungen neu starten.')
            source=normalized['sites'] if request['include_sites'] else None
            stamp=self.sites._stamp() if source is not None else self.clock().astimezone(timezone.utc).isoformat()
            merged,summary=self._merge_sites(source,normalized['exported_at'],stamp)
            self._candidate(settings,merged)
            changes=[{'field':key,'before':self.settings.value[key],'after':settings[key]} for key in settings if self.settings.value[key]!=settings[key]]
            public={'token':secrets.token_urlsafe(32),'expires_in_seconds':600,'legacy':normalized['legacy'],
                    'include_sites':source is not None,'settings':settings,'settings_changes':changes,**summary}
            self.pending={'public':public,'revision':self.revision,'deadline':time.monotonic()+600,'source':source,'exported_at':normalized['exported_at']}
            return deepcopy(public)

    def apply(self,request):
        if not isinstance(request,dict) or set(request)!={'token'} or not isinstance(request['token'],str):raise ValueError('Konkrete Importvorschau erforderlich.')
        with self.lock:
            plan=self.pending
            if not plan or time.monotonic()>=plan['deadline'] or not secrets.compare_digest(request['token'],plan['public']['token']):raise ValueError('Importvorschau fehlt oder ist abgelaufen.')
            self.pending=None
            if plan['revision']!=self.revision:raise ValueError('Konfiguration inzwischen geändert. Neue Importvorschau prüfen.')
            stamp=self.sites._stamp() if plan['source'] is not None else self.clock().astimezone(timezone.utc).isoformat()
            sites,summary=self._merge_sites(plan['source'],plan['exported_at'],stamp)
            self._write(plan['public']['settings'],sites)
            result=self.document()
        if self.events:self.events.emit('settings.imported','info','Einstellungen importiert; bestehende aktive Loggerbelegungen beibehalten.',details={key:value for key,value in summary.items() if key!='site_changes'})
        return result
