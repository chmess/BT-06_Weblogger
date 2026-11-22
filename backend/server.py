"""Loopback web app, synthetic tests and explicitly enabled BLE advertising."""
from __future__ import annotations

import json
import mimetypes
import secrets
import shutil
import threading
import time
from contextlib import nullcontext
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from backend import VERSION
from backend.common.settings import Settings
from backend.common.simulation import generate, list_runs, load_profiles
from backend.common.storage import chart_data, csv_text, identifier, rows_in_range
from backend.linux.ble_jobs import BluetoothJobs, BusyError
from backend.linux.receiver import Receiver
from backend.common.live_store import LiveStore, LIVE_FIELDS
from backend.common.history_store import HistoryStore, HISTORY_FIELDS
from backend.linux.history_jobs import HistoryJobs
from backend.linux.auto_sync import AutoSync
from backend.common.history_timezones import HistoryTimezones, ASSIGNED_FIELDS
from backend.common.device_settings import DeviceSettingsStore
from backend.common.settings_preview import settings_preview
from backend.linux.configuration import ConfigurationWorkflow
from backend.linux.recording import RecordingWorkflow


class Application:
    def __init__(self, root, base_path="", public_origin=None):
        self.root = Path(root)
        self.web = Path(__file__).resolve().parents[1] / "web"
        # Keep UI and backend from the same process start together during updates.
        self.assets = {str(path.relative_to(self.web)): path.read_bytes() for path in self.web.rglob("*") if path.is_file()}
        self.base_path = base_path.rstrip("/")
        if self.base_path and (not self.base_path.startswith("/") or any(c not in "/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in self.base_path)):
            raise ValueError("Ungültiger Basispfad.")
        self.settings = Settings(self.root / "config/settings.json")
        self.simulation = self.root / "simulation"
        self.csrf = secrets.token_urlsafe(32)
        self.started = time.monotonic()
        self.public_origins = tuple([public_origin] if isinstance(public_origin, str) else public_origin or [])
        for origin in self.public_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError("Public Origin muss eine HTTP(S)-Origin ohne Pfad sein.")
        self.generation_lock = threading.Lock()
        radio_lock = threading.Lock()
        self.bluetooth = BluetoothJobs(radio_lock)
        self.live_store = LiveStore(self.root / "data")
        self.receiver = Receiver(self.root / "config/receiver.json", self.live_store, radio_lock)
        self.control_lock = threading.RLock()
        self.history_store = HistoryStore(self.root / "data/history")
        self.device_settings = DeviceSettingsStore(self.root / "data/device-settings")
        self.sync = HistoryJobs(self.receiver, self.history_store, self.device_settings)
        self.configuration = ConfigurationWorkflow(self.receiver, self.sync, self.device_settings, self.history_store)
        self.recording = RecordingWorkflow(self.receiver,self.sync,self.device_settings,self.history_store,self.configuration)
        self.timezones = HistoryTimezones(self.root / "config/history-timezones.json", self.history_store)
        self.auto_sync = AutoSync(self.root / "config/autosync.json", self.receiver, self.sync, self.bluetooth, self.control_lock)

    def resume(self):
        if self.receiver.config["enabled"]:
            self.receiver.start()
        self.auto_sync.start()

    def close(self):
        self.auto_sync.close()
        self.sync.close()
        self.receiver.stop(persist=False)

    def loggers(self):
        ids = {p.name for p in (self.root / "data").glob("bt06-*") if p.is_dir()}
        config = self.receiver.status()["config"]
        if config["device"]:
            ids.add("bt06-" + config["device"]["id"])
        return [{"id": identifier(logger), "name": "BT06 " + logger.removeprefix("bt06-"),
                 "source": "BLE-Advertising", "interval_minutes": config["save_interval_seconds"] / 60}
                for logger in sorted(ids)]

    def status(self):
        live = self.receiver.status()
        sync = self.sync.status()
        syncing = sync["state"] == "running"
        return {"version": VERSION, "mode": "advertising" if live["config"]["enabled"] else "offline", "uptime_seconds": round(time.monotonic() - self.started),
                "ble": {"connected": syncing and sync["phase"] in ("reading_metadata", "reading_settings", "selecting_range", "full_fallback", "receiving", "stopping_logger", "writing_settings", "committing_settings", "verifying_settings", "reading_inventory", "starting_logger", "verifying_recording"),
                        "status": ("Aufzeichnungssteuerung · " if sync.get('mode','').startswith('recording_') else "Gerätekonfiguration · " if sync.get('mode', '').startswith('configuration_') else "Historienlesen · ") + sync["phase"] if syncing else "Advertising-Empfang " + live["state"] + " · keine GATT-Verbindung"},
                "free_bytes": shutil.disk_usage(self.root).free,
                "local_profiles": (self.root / "private/profiles.json").exists(),
                "limits": {"max_days": 90, "max_points_per_logger": 80000},
                "data_notice": "Echte BLE-Empfänge und synthetische Testdaten sind getrennt. Klimabewertung folgt gemäß Roadmap."}


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BT06/" + VERSION

        def log_message(self, format, *args):
            # Never put query strings, payloads or credentials in access logs.
            pass

        def valid_host(self):
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            allowed.update(urlsplit(origin).netloc for origin in app.public_origins)
            return host in allowed

        def send(self, status, payload, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def route(self):
            if not self.valid_host():
                self.send(403, {"error": "Host nicht freigegeben."})
                return None, None
            parsed = urlsplit(self.path)
            if app.base_path and parsed.path == app.base_path:
                self.send_response(308)
                self.send_header("Location", app.base_path + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None, None
            if not parsed.path.startswith(app.base_path + "/"):
                self.send(404, {"error": "Pfad nicht gefunden."})
                return None, None
            return parsed.path[len(app.base_path):], parse_qs(parsed.query, keep_blank_values=True)

        def do_GET(self):
            try:
                path, query = self.route()
                if path is None:
                    return
                if path == "/api/status":
                    self.send(200, app.status())
                elif path == "/api/session":
                    self.send(200, {"csrf_token": app.csrf})
                elif path == "/api/settings":
                    self.send(200, app.settings.get())
                elif path == "/api/settings/download":
                    self.send(200, app.settings.get(), filename="bt06-settings.json")
                elif path == "/api/runs":
                    self.send(200, {"runs": list_runs(app.simulation)})
                elif path == "/api/ble":
                    self.send(200, app.bluetooth.status())
                elif path == "/api/live":
                    self.send(200, app.receiver.status())
                elif path == "/api/loggers":
                    self.send(200, {"loggers": app.loggers()})
                elif path == "/api/sync":
                    self.send(200, app.sync.status())
                elif path == "/api/snapshots":
                    self.send(200, {"snapshots": app.history_store.snapshots()})
                elif path == "/api/series":
                    self.send(200, {"series": app.history_store.series()})
                elif path == "/api/autosync":
                    self.send(200, app.auto_sync.status())
                elif path == "/api/device-settings":
                    device = app.receiver.status()["config"]["device"]
                    self.send(200, {"settings": app.device_settings.latest(device["id"]) if device else None,
                                    "read_only": True, "selected": device is not None})
                elif path == "/api/device-settings/configuration":
                    self.send(200, app.configuration.status())
                elif path == "/api/recording":
                    self.send(200,app.recording.status())
                elif path == "/api/time-assignment":
                    if set(query) != {"logger", "snapshot"} or any(len(v) != 1 for v in query.values()):
                        raise ValueError("Zeitzuordnung benötigt genau logger und snapshot.")
                    self.send(200, app.timezones.info(query["logger"][0], query["snapshot"][0]))
                elif path in ("/api/history", "/api/export"):
                    allowed = {"source", "run", "logger", "start", "end", "snapshot", "time_basis"}
                    if set(query) - allowed or any(len(v) != 1 for v in query.values()):
                        raise ValueError("Ungültige Abfrageparameter.")
                    source = query.get("source", ["simulation"])[0]
                    basis = query.get("time_basis", ["original"])[0]
                    if basis not in ("original", "assigned") or "time_basis" in query and (source != "device" or path != "/api/export"):
                        raise ValueError("Zeitzuordnung ist nur für den zusätzlichen Historien-CSV-Export verfügbar.")
                    logger = identifier(query.get("logger", [""])[0])
                    start, end = query.get("start", [None])[0], query.get("end", [None])[0]
                    if source == "simulation":
                        if "snapshot" in query:
                            raise ValueError("Historienstand ist kein Testlauf.")
                        run = identifier(query.get("run", [""])[0])
                        runs = list_runs(app.simulation)
                        manifest = next((item for item in runs if item["id"] == run), None)
                        if not manifest or logger not in {item["id"] for item in manifest["loggers"]}:
                            raise ValueError("Unbekannter Testlauf oder Messstelle.")
                        rows = rows_in_range(app.simulation, run, logger, start, end)
                        interval, fields, label = manifest["options"]["interval_minutes"], None, "Simulation"
                    elif source == "live":
                        if "run" in query or "snapshot" in query or logger not in {item["id"] for item in app.loggers()}:
                            raise ValueError("Unbekannter echter Logger oder ungültige Abfrage.")
                        run = "ble"
                        rows = app.live_store.rows(logger, start, end)
                        interval = app.receiver.status()["config"]["save_interval_seconds"] / 60
                        fields, label = LIVE_FIELDS, "BLE-Advertising"
                    elif source == "device":
                        if "run" in query:
                            raise ValueError("Loggerhistorie ist kein Testlauf.")
                        snapshot = query.get("snapshot", [""])[0]
                        meta = app.history_store.metadata(logger, snapshot)
                        run = snapshot[:16]
                        interval = meta["interval_seconds"] / 60
                        rows = (app.history_store.filtered_rows(logger, snapshot, start, end) if path == "/api/export"
                                else app.history_store.chart_rows(logger, snapshot, start, end))
                        fields, label = HISTORY_FIELDS, "BT06-Historie"
                        if basis == "assigned":
                            rows = app.timezones.export_rows(logger, snapshot, start, end)
                            fields = HISTORY_FIELDS + ASSIGNED_FIELDS
                    else:
                        raise ValueError("Unbekannte Datenquelle.")
                    if path == "/api/export":
                        export = csv_text(rows, fields) if fields else csv_text(rows)
                        self.send(200, export.encode("utf-8-sig"), "text/csv; charset=utf-8", f"{run}_{logger}.csv")
                    else:
                        self.send(200, {"source": label, "clock_verified": source != "device",
                                        "axis_basis": "device_calendar" if source == "device" else "timestamp", **chart_data(rows, interval)})
                else:
                    assets = {"/": "index.html", "/css/app.css": "css/app.css", "/js/app.js": "js/app.js",
                              "/assets/favicon.svg": "assets/favicon.svg", "/favicon.ico": "assets/favicon.ico",
                              "/assets/echarts.min.js": "assets/echarts.min.js"}
                    target = assets.get(path)
                    if not target or target not in app.assets:
                        self.send(404, {"error": "Nicht gefunden."})
                    else:
                        mime = {".svg": "image/svg+xml", ".ico": "image/x-icon", ".js": "text/javascript; charset=utf-8",
                                ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8"}.get(Path(target).suffix)
                        self.send(200, app.assets[target], mime or mimetypes.guess_type(target)[0] or "application/octet-stream")
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.send(400, {"error": str(exc)})
            except OSError:
                self.send(503, {"error": "Dateizugriff fehlgeschlagen. Speicherplatz und Dateirechte prüfen."})

        def do_POST(self):
            try:
                path, _ = self.route()
                if path is None:
                    return
                origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
                origins.update(app.public_origins)
                if self.headers.get("Origin") not in origins or not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), app.csrf):
                    self.send(403, {"error": "Schreibzugriff benötigt gleiche Origin und Sitzungstoken."})
                    return
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    self.send(415, {"error": "JSON erforderlich."})
                    return
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("Transfer-Encoding nicht unterstützt.")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    self.send(413, {"error": "JSON muss zwischen 1 und 16.384 Bytes groß sein."})
                    return
                value = json.loads(self.rfile.read(length))
                controlled = path in {"/api/ble", "/api/live/start", "/api/live/stop", "/api/sync", "/api/autosync", "/api/device-settings/read", "/api/device-settings/preview", "/api/device-settings/prepare", "/api/device-settings/apply", "/api/device-settings/cancel", "/api/device-settings/verify", "/api/recording/prepare", "/api/recording/start", "/api/recording/cancel", "/api/recording/verify"}
                with app.control_lock if controlled else nullcontext():
                    if controlled and path != "/api/autosync" and app.sync.busy():
                        raise BusyError("Historienlesen läuft. Bluetooth-Steuerung nach Abschluss wieder verfügbar.")
                    if path == "/api/settings":
                        self.send(200, app.settings.save(value))
                    elif path == "/api/autosync":
                        self.send(200, app.auto_sync.configure(value))
                    elif path == "/api/time-assignment":
                        self.send(200, app.timezones.assign(value))
                    elif path == "/api/device-settings/preview":
                        config = app.receiver.status()['config']
                        device = config['device']
                        saved = app.device_settings.latest(device['id']) if device else None
                        self.send(200, settings_preview(config, saved, value))
                    elif path == "/api/device-settings/prepare":
                        if app.bluetooth.status()['state'] == 'running':
                            raise BusyError('Bluetooth-Diagnose läuft bereits.')
                        self.send(202, app.configuration.prepare(value))
                    elif path == "/api/device-settings/apply":
                        if app.bluetooth.status()['state'] == 'running':
                            raise BusyError('Bluetooth-Diagnose läuft bereits.')
                        self.send(202, app.configuration.apply(value))
                    elif path == "/api/device-settings/cancel":
                        self.send(200, app.configuration.cancel(value))
                    elif path == "/api/device-settings/verify":
                        if app.bluetooth.status()['state']=='running':
                            raise BusyError('Bluetooth-Diagnose läuft bereits.')
                        self.send(202,app.configuration.verify_last(value))
                    elif path in ('/api/recording/prepare','/api/recording/start','/api/recording/cancel','/api/recording/verify'):
                        if app.bluetooth.status()['state']=='running':raise BusyError('Bluetooth-Diagnose läuft bereits.')
                        command={'/api/recording/prepare':app.recording.prepare,'/api/recording/start':app.recording.apply,
                                 '/api/recording/cancel':app.recording.cancel,'/api/recording/verify':app.recording.verify}[path]
                        self.send(200 if path.endswith('/cancel') else 202,command(value))
                    elif path == "/api/device-settings/read":
                        if value != {}:
                            raise ValueError("Geräteeinstellungen lesen benötigt ein leeres JSON-Objekt.")
                        if app.bluetooth.status()["state"] == "running":
                            raise BusyError("Bluetooth-Diagnose läuft bereits.")
                        self.send(202, app.sync.start({"mode": "settings"}))
                    elif path == "/api/sync":
                        if app.bluetooth.status()["state"] == "running":
                            raise BusyError("Bluetooth-Diagnose läuft bereits.")
                        self.send(202, app.sync.start(value))
                    elif path == "/api/ble":
                        self.send(202, app.bluetooth.start(value))
                    elif path == "/api/live/start":
                        if not isinstance(value, dict) or set(value) - {"device", "adapter", "save_interval_seconds"}:
                            raise ValueError("Ungültige Empfangsoptionen.")
                        if not value:
                            self.send(202, app.receiver.start())
                        else:
                            candidate = app.bluetooth.candidate(value.get("device"), value.get("adapter", "hci0"))
                            if not candidate or not candidate.get("bt06"):
                                raise ValueError("Kein verifiziertes BT06-Advertising-Format ausgewählt.")
                            reading = candidate["bt06"]
                            config = {"schema_version": 1, "enabled": True, "adapter": value.get("adapter", "hci0"),
                                      "save_interval_seconds": value.get("save_interval_seconds", 60),
                                      "device": {"address": candidate["address"], "id": reading["device_id"],
                                                 "firmware": reading["firmware"], "name": (candidate.get("name") or "BT06")[:80]}}
                            self.send(202, app.receiver.start(config))
                    elif path == "/api/live/stop":
                        if value != {}:
                            raise ValueError("Stop benötigt ein leeres JSON-Objekt.")
                        self.send(200, app.receiver.stop())
                    elif path == "/api/simulation":
                        if not app.generation_lock.acquire(blocking=False):
                            self.send(409, {"error": "Ein Generatorlauf ist bereits aktiv."})
                            return
                        try:
                            profiles = load_profiles(app.root / "private/profiles.json")
                            manifest = generate(app.simulation, value, profiles)
                        finally:
                            app.generation_lock.release()
                        self.send(201, manifest)
                    else:
                        self.send(404, {"error": "Nicht gefunden."})
            except BusyError as exc:
                self.send(409, {"error": str(exc)})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.send(400, {"error": str(exc)})
            except OSError:
                self.send(503, {"error": "Speichern fehlgeschlagen. Speicherplatz und Dateirechte prüfen."})

    return Handler


def make_server(app, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(app))
    server.daemon_threads = False
    return server
