"""CSV codec and simulation reader; never touches real logger data."""
from __future__ import annotations

import csv
from array import array
from math import isfinite,isnan
import io
import re
from datetime import datetime
from pathlib import Path

from .climate import MODEL,air_values

FIELDS = ["Schema", "DatensatzID", "Zeitstempel", "Temperatur", "Feuchte", "Batterie", "RSSI", "Quelle", "Messstelle", "Qualitaet"]
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Ungültige Kennung.")
    return value


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("Zeitstempel benötigt einen UTC-Offset.")
    return result


def csv_text(rows, fields=FIELDS):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fields, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def decimal(value):
    return f"{value:.2f}".replace(".", ",")


def rows_in_range(root: Path, run, logger, start=None, end=None):
    run, logger = identifier(run), identifier(logger)
    folder = root / run / logger
    if not folder.is_dir():
        raise ValueError("Testmessstelle nicht gefunden.")
    yield from read_months(folder, start, end)


def read_months(folder, start=None, end=None, fields=FIELDS):
    start_dt = parse_time(start) if start else None
    end_dt = parse_time(end) if end else None
    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError("Beginn liegt nach dem Ende.")
    # Files use UTC month boundaries. Filter months before opening them.
    from datetime import timezone
    first = start_dt.astimezone(timezone.utc).strftime("%Y-%m") if start_dt else "0000-00"
    last = end_dt.astimezone(timezone.utc).strftime("%Y-%m") if end_dt else "9999-99"
    for path in sorted(folder.glob("*/*.csv")):
        if not first <= path.stem <= last:
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            if reader.fieldnames != fields:
                raise ValueError(f"CSV-Schemafehler: {path.name}")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Unvollständige CSV-Zeile: {path.name}")
                stamp = parse_time(row["Zeitstempel"])
                if (start_dt is None or stamp >= start_dt) and (end_dt is None or stamp <= end_dt):
                    yield row


def chart_data(rows, interval_minutes, budget=1600):
    """Compact columns, streaming summaries; preserve the established point selection."""
    times=array('q');columns=[array('d') for _ in range(4)];missing=float('nan')
    selected=set();boundaries=set();segment=None;previous_mask=None;gap_ms=None
    minima=[None]*4;maxima=[None]*4
    temperature_values,humidity_values,dew_values,density_values=columns
    for row in rows:
        index=len(times);current=getattr(row,"site_segment",None)
        if index and current!=segment:boundaries.add(index)
        segment=current
        t=int(parse_time(row["Zeitstempel"]).timestamp()*1000)
        temperature=float(row["Temperatur"].replace(",",".")) if row["Temperatur"] else None
        humidity=float(row["Feuchte"].replace(",",".")) if row["Feuchte"] else None
        if temperature is not None and not isfinite(temperature) or humidity is not None and not isfinite(humidity):raise ValueError('Nicht endlicher Messwert; keine Diagrammausgabe.')
        derived=air_values(temperature,humidity)
        dew=derived['dew_point_c'];density=derived['absolute_humidity_g_m3']
        mask=(temperature is None,humidity is None,dew is None,density is None)
        if gap_ms is None:gap_ms=interval_minutes*60_000*1.5
        if index and (index in boundaries or t-times[-1]>gap_ms or mask!=previous_mask):selected.update((index-1,index))
        previous_mask=mask;times.append(t)
        temperature_values.append(missing if temperature is None else temperature)
        humidity_values.append(missing if humidity is None else humidity)
        dew_values.append(missing if dew is None else dew)
        density_values.append(missing if density is None else density)
    count=len(times)
    if not count:
        return {"points": [], "raw_count": 0, "latest": None, "min_temperature": None,
                "max_temperature": None, "min_humidity": None, "max_humidity": None,
                "climate":{"model":MODEL,"latest":None,"points":[],"min_dew_point_c":None,"max_dew_point_c":None}}
    def point(index):
        values=[column[index] for column in columns]
        values=[None if isnan(value) else value for value in values]
        # The established inverse model serializes clamped dew-point bounds as integers.
        if values[2] in MODEL['temperature_range_c']:values[2]=int(values[2])
        return [times[index],*values]
    selected.update((0,count-1));buckets=max(1,budget//8);width=max(1,(count+buckets-1)//buckets)
    for left in range(0,count,width):
        right=min(left+width,count)
        for column_index,column in enumerate(columns):
            low=float('inf');high=-low;low_index=high_index=None
            for index in range(left,right):
                value=column[index]
                if isnan(value):continue
                if value<low:low=value;low_index=index
                if value>high:high=value;high_index=index
            if low_index is not None:
                selected.update((low_index,high_index))
                if minima[column_index] is None or low<minima[column_index]:minima[column_index]=low
                if maxima[column_index] is None or high>maxima[column_index]:maxima[column_index]=high
    reduced=[];previous_index=None
    for index in sorted(selected):
        if previous_index is not None and index==previous_index+1 and (index in boundaries or times[index]-times[previous_index]>gap_ms):
            reduced.append([(times[previous_index]+times[index])/2 if index in boundaries else times[previous_index]+interval_minutes*60_000,None,None,None,None])
        reduced.append(point(index));previous_index=index
    for extrema in (minima,maxima):
        if extrema[2] in MODEL['temperature_range_c']:extrema[2]=int(extrema[2])
    summary={"raw_count":count,"latest":point(count-1)[:3],"min_temperature":minima[0],"max_temperature":maxima[0],
             "min_humidity":minima[1],"max_humidity":maxima[1]}
    return {**summary,"points":[item[:3] for item in reduced],
            "climate":{"model":MODEL,"latest":derived,"points":[[item[0],item[3],item[4]] for item in reduced],
                       "min_dew_point_c":minima[2],"max_dew_point_c":maxima[2]}}
