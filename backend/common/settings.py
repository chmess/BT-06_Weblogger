"""Validated local settings. No device settings or secrets are accepted."""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULTS = {
    "schema_version": 1,
    "theme": "dark",
    "timezone": "Europe/Berlin",
    "refresh_seconds": 15,
    "default_hours": 24,
    "humidity_warning": 70,
    "humidity_critical": 80,
}


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Unvollständige oder unbekannte Einstellungsfelder.")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unbekannte Einstellungsversion.")
    if value["theme"] not in ("dark", "light"):
        raise ValueError("Theme muss dark oder light sein.")
    if not isinstance(value["timezone"], str):
        raise ValueError("Ungültige Zeitzone.")
    try:
        ZoneInfo(value["timezone"])
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("Unbekannte Zeitzone.") from None
    limits = {"refresh_seconds": (5, 300), "default_hours": (1, 2160),
              "humidity_warning": (1, 99), "humidity_critical": (2, 100)}
    for field, (low, high) in limits.items():
        v = value[field]
        if type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError(f"{field}: zulässiger Bereich {low}–{high}.")
    if value["humidity_warning"] >= value["humidity_critical"]:
        raise ValueError("Warnschwelle muss unter der kritischen Schwelle liegen.")
    return deepcopy(value)


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Settings:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        # Invalid files are reported; never silently replaced with defaults.
        self.value = validate_settings(json.loads(self.path.read_text(encoding="utf-8"))) if self.path.exists() else deepcopy(DEFAULTS)

    def get(self):
        with self.lock:
            return deepcopy(self.value)

    def save(self, value):
        clean = validate_settings(value)
        with self.lock:
            atomic_json(self.path, clean)
            self.value = clean
        return self.get()
