"""Reproducible artificial climate scenarios, isolated from original data."""
from __future__ import annotations

import csv
import json
import math
import os
import random
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .settings import atomic_json
from .storage import FIELDS, decimal, identifier, parse_time

PROFILES = [
    {"id": "demo-room", "name": "Raum · Test", "temperature": 20.5, "humidity": 55.0, "amplitude": 1.4},
    {"id": "demo-outside", "name": "Außen · Test", "temperature": 8.0, "humidity": 78.0, "amplitude": 4.0},
    {"id": "demo-corner", "name": "Kühle Messstelle · Test", "temperature": 17.5, "humidity": 69.0, "amplitude": 1.0},
]
SCENARIOS = {"daily": "Tagesgang", "humidity": "Feuchtespitzen", "ventilation": "Lüftung", "gaps": "Datenlücken"}


def validate_options(options):
    if not isinstance(options, dict) or set(options) - {"days", "interval_minutes", "seed", "scenario", "end"}:
        raise ValueError("Unbekannte Generatoroptionen.")
    result = {"days": 7, "interval_minutes": 5, "seed": 42, "scenario": "humidity", **options}
    for key, low, high in (("days", 1, 90), ("interval_minutes", 1, 60), ("seed", 0, 2147483647)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f"{key}: ganze Zahl von {low} bis {high} erforderlich.")
    if result["scenario"] not in SCENARIOS:
        raise ValueError("Unbekanntes Szenario.")
    if result["days"] * 1440 // result["interval_minutes"] > 80000:
        raise ValueError("Maximal 80.000 Messwerte je Testmessstelle. Intervall erhöhen.")
    end = parse_time(result["end"]) if result.get("end") else datetime.now(timezone.utc)
    result["end"] = end.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()
    return result


def load_profiles(path):
    if not path.exists():
        return PROFILES
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list) or not 1 <= len(values) <= 3:
        raise ValueError("Lokale Vorlage benötigt ein bis drei Profile.")
    ids = set()
    for value in values:
        if not isinstance(value, dict) or set(value) != set(PROFILES[0]):
            raise ValueError("Ungültiges Vorlagenformat.")
        identifier(value["id"])
        if value["id"] in ids:
            raise ValueError("Doppelte Vorlagenkennung.")
        ids.add(value["id"])
        if not isinstance(value["name"], str) or not 1 <= len(value["name"]) <= 80:
            raise ValueError("Ungültiger Vorlagenname.")
        for key, low, high in (("temperature", -40, 60), ("humidity", 1, 100), ("amplitude", 0, 20)):
            number = value[key]
            if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError("Ungültige Klimavorlage.")
    return values


def generate(root: Path, options, profiles=None):
    options = validate_options(options)
    profiles = profiles if profiles is not None else PROFILES
    root.mkdir(parents=True, exist_ok=True)
    run = "demo-" + uuid.uuid4().hex[:12]
    staging = Path(tempfile.mkdtemp(prefix=".generating-", dir=root))
    manifest = {"schema_version": 1, "id": run, "source": "Simulation", "options": options,
                "created_at": datetime.now(timezone.utc).isoformat(), "loggers": [],
                "template": "local" if profiles != PROFILES else "synthetic"}
    end = parse_time(options["end"])
    start = end - timedelta(days=options["days"])
    step = timedelta(minutes=options["interval_minutes"])
    try:
        for profile_index, profile in enumerate(profiles):
            rng = random.Random(options["seed"] + profile_index * 1009)
            count, target, writer, stream = 0, None, None, None
            stamp = start
            try:
                while stamp <= end:
                    # Use local wall time for plausible daily patterns, UTC for identity.
                    local = stamp.astimezone(ZoneInfo("Europe/Berlin"))
                    hour = local.hour + local.minute / 60
                    phase = math.sin((hour - 8) * math.tau / 24)
                    t = profile["temperature"] + profile["amplitude"] * phase + rng.gauss(0, .12)
                    h = profile["humidity"] - 4 * phase + rng.gauss(0, .5)
                    if options["scenario"] == "humidity":
                        h += 21 * math.exp(-((hour - 7.5) / .8) ** 2) + 16 * math.exp(-((hour - 20) / 1.2) ** 2)
                    elif options["scenario"] == "ventilation" and 8 <= hour <= 9:
                        effect = math.sin((hour - 8) * math.pi)
                        t -= 3 * effect
                        h -= 12 * effect
                    skip = options["scenario"] == "gaps" and 11 <= hour < 14
                    if not skip:
                        month = stamp.strftime("%Y-%m")
                        if month != target:
                            if stream:
                                stream.flush()
                                os.fsync(stream.fileno())
                                stream.close()
                            folder = staging / profile["id"] / stamp.strftime("%Y")
                            folder.mkdir(parents=True, exist_ok=True)
                            stream = (folder / (month + ".csv")).open("w", encoding="utf-8", newline="")
                            writer = csv.DictWriter(stream, FIELDS, delimiter=";", lineterminator="\n")
                            writer.writeheader()
                            target = month
                        writer.writerow({"Schema": "1", "DatensatzID": f"{profile['id']}-{int(stamp.timestamp())}",
                                         "Zeitstempel": stamp.isoformat(), "Temperatur": decimal(t),
                                         "Feuchte": decimal(max(1, min(100, h))), "Batterie": "", "RSSI": "",
                                         "Quelle": "Simulation", "Messstelle": profile["id"], "Qualitaet": "SYNTHETISCH"})
                        count += 1
                    stamp += step
            finally:
                if stream and not stream.closed:
                    stream.flush()
                    os.fsync(stream.fileno())
                    stream.close()
            manifest["loggers"].append({"id": profile["id"], "name": profile["name"], "count": count})
        atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, root / run)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return manifest
    except BaseException:
        # Retain partial files for diagnosis. Hidden staging runs are never offered as complete.
        raise


def list_runs(root):
    if not root.exists():
        return []
    runs = []
    for path in root.glob("demo-*/manifest.json"):
        runs.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(runs, key=lambda run: run["created_at"], reverse=True)
