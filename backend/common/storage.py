"""CSV codec and simulation reader; never touches real logger data."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path

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
    """Bounded chart payload, including both T/RH extrema and explicit gaps."""
    points = []
    for row in rows:
        points.append([int(parse_time(row["Zeitstempel"]).timestamp() * 1000),
                       float(row["Temperatur"].replace(",", ".")) if row["Temperatur"] else None,
                       float(row["Feuchte"].replace(",", ".")) if row["Feuchte"] else None])
    if not points:
        return {"points": [], "raw_count": 0, "latest": None, "min_temperature": None,
                "max_temperature": None, "min_humidity": None, "max_humidity": None}
    count = len(points)
    summary = {"raw_count": count, "latest": points[-1],
               "min_temperature": min((p[1] for p in points if p[1] is not None), default=None),
               "max_temperature": max((p[1] for p in points if p[1] is not None), default=None),
               "min_humidity": min((p[2] for p in points if p[2] is not None), default=None),
               "max_humidity": max((p[2] for p in points if p[2] is not None), default=None)}
    # Preserve gap boundaries as well as extrema. Never draw a line across a gap.
    selected = {0, count - 1}
    gap_ms = interval_minutes * 60_000 * 1.5
    for i in range(1, count):
        if points[i][0] - points[i - 1][0] > gap_ms or [v is None for v in points[i][1:]] != [v is None for v in points[i-1][1:]]:
            selected.update((i - 1, i))
    width = max(1, (count + budget // 4 - 1) // (budget // 4))
    for left in range(0, count, width):
        indices = range(left, min(left + width, count))
        for column in (1, 2):
            valid = [i for i in indices if points[i][column] is not None]
            if valid:
                selected.add(min(valid, key=lambda i: points[i][column]))
                selected.add(max(valid, key=lambda i: points[i][column]))
    reduced = []
    previous_index = None
    for i in sorted(selected):
        if previous_index is not None and i == previous_index + 1 and points[i][0] - points[previous_index][0] > gap_ms:
            reduced.append([points[previous_index][0] + interval_minutes * 60_000, None, None])
        reduced.append(points[i])
        previous_index = i
    return {**summary, "points": reduced}
