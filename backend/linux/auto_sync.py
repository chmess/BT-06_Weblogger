"""Opt-in bounded sync scheduling inside the existing application process."""
import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone

from backend.common.settings import atomic_json
from backend.common.storage import parse_time
from .ble_jobs import BusyError
from .receiver import Receiver

DEFAULT = {'schema_version': 1, 'enabled': False, 'interval_minutes': 30, 'target': None}


def target_of(config):
    device = config['device']
    if device is None:
        return None
    return {'id': device['id'], 'address': device['address'].upper(), 'firmware': device['firmware'], 'adapter': config['adapter']}


class AutoSync:
    def __init__(self, path, receiver, jobs, bluetooth, control_lock, monotonic=time.monotonic, wall=time.time):
        self.path = path
        self.state_path = path.with_name('autosync-state.json')
        self.receiver, self.jobs, self.bluetooth = receiver, jobs, bluetooth
        self.control_lock = control_lock
        self.monotonic, self.wall = monotonic, wall
        self.lock = threading.RLock()
        self.wakeup = threading.Event()
        self.worker = None
        self.closing = False
        self.config = json.loads(path.read_text()) if path.exists() else deepcopy(DEFAULT)
        self.validate(self.config)
        self.state = {'schema_version': 1, 'failures': 0, 'last_attempt_at': None, 'last_success_at': None,
                      'next_attempt_at': None, 'last_error': None}
        if self.state_path.exists():
            saved = json.loads(self.state_path.read_text())
            if (not isinstance(saved, dict) or set(saved) != set(self.state) or saved['schema_version'] != 1
                    or type(saved['failures']) is not int or not 0 <= saved['failures'] <= 10
                    or saved['last_error'] is not None and not isinstance(saved['last_error'], str)):
                raise ValueError('Ungültiger Auto-Sync-Zustand; Originaldatei erhalten.')
            for key in ('last_attempt_at', 'last_success_at', 'next_attempt_at'):
                if saved[key] is not None:
                    parse_time(saved[key])
            self.state = saved
        self.active = False
        self.wait_reason = None
        self.persistence_error = None
        interval = self.config['interval_minutes'] * 60
        remaining = (parse_time(self.state['next_attempt_at']).timestamp() - self.wall() if self.state['next_attempt_at']
                     else min(interval * 2 ** self.state['failures'], max(interval, 21600)))
        self.due = self.monotonic() + max(0, min(max(interval, 21600), remaining)) if self.config['enabled'] else None

    @staticmethod
    def validate(config):
        if (not isinstance(config, dict) or set(config) != set(DEFAULT) or config['schema_version'] != 1
                or type(config['enabled']) is not bool or type(config['interval_minutes']) is not int
                or not 15 <= config['interval_minutes'] <= 1440):
            raise ValueError('Auto-Sync benötigt Aktivierung und ein Intervall von 15 bis 1440 Minuten.')
        target = config['target']
        if target is not None:
            if not isinstance(target, dict) or set(target) != {'id', 'address', 'firmware', 'adapter'}:
                raise ValueError('Ungültiges Auto-Sync-Ziel.')
            Receiver.validate({'schema_version': 1, 'enabled': True, 'adapter': target['adapter'], 'save_interval_seconds': 60,
                               'device': {'id': target['id'], 'address': target['address'], 'firmware': target['firmware'], 'name': ''}})
        if config['enabled'] and target is None:
            raise ValueError('Auto-Sync benötigt einen ausdrücklich gewählten Logger.')

    def _stamp(self, seconds):
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat()

    def _persist(self):
        try:
            atomic_json(self.state_path, self.state)
            self.persistence_error = None
        except OSError:
            self.persistence_error = 'Auto-Sync-Zustand konnte nicht gespeichert werden; weitere automatische Versuche pausiert.'
            self.due = None

    def status(self):
        with self.lock:
            result = {'config': deepcopy(self.config), **deepcopy(self.state), 'active': self.active,
                      'wait_reason': self.wait_reason, 'persistence_error': self.persistence_error}
            result['next_in_seconds'] = max(0, round(self.due - self.monotonic())) if self.due is not None else None
            return result

    def configure(self, options):
        if not isinstance(options, dict) or set(options) != {'enabled', 'interval_minutes'}:
            raise ValueError('Auto-Sync erwartet enabled und interval_minutes.')
        selected = self.receiver.status()['config']
        clean = {'schema_version': 1, **options, 'target': target_of(selected)}
        self.validate(clean)
        if clean['enabled'] and not selected['enabled']:
            raise ValueError('Zuerst den Liveempfang für den ausgewählten Logger aktivieren.')
        with self.control_lock, self.lock:
            if self.closing:
                raise BusyError('Anwendung wird beendet.')
            atomic_json(self.path, clean)
            self.config = clean
            self.wait_reason = None
            self.state['failures'] = 0
            self.state['last_error'] = None
            self.persistence_error = None
            self._schedule(clean['interval_minutes'] * 60 if clean['enabled'] else None)
            self.wakeup.set()
        return self.status()

    def _schedule(self, delay):
        self.due = self.monotonic() + delay if delay is not None else None
        self.state['next_attempt_at'] = self._stamp(self.wall() + delay) if delay is not None else None
        self._persist()

    def _complete(self, outcome):
        with self.control_lock, self.lock:
            self.active = False
            failed = outcome['state'] != 'done' or bool(outcome.get('resume_error'))
            self.state['failures'] = min(10, self.state['failures'] + 1) if failed else 0
            self.state['last_error'] = outcome.get('error') or outcome.get('resume_error') if failed else None
            if not failed:
                self.state['last_success_at'] = self._stamp(self.wall())
            base = self.config['interval_minutes'] * 60
            delay = min(base * 2 ** self.state['failures'], max(base, 21600))
            self._schedule(delay if self.config['enabled'] and not self.closing else None)
            self.wakeup.set()

    def tick(self):
        # Same ordering as API controls: control lock first, scheduler lock second.
        if not self.control_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                if self.closing or not self.config['enabled'] or self.active or self.due is None or self.monotonic() < self.due:
                    return
                live = self.receiver.status()
                if target_of(live['config']) != self.config['target']:
                    self.wait_reason = 'Loggerauswahl geändert. Auto-Sync für das gewünschte Gerät erneut speichern.'
                    return
                if not live['config']['enabled'] or live['state'] != 'receiving':
                    self.wait_reason = 'Liveempfang pausiert oder noch nicht bereit.'
                    return
                if not live['fresh']:
                    self.wait_reason = 'Kein frisches Advertising des ausgewählten Loggers.'
                    return
                if self.jobs.busy() or self.bluetooth.status()['state'] == 'running':
                    self.wait_reason = 'Bluetooth ist durch einen anderen Auftrag belegt.'
                    return
                self.wait_reason = None
                self.active = True
                self.state['last_attempt_at'] = self._stamp(self.wall())
                self.state['next_attempt_at'] = None
                self.due = None
                self._persist()
                if self.persistence_error:
                    self.active = False
                    return
                try:
                    self.jobs.start({'mode': 'incremental'}, automatic=True, on_complete=self._complete)
                except (ValueError, RuntimeError, OSError):
                    self._complete({'state': 'error', 'error': 'Automatischer Auftrag konnte nicht gestartet werden.', 'resume_error': None})
        finally:
            self.control_lock.release()

    def start(self):
        with self.lock:
            if self.worker and self.worker.is_alive():
                return
            self.worker = threading.Thread(target=self._run, name='bt06-auto-sync')
            self.worker.start()

    def _run(self):
        while not self.closing:
            self.wakeup.wait(10)
            self.wakeup.clear()
            try:
                self.tick()
            except Exception:
                with self.lock:
                    self.persistence_error = 'Auto-Sync wegen internem Fehler pausiert; Einstellungen prüfen.'
                    self.due = None

    def close(self):
        with self.lock:
            self.closing = True
            self.wakeup.set()
            worker = self.worker
        if worker:
            worker.join(timeout=2)
