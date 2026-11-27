"""Streaming humidity-phase analysis of original rows; no persistence or BLE.

Durations count adjacent valid sample pairs, never across missing values or
intervals over 1.5 times the configured source cadence. See docs/KLIMA.md.
"""
from collections import deque
from .climate import MODEL,finite_number,saturation_pressure
from .storage import parse_time

FIELDS={'air_threshold','surface_threshold','hysteresis','minimum_minutes','surface_mode','surface_value'}


def validate_options(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('Feuchteauswertung: vollständige Kriterien erforderlich.')
    for field in ('air_threshold','surface_threshold'):
        if not finite_number(value[field]) or not 0<value[field]<=100:raise ValueError('Feuchteschwellen müssen über 0 und höchstens 100 % sein.')
    if not finite_number(value['hysteresis']) or not 0<=value['hysteresis']<min(value['air_threshold'],value['surface_threshold']):raise ValueError('Hysterese muss nichtnegativ und kleiner als beide Schwellen sein.')
    if not finite_number(value['minimum_minutes']) or not 0<=value['minimum_minutes']<=43200:raise ValueError('Mindestdauer: 0 bis 43.200 Minuten erforderlich.')
    mode,surface=value['surface_mode'],value['surface_value']
    if mode not in ('none','fixed','delta'):raise ValueError('Oberflächenannahme unbekannt.')
    if mode=='none':
        if surface is not None:raise ValueError('Ohne Oberflächenannahme darf kein Oberflächenwert gesetzt sein.')
    elif not finite_number(surface) or not ((-45<=surface<=60) if mode=='fixed' else (0<=surface<=50)):
        raise ValueError('Oberfläche: −45 bis 60 °C; Differenz zur Luft: 0 bis 50 K.')
    return dict(value)


def options_from_query(query):
    if not FIELDS<=set(query):raise ValueError('Kriterien der Feuchteauswertung fehlen.')
    value={key:query[key][0] for key in FIELDS}
    for key in FIELDS-{'surface_mode'}:value[key]=None if key=='surface_value' and value[key]=='' else float(value[key])
    return validate_options(value)


class Phases:
    def __init__(self,threshold,hysteresis,minimum_seconds,max_gap_ms):
        self.threshold,self.release=threshold,threshold-hysteresis
        self.minimum,self.max_gap=minimum_seconds,max_gap_ms
        self.previous=None;self.active=None;self.items=deque(maxlen=100)
        self.observed=0;self.above=0;self.total=0;self.qualified=0;self.longest=0
        self.samples=0;self.invalid=0;self.above_samples=0

    def finish(self,reason):
        if self.active is None:return
        phase=self.active;phase['end_reason']=reason
        phase['qualified']=phase['duration_seconds']>=self.minimum
        phase['right_censored']=reason!='below_release'
        self.total+=1;self.qualified+=int(phase['qualified'])
        self.longest=max(self.longest,phase['duration_seconds']);self.items.append(phase);self.active=None

    def add(self,t,value):
        self.samples+=1;self.invalid+=int(value is None)
        previous_t,previous_value=self.previous if self.previous else (None,None)
        dt=t-previous_t if previous_t is not None else None
        connected=dt is not None and 0<dt<=self.max_gap and previous_value is not None and value is not None
        if connected:
            self.observed+=dt/1000
            if previous_value>=self.threshold and value>=self.threshold:self.above+=dt/1000
        else:self.finish('invalid_value' if value is None or previous_value is None else 'data_gap')
        if value is None:self.finish('invalid_value')
        else:
            self.above_samples+=int(value>=self.threshold)
            if self.active is not None:
                if value<self.release:self.finish('below_release')
                else:
                    self.active['end_ms']=t;self.active['duration_seconds']=(t-self.active['start_ms'])/1000
                    self.active['peak_pct']=max(self.active['peak_pct'],value)
            if self.active is None and value>=self.threshold:
                self.active={'start_ms':t,'end_ms':t,'duration_seconds':0,'peak_pct':value,'left_censored':not connected}
        self.previous=(t,value)

    def result(self,span):
        self.finish('range_end')
        unknown=max(0,span-self.observed)
        return {'threshold_pct':self.threshold,'release_pct':self.release,'minimum_seconds':self.minimum,
                'observed_seconds':self.observed,'unknown_seconds':unknown,
                'coverage_fraction':self.observed/span if span>0 else None,
                'status':'insufficient_data' if self.observed==0 else 'incomplete' if unknown>0.001 else 'evaluated',
                'above_threshold_seconds':self.above,'above_threshold_samples':self.above_samples,
                'sample_count':self.samples,'invalid_samples':self.invalid,'phase_count':self.total,
                'qualified_phase_count':self.qualified,'longest_phase_seconds':self.longest,
                'phases':list(self.items),'omitted_phases':max(0,self.total-len(self.items))}


def analyze(rows,interval_minutes,options,start=None,end=None):
    options=validate_options(options)
    if not finite_number(interval_minutes) or interval_minutes<=0:raise ValueError('Messintervall unbekannt.')
    lower=round(parse_time(start).timestamp()*1000) if start else None
    upper=round(parse_time(end).timestamp()*1000) if end else None
    if lower is not None and upper is not None and lower>upper:raise ValueError('Beginn liegt nach dem Ende.')
    minimum=options['minimum_minutes']*60;gap=interval_minutes*60000*1.5
    air=Phases(options['air_threshold'],options['hysteresis'],minimum,gap)
    use_surface=options['surface_mode']!='none'
    surface=Phases(options['surface_threshold'],options['hysteresis'],minimum,gap) if use_surface else None
    condensation=Phases(100,0,minimum,gap) if use_surface else None
    fixed_pressure=saturation_pressure(options['surface_value']) if options['surface_mode']=='fixed' else None
    first=last=None;segment=None
    for row in rows:
        t=round(parse_time(row['Zeitstempel']).timestamp()*1000)
        if lower is not None and t<lower or upper is not None and t>upper:continue
        if last is not None and t<=last:raise ValueError('Zeitreihe nicht eindeutig aufsteigend; keine Phasenauswertung.')
        current_segment=getattr(row,"site_segment",None)
        if last is not None and current_segment!=segment:
            for channel in (air,surface,condensation):
                if channel is not None:channel.finish("assignment_boundary");channel.previous=None
        segment=current_segment
        if first is None:first=t
        last=t
        temperature=float(row['Temperatur'].replace(',','.')) if row['Temperatur'] else None
        rh=float(row['Feuchte'].replace(',','.')) if row['Feuchte'] else None
        valid_rh=finite_number(rh) and 0<=rh<=100
        air.add(t,rh if valid_rh else None)
        if use_surface:
            calculated=None
            if valid_rh and finite_number(temperature) and -45<=temperature<=60:
                ts=options['surface_value'] if fixed_pressure is not None else temperature-options['surface_value']
                if -45<=ts<=60:calculated=saturation_pressure(temperature)*rh/(fixed_pressure if fixed_pressure is not None else saturation_pressure(ts))
            surface.add(t,calculated);condensation.add(t,calculated)
    range_start=lower if lower is not None else first
    range_end=upper if upper is not None else last
    span=max(0,(range_end-range_start)/1000) if range_start is not None and range_end is not None else 0
    return {'model':MODEL,'criteria':options,'interval_minutes':interval_minutes,'gap_factor':1.5,
            'duration_method':'adjacent_valid_pairs','range':{'start_ms':range_start,'end_ms':range_end,'seconds':span},
            'air':air.result(span),'surface':surface.result(span) if surface else None,
            'condensation':condensation.result(span) if condensation else None}
