"""Append-only host-received BLE observations, isolated from simulations."""
import csv
import fcntl
import io
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .storage import FIELDS, decimal, identifier, parse_time, read_months

LIVE_FIELDS = FIELDS + ["Batteriespannung", "Firmware", "Zeitbasis", "Aufzeichnungsstatus", "SpeicherVoll"]


class LiveStore:
    def __init__(self, root, sites=None):
        self.root = Path(root)
        self.sites=sites
        self.lock = threading.RLock()

    def append(self, reading, rssi, received_at):
        stamp = parse_time(received_at).astimezone(timezone.utc)
        logger = identifier("bt06-" + reading["device_id"])
        folder = self.root / logger / stamp.strftime("%Y")
        assignment=self.sites.resolve(logger,stamp.isoformat()) if self.sites else None
        row = {"Schema": "2", "DatensatzID": uuid.uuid4().hex, "Zeitstempel": stamp.isoformat(),
               "Temperatur": decimal(reading["temperature_c"]) if reading["temperature_c"] is not None else "",
               "Feuchte": decimal(reading["humidity_pct"]) if reading["humidity_pct"] is not None else "",
               "Batterie": "", "RSSI": str(rssi), "Quelle": "BLE-Advertising", "Messstelle": assignment["site_id"] if assignment else logger,
               "Qualitaet": reading["quality"], "Batteriespannung": decimal(reading["voltage_v"]),
               "Firmware": reading["firmware"], "Zeitbasis": "Host-Empfang",
               "Aufzeichnungsstatus": reading["recording"], "SpeicherVoll": "1" if reading["memory_full"] else "0"}
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, LIVE_FIELDS, delimiter=";", lineterminator="\n")
        writer.writerow(row)
        path = folder / (stamp.strftime("%Y-%m") + ".csv")
        with self.lock:
            folder.mkdir(parents=True, exist_ok=True)
            with path.open("a+b") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                if size:
                    stream.seek(0)
                    header = stream.readline().decode("utf-8").rstrip("\r\n")
                    if header != ";".join(LIVE_FIELDS):
                        raise ValueError("Live-CSV-Schemafehler; Originaldatei unverändert.")
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) != b"\n":
                        raise ValueError("Unvollständige Live-CSV-Zeile. Aufzeichnung gesperrt; Originaldatei erhalten.")
                else:
                    stream.write((";".join(LIVE_FIELDS) + "\n").encode("utf-8"))
                stream.seek(0, os.SEEK_END)
                stream.write(content.getvalue().encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            if not size:
                for directory in (folder, folder.parent, self.root):
                    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
        return row

    def rows(self, logger, start=None, end=None):
        folder = self.root / identifier(logger)
        with self.lock:
            # An empty selected logger is a legitimate state before first reception.
            yield from read_months(folder, start, end, fields=LIVE_FIELDS)

    def latest(self, logger):
        with self.lock:
            files = sorted((self.root / identifier(logger)).glob("*/*.csv"))
            if not files:
                return None
            with files[-1].open("rb") as stream:
                header = stream.readline().decode("utf-8").rstrip("\r\n")
                if header != ";".join(LIVE_FIELDS):
                    raise ValueError("Live-CSV-Schemafehler.")
                start = stream.tell()
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                if size == start:
                    return None
                stream.seek(max(start, size - 65536))
                tail = stream.read()
                if not tail.endswith(b"\n"):
                    raise ValueError("Unvollständige Live-CSV-Zeile; Original erhalten.")
                line = tail.splitlines()[-1].decode("utf-8")
                rows = list(csv.DictReader(io.StringIO(header + "\n" + line + "\n"), delimiter=";"))
                if len(rows) != 1 or None in rows[0] or any(v is None for v in rows[0].values()):
                    raise ValueError("Beschädigte Live-CSV-Zeile.")
                parse_time(rows[0]["Zeitstempel"])
                return rows[0]
