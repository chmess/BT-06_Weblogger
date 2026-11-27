"""Streaming descriptive statistics from original rows, without gap filling."""
from .climate import MODEL,air_values,finite_number
from .storage import parse_time


class Metric:
    def __init__(self):
        self.count=0;self.missing=0;self.mean=None;self.minimum=None;self.maximum=None
        self.previous=None;self.observed_ms=0;self.time_mean=None;self.last_valid=None

    def add(self,t,value,max_gap_ms):
        previous_t,previous_value=self.previous if self.previous else (None,None)
        if value is None:self.missing+=1
        else:
            self.count+=1
            self.mean=value if self.count==1 else self.mean*((self.count-1)/self.count)+value/self.count
            if self.minimum is None or value<self.minimum['value']:self.minimum={'value':value,'time_ms':t}
            if self.maximum is None or value>self.maximum['value']:self.maximum={'value':value,'time_ms':t}
            self.last_valid={'value':value,'time_ms':t}
            dt=t-previous_t if previous_t is not None else None
            if previous_value is not None and dt is not None and 0<dt<=max_gap_ms:
                midpoint=previous_value/2+value/2
                total=self.observed_ms+dt
                self.time_mean=midpoint if self.observed_ms==0 else self.time_mean*(self.observed_ms/total)+midpoint*(dt/total)
                self.observed_ms=total
        self.previous=(t,value)

    def result(self,span_ms):
        return {'valid_samples':self.count,'missing_samples':self.missing,'minimum':self.minimum,'maximum':self.maximum,
                'sample_mean':self.mean,'time_weighted_mean':self.time_mean,'last_valid':self.last_valid,
                'observed_seconds':self.observed_ms/1000,'unknown_seconds':max(0,span_ms-self.observed_ms)/1000,
                'coverage_fraction':self.observed_ms/span_ms if span_ms>0 else None,
                'status':'insufficient_data' if self.observed_ms==0 else 'incomplete' if self.observed_ms<span_ms else 'evaluated'}


def summarize(rows,interval_minutes,start=None,end=None):
    if not finite_number(interval_minutes) or interval_minutes<=0:raise ValueError('Messintervall unbekannt.')
    lower=round(parse_time(start).timestamp()*1000) if start else None
    upper=round(parse_time(end).timestamp()*1000) if end else None
    if lower is not None and upper is not None and lower>upper:raise ValueError('Beginn liegt nach dem Ende.')
    gap=interval_minutes*60000*1.5
    metrics={key:Metric() for key in ('temperature_c','humidity_pct','dew_point_c','absolute_humidity_g_m3')}
    first=last=None;count=0;gap_count=0;largest_gap=0;segment=None
    for row in rows:
        t=round(parse_time(row['Zeitstempel']).timestamp()*1000)
        if lower is not None and t<lower or upper is not None and t>upper:continue
        current_segment=getattr(row,"site_segment",None)
        changed=last is not None and current_segment!=segment
        if changed:
            for metric in metrics.values():metric.previous=None
        segment=current_segment
        if last is not None:
            dt=t-last
            if dt<=0:raise ValueError('Zeitreihe nicht eindeutig aufsteigend; keine Statistik.')
            largest_gap=max(largest_gap,dt)
            gap_count+=int(dt>gap or changed)
        if first is None:first=t
        last=t;count+=1
        temperature=float(row['Temperatur'].replace(',','.')) if row['Temperatur'] else None
        humidity=float(row['Feuchte'].replace(',','.')) if row['Feuchte'] else None
        temperature=temperature if finite_number(temperature) else None
        humidity=humidity if finite_number(humidity) and 0<=humidity<=100 else None
        derived=air_values(temperature,humidity)
        for key,value in (('temperature_c',temperature),('humidity_pct',humidity),('dew_point_c',derived['dew_point_c']),('absolute_humidity_g_m3',derived['absolute_humidity_g_m3'])):metrics[key].add(t,value,gap)
    begin=lower if lower is not None else first;end_time=upper if upper is not None else last
    span=max(0,end_time-begin) if begin is not None and end_time is not None else 0
    return {'model':MODEL,'raw_count':count,'interval_minutes':interval_minutes,'gap_factor':1.5,
            'gap_count':gap_count,'largest_sample_interval_seconds':largest_gap/1000,
            'range':{'start_ms':begin,'end_ms':end_time,'seconds':span/1000},
            'time_mean_method':'linear_adjacent_valid_pairs','metrics':{key:metric.result(span) for key,metric in metrics.items()}}
