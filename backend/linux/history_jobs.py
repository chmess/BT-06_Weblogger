"""Serialized manual and opt-in automatic sync; restore host reception on every exit."""
import asyncio
import threading
from copy import deepcopy
from datetime import datetime, timezone

from backend.common.bt06_gatt import ProtocolError
from .ble_jobs import BusyError
from .history_reader import retrieve
from .settings_reader import retrieve_settings


class HistoryJobs:
    def __init__(self, receiver, store, settings_store=None):
        self.receiver, self.store = receiver, store
        self.settings_store = settings_store
        self.lock = threading.RLock()
        self.worker = None
        self.loop = self.task = None
        self.operation = None
        self.closing = False
        self.value = {'state': 'idle', 'phase': None, 'received': 0, 'expected': None, 'result': None, 'error': None, 'resume_error': None}

    def status(self):
        with self.lock:
            return deepcopy(self.value)

    def busy(self):
        return self.status()['state'] == 'running'

    def start(self, options, *, automatic=False, on_complete=None):
        if not isinstance(options, dict) or set(options) - {'mode'} or options.get('mode', 'full') not in ('full', 'incremental', 'settings'):
            raise ValueError('Leseauftrag erwartet mode=full, incremental oder settings.')
        if options.get('mode') == 'settings' and self.settings_store is None:
            raise ValueError('Geräteeinstellungsablage nicht eingerichtet.')
        config = self.receiver.status()['config']
        self.receiver.validate(config)
        if config['device'] is None:
            raise ValueError('Zuerst einen verifizierten BT06 für den Liveempfang auswählen.')
        if automatic and options.get('mode') != 'incremental':
            raise ValueError('Automatische Aufträge dürfen nur neue Werte nachladen.')
        return self._launch(config, options.get('mode', 'full'), automatic, on_complete)

    def start_task(self, mode, operation):
        """Internal configuration workflow only, never dispatched from /api/sync."""
        if mode not in ('configuration_prepare', 'configuration_write') or not callable(operation):
            raise ValueError('Unbekannter Konfigurationsauftrag.')
        config = self.receiver.status()['config']
        self.receiver.validate(config)
        if config['device'] is None:
            raise ValueError('Zuerst einen verifizierten BT06 auswählen.')
        return self._launch(config, mode, False, None, operation)

    def _launch(self, config, mode, automatic, on_complete, operation=None):
        with self.lock:
            if self.closing or self.busy():
                raise BusyError('Historienauftrag läuft bereits oder Anwendung wird beendet.')
            self.value = {'state': 'running', 'phase': 'pausing_host', 'received': 0, 'expected': None,
                          'result': None, 'error': None, 'resume_error': None,
                          'mode': mode,
                          'trigger': 'automatic' if automatic else 'manual',
                          'started_at': datetime.now(timezone.utc).isoformat()}
            self.operation = operation
            self.worker = threading.Thread(target=self._run, args=(deepcopy(config), mode, automatic, on_complete), name='bt06-history')
            try:
                self.worker.start()
            except BaseException:
                self.value.update(state='error', error='Historienauftrag konnte nicht starten.')
                self.operation = None
                raise
        return self.status()

    def _progress(self, phase, **values):
        with self.lock:
            self.value.update(phase=phase, **values)

    async def _read(self, config, base, automatic, mode):
        with self.lock:
            self.loop = asyncio.get_running_loop()
            self.task = asyncio.current_task()
            if self.closing:
                raise asyncio.CancelledError()
        if self.operation:
            return await asyncio.wait_for(self.operation(config, self._progress), 300)
        operation = (retrieve_settings(config, self._progress) if mode == 'settings'
                     else retrieve(config, self._progress, base=base, automatic=automatic))
        return await asyncio.wait_for(operation, 70 if automatic else 180)

    def _run(self, config, mode, automatic, on_complete):
        acquired = False
        paused = False
        try:
            base = self.store.incremental_base('bt06-' + config['device']['id']) if mode == 'incremental' else None
            if automatic and base is None:
                raise ProtocolError('Keine eindeutige geprüfte Nachladebasis. Manuell vollständig lesen.')
            self.receiver.stop(persist=False)
            paused = True
            acquired = self.receiver.radio_lock.acquire(blocking=False)
            if not acquired:
                raise BusyError('Bluetooth ist noch belegt. Historienlesen später erneut starten.')
            transfer = asyncio.run(self._read(config, base, automatic, mode))
            if self.operation:
                result = transfer
            else:
                self._progress('saving')
                result = (self.settings_store.save(config['device']['id'], transfer) if mode == 'settings'
                          else self.store.publish(config['device']['id'], **transfer))
            with self.lock:
                self.value.update(result=result)
        except (Exception, asyncio.CancelledError) as exc:
            if isinstance(exc, ProtocolError):
                message = str(exc)
            elif isinstance(exc, TimeoutError):
                message = ('Automatischer Verbindungsversuch ohne Tastendruck hat das Zeitlimit erreicht. Manuellen Verbindungsmodus prüfen.' if automatic
                           else 'Bluetooth-Zeitlimit erreicht. Verbindungsfenster per kurzem START/STOP prüfen und erneut lesen. Kein vollständiger Leseauftrag bestätigt.')
            elif isinstance(exc, (ValueError, BusyError, RuntimeError)):
                message = str(exc) if isinstance(exc, BusyError) else 'Historienlesen fehlgeschlagen. Geräteauswahl, Verbindung und Format prüfen; bisherige Daten erhalten.'
            elif isinstance(exc, OSError):
                message = 'Historie nicht dauerhaft gespeichert. Speicherplatz, Dateirechte und CSV prüfen; bisherige Daten erhalten.'
            elif isinstance(exc, asyncio.CancelledError):
                message = 'Historienlesen beim Beenden abgebrochen; bisherige Daten erhalten.'
            else:
                message = 'Historienlesen fehlgeschlagen. Bleak/BlueZ prüfen; bisherige Daten erhalten.'
            if mode == 'configuration_write':
                message = 'Geräteänderung nicht vollständig bestätigt. Gerätezustand neu lesen; nicht automatisch wiederholen. ' + message
            with self.lock:
                self.value.update(error=message)
        finally:
            if acquired:
                self.receiver.radio_lock.release()
            with self.lock:
                self.loop = self.task = None
                self.operation = None
                closing = self.closing
            if paused and config['enabled'] and not closing:
                try:
                    self.receiver.start()
                except Exception:
                    with self.lock:
                        self.value['resume_error'] = 'Liveempfang konnte nicht wieder starten. Unter Logger / Bluetooth erneut aktivieren.'
            with self.lock:
                self.value.update(state='error' if self.value['error'] else 'done', phase='finished')
                completion = deepcopy(self.value)
            if on_complete:
                # Scheduler persistence failures must not corrupt the finished
                # transfer or prevent receiver recovery.
                try:
                    on_complete(completion)
                except Exception:
                    pass

    def close(self):
        with self.lock:
            self.closing = True
            if self.loop and self.task:
                try:
                    self.loop.call_soon_threadsafe(self.task.cancel)
                except RuntimeError:
                    pass
            worker = self.worker
        if worker:
            worker.join(timeout=25)
