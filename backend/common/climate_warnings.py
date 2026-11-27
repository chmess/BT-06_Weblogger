"""Session-local indicators from persisted host samples; never infer missing time."""
import threading
from copy import deepcopy
from datetime import datetime,timezone
from .climate import finite_number,saturation_pressure
from .risk import Phases
from .storage import parse_time

LABELS={'air':'Luftfeuchte','surface':'angenommene Oberflächenfeuchte','condensation':'angenommene Kondensationsbedingung'}


class ClimateWarnings:
    def __init__(self,sites,events):
        self.sites=sites;self.events=events;self.lock=threading.RLock();self.entries={};self.error=None
        self.started_at=datetime.now(timezone.utc).isoformat()

    def _emit(self,kind,entry,channel,at,reason=None,phase=None):
        item=entry['channels'][channel];phase=phase if phase is not None else item['phases'].active
        details={'site_id':entry['site_id'],'assignment_id':entry['assignment_id'],'channel':channel,
                 'criteria':entry['criteria'],'reason':reason,'duration_seconds':phase['duration_seconds'] if phase else None}
        messages={'climate.warning':'Konfigurierter Feuchteindikator aktiv: ',
                  'climate.cleared':'Freigabeschwelle unterschritten: ',
                  'climate.unknown':'Bisheriger Feuchteindikator nicht weiter beurteilbar: '}
        try:
            saved=self.events.emit(kind,'warning' if kind!='climate.cleared' else 'info',messages[kind]+LABELS[channel]+'. Keine Schimmelwahrscheinlichkeit.',
                                   logger=entry['logger'],source='climate-monitor',at=at,details=details)
            item['event_saved']=saved is not None
        except Exception:
            item['event_saved']=False;self.error='Warnereignis nicht dauerhaft bestätigt; Ereignisablage prüfen.'

    def _invalidate(self,entry,reason,stamp):
        for channel,item in entry['channels'].items():
            if item['alerted']:self._emit('climate.unknown',entry,channel,stamp,reason)
            item['alerted']=False;item['value']=None
            item['phases'].finish(reason);item['phases'].previous=None
        entry['valid']=False;entry['reason']=reason

    def pause(self,reason='host_paused',now=None):
        stamp=(now or datetime.now(timezone.utc)).isoformat()
        with self.lock:
            for entry in self.entries.values():
                if entry['valid']:self._invalidate(entry,reason,stamp)

    def _new(self,logger,assignment,cadence):
        criteria=deepcopy(assignment['site_snapshot']['criteria']);minimum=criteria['minimum_minutes']*60;gap=cadence*1500
        channels={'air':{'phases':Phases(criteria['air_threshold'],criteria['hysteresis'],minimum,gap)}}
        if criteria['surface_mode']!='none':
            channels['surface']={'phases':Phases(criteria['surface_threshold'],criteria['hysteresis'],minimum,gap)}
            channels['condensation']={'phases':Phases(100,0,minimum,gap)}
        for item in channels.values():item.update(alerted=False,value=None,event_saved=None)
        return {'logger':logger,'site_id':assignment['site_id'],'assignment_id':assignment['id'],
                'site_name':assignment['site_snapshot']['name'],'criteria':criteria,'cadence_seconds':cadence,
                'valid':False,'reason':'waiting_for_sample','last_ms':None,'last_stored_at':None,'channels':channels}

    def observe(self,logger,row,cadence_seconds):
        try:self._observe(logger,row,cadence_seconds)
        except Exception:
            with self.lock:
                self.error='Automatische Feuchteauswertung fehlgeschlagen; keine Entwarnung ableiten.'
                entry=self.entries.get(logger)
                if entry:self._invalidate(entry,'evaluation_error',datetime.now(timezone.utc).isoformat())

    def _observe(self,logger,row,cadence):
        if row.get('Schema')!='2' or row.get('Quelle')!='BLE-Advertising' or row.get('Zeitbasis')!='Host-Empfang':return
        if not finite_number(cadence) or cadence<=0:raise ValueError('Speicherintervall unbekannt.')
        stamp=parse_time(row['Zeitstempel']);t=round(stamp.timestamp()*1000)
        assignment=self.sites.resolve(logger,stamp.isoformat())
        with self.lock:
            self.error=None
            entry=self.entries.get(logger)
            if not assignment or assignment['site_id']!=row['Messstelle']:
                if entry and entry['valid']:self._invalidate(entry,'no_matching_assignment',stamp.isoformat())
                return
            if entry and entry['last_ms'] is not None and t<=entry['last_ms']:
                self._invalidate(entry,'host_time_not_increasing',stamp.isoformat());return
            if entry is None or entry['assignment_id']!=assignment['id'] or entry['cadence_seconds']!=cadence:
                if entry and entry['valid']:self._invalidate(entry,'assignment_or_cadence_changed',stamp.isoformat())
                entry=self._new(logger,assignment,cadence);self.entries[logger]=entry
            temperature=float(row['Temperatur'].replace(',','.')) if row['Temperatur'] else None
            rh=float(row['Feuchte'].replace(',','.')) if row['Feuchte'] else None
            valid_rh=finite_number(rh) and 0<=rh<=100
            values={'air':rh if valid_rh else None,'surface':None,'condensation':None}
            criteria=entry['criteria']
            if criteria['surface_mode']!='none' and valid_rh and finite_number(temperature) and -45<=temperature<=60:
                surface=criteria['surface_value'] if criteria['surface_mode']=='fixed' else temperature-criteria['surface_value']
                if -45<=surface<=60:
                    calculated=saturation_pressure(temperature)*rh/saturation_pressure(surface)
                    values['surface']=values['condensation']=calculated
            for channel,item in entry['channels'].items():
                phases=item['phases'];previous=phases.active
                phases.add(t,values[channel]);current=phases.active
                if item['alerted'] and (current is None or previous is not current):
                    reason=phases.items[-1]['end_reason']
                    self._emit('climate.cleared' if reason=='below_release' else 'climate.unknown',entry,channel,stamp.isoformat(),reason,previous)
                    item['alerted']=False
                if current is not None and current['duration_seconds']>=phases.minimum and not item['alerted']:
                    self._emit('climate.warning',entry,channel,stamp.isoformat());item['alerted']=True
                item['value']=values[channel]
            entry.update(valid=True,reason=None,last_ms=t,last_stored_at=stamp.isoformat())

    def tick(self,now=None):
        now=now or datetime.now(timezone.utc);stamp=now.isoformat();t=round(now.timestamp()*1000)
        try:
            with self.lock:
                if not any(entry['valid'] for entry in self.entries.values()):return
            with self.sites.lock:
                assignments={item['logger']:item['id'] for item in self.sites.value['assignments'] if item['end'] is None}
            with self.lock:
                for entry in self.entries.values():
                    if not entry['valid']:continue
                    reason='assignment_changed' if assignments.get(entry['logger'])!=entry['assignment_id'] else 'host_time_backwards' if t<entry['last_ms'] else 'sample_gap' if t-entry['last_ms']>entry['cadence_seconds']*1500 else None
                    if reason:self._invalidate(entry,reason,stamp)
        except Exception:
            self.pause('evaluation_error',now)
            with self.lock:self.error='Aktuelle Messstellen-/Zeitzuordnung nicht prüfbar; keine Entwarnung ableiten.'

    def status(self,now=None):
        self.tick(now)
        with self.lock:
            entries=[]
            for entry in self.entries.values():
                channels={}
                for name,item in entry['channels'].items():
                    phase=item['phases'].active
                    state='unknown' if not entry['valid'] or item['value'] is None else 'warning' if item['alerted'] else 'pending' if phase else 'below_threshold'
                    channels[name]={'state':state,'value_pct':item['value'],'phase_seconds':phase['duration_seconds'] if phase else 0,
                                    'event_saved':item['event_saved']}
                entries.append({key:deepcopy(value) for key,value in entry.items() if key not in ('channels','last_ms')}|{'channels':channels})
            return {'started_at':self.started_at,'scope':'new_persisted_host_samples','error':self.error,'entries':entries,
                    'active_count':sum(item['state']=='warning' for entry in entries for item in entry['channels'].values())}
