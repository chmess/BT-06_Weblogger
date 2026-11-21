"""Manual serialized history sync, with host-receiver restoration on every exit."""
import asyncio
import threading
from copy import deepcopy
from datetime import datetime, timezone

from backend.common.bt06_gatt import ProtocolError
from .ble_jobs import BusyError
from .history_reader import retrieve


class HistoryJobs:
    def __init__(self, receiver, store):
        self.receiver, self.store = receiver, store
        self.lock = threading.RLock()
        self.worker = None
        self.loop = self.task = None
        self.closing = False
        self.value = {'state': 'idle', 'phase': None, 'received': 0, 'expected': None, 'result': None, 'error': None, 'resume_error': None}

    def status(self):
        with self.lock:
            return deepcopy(self.value)

    def busy(self):
        return self.status()['state'] == 'running'

    def start(self, options):
        if not isinstance(options, dict) or set(options) - {'mode'} or options.get('mode', 'full') not in ('full', 'incremental'):
            raise ValueError('Historienlesen erwartet mode=full oder incremental; Standard ist vollständig.')
        config = self.receiver.status()['config']
        self.receiver.validate(config)
        if config['device'] is None:
            raise ValueError('Zuerst einen verifizierten BT06 für den Liveempfang auswählen.')
        with self.lock:
            if self.closing or self.busy():
                raise BusyError('Historienauftrag läuft bereits oder Anwendung wird beendet.')
            self.value = {'state': 'running', 'phase': 'pausing_host', 'received': 0, 'expected': None,
                          'result': None, 'error': None, 'resume_error': None,
                          'mode': options.get('mode', 'full'),
                          'started_at': datetime.now(timezone.utc).isoformat()}
            self.worker = threading.Thread(target=self._run, args=(deepcopy(config), options.get('mode', 'full')), name='bt06-history')
            try:
                self.worker.start()
            except BaseException:
                self.value.update(state='error', error='Historienauftrag konnte nicht starten.')
                raise
        return self.status()

    def _progress(self, phase, **values):
        with self.lock:
            self.value.update(phase=phase, **values)

    async def _read(self, config, base):
        with self.lock:
            self.loop = asyncio.get_running_loop()
            self.task = asyncio.current_task()
            if self.closing:
                raise asyncio.CancelledError()
        return await asyncio.wait_for(retrieve(config, self._progress, base=base), 180)

    def _run(self, config, mode):
        acquired = False
        paused = False
        try:
            base = self.store.incremental_base('bt06-' + config['device']['id']) if mode == 'incremental' else None
            self.receiver.stop(persist=False)
            paused = True
            acquired = self.receiver.radio_lock.acquire(blocking=False)
            if not acquired:
                raise BusyError('Bluetooth ist noch belegt. Historienlesen später erneut starten.')
            transfer = asyncio.run(self._read(config, base))
            self._progress('saving')
            result = self.store.publish(config['device']['id'], **transfer)
            with self.lock:
                self.value.update(result=result)
        except (Exception, asyncio.CancelledError) as exc:
            if isinstance(exc, ProtocolError):
                message = str(exc)
            elif isinstance(exc, TimeoutError):
                message = 'Bluetooth-Zeitlimit erreicht. Verbindungsfenster per kurzem START/STOP prüfen und erneut lesen. Kein vollständiger Import bestätigt.'
            elif isinstance(exc, (ValueError, BusyError, RuntimeError)):
                message = str(exc) if isinstance(exc, BusyError) else 'Historienlesen fehlgeschlagen. Geräteauswahl, Verbindung und Format prüfen; bisherige Daten erhalten.'
            elif isinstance(exc, OSError):
                message = 'Historie nicht dauerhaft gespeichert. Speicherplatz, Dateirechte und CSV prüfen; bisherige Daten erhalten.'
            elif isinstance(exc, asyncio.CancelledError):
                message = 'Historienlesen beim Beenden abgebrochen; bisherige Daten erhalten.'
            else:
                message = 'Historienlesen fehlgeschlagen. Bleak/BlueZ prüfen; bisherige Daten erhalten.'
            with self.lock:
                self.value.update(error=message)
        finally:
            if acquired:
                self.receiver.radio_lock.release()
            with self.lock:
                self.loop = self.task = None
                closing = self.closing
            if paused and config['enabled'] and not closing:
                try:
                    self.receiver.start()
                except Exception:
                    with self.lock:
                        self.value['resume_error'] = 'Liveempfang konnte nicht wieder starten. Unter Logger / Bluetooth erneut aktivieren.'
            with self.lock:
                self.value.update(state='error' if self.value['error'] else 'done', phase='finished')

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
