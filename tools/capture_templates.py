#!/usr/bin/env python3
"""Read ioBroker climate templates into private/, without retaining raw history."""
import argparse
import json
import math
import statistics
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.common.settings import atomic_json


def fetch(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)


def clean_number(value):
    if isinstance(value, dict):
        value = value.get("val")
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)


def capture(base, sources, output):
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username:
        raise ValueError("HTTP(S)-Basisadresse ohne eingebettete Zugangsdaten erforderlich.")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 3 or not all(isinstance(s, str) and s.startswith("zigbee.") for s in sources):
        raise ValueError("Ein bis drei Zigbee-Gerätekennungen erforderlich.")
    base = base.rstrip("/") + "/"
    profiles, provenance = [], []
    end_ms = int(time.time() * 1000)
    for index, source in enumerate(sources, 1):
        readings, stats = {}, {}
        for field, low, high in (("temperature", -40, 60), ("humidity", 1, 100)):
            state_id = source + "." + field
            state = fetch(base + "state/" + urllib.parse.quote(state_id, safe="."))
            current = clean_number(state)
            values = []
            history_error = None
            query = urllib.parse.urlencode({"start": end_ms - 7 * 86400000, "end": end_ms, "count": 336, "aggregate": "average", "ignoreNull": "true", "removeBorderValues": "true"})
            try:
                history = fetch(base + "getHistory/" + urllib.parse.quote(state_id, safe="") + "?" + query)
                if isinstance(history, list):
                    values = [v for item in history if (v := clean_number(item)) is not None and low <= v <= high]
            except (OSError, ValueError) as exc:
                history_error = type(exc).__name__
            if values:
                readings[field] = statistics.median(values)
            elif current is not None and low <= current <= high:
                readings[field] = current
            else:
                raise ValueError(f"Vorlage {index}: {field} liefert keine gültigen Daten. Keine Profile geschrieben.")
            stats[field] = {"history_points": len(values), "basis": "seven_day_median" if values else "current_state", "state_ts": state.get("ts") if isinstance(state, dict) else None, "history_error": history_error}
            if field == "temperature":
                amplitude = min(10, max(.3, (max(values) - min(values)) / 2)) if len(values) >= 2 else 1.2
        profiles.append({"id": f"demo-template-{index}", "name": f"Klimavorlage {index} · Test", "temperature": round(readings["temperature"], 2), "humidity": round(readings["humidity"], 2), "amplitude": round(amplitude, 2)})
        provenance.append({"source": source, "statistics": stats})
    # Only aggregate parameters feed the generator. Source identifiers remain private.
    atomic_json(output / "template-sources.json", {"captured_at_ms": end_ms, "sources": provenance})
    atomic_json(output / "profiles.json", profiles)
    return {"profiles": len(profiles), "output": str(output), "note": "Nur aggregierte Vorlagen, keine Rohhistorien. Ausschließlich lesende HTTP-Aufrufe."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--sources", type=Path, required=True, help="Private JSON-Liste der Gerätekennungen")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "private")
    args = parser.parse_args()
    try:
        result = capture(args.base, json.loads(args.sources.read_text()), args.output)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        # Do not echo server URLs or response bodies that might contain credentials.
        print(f"Vorlagen konnten nicht eingelesen werden ({type(exc).__name__}). Vorhandene Profile bleiben erhalten.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
