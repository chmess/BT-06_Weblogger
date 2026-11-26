"""Explicit two-step configuration, full history first; never reset or restart."""
import asyncio
import csv
import json
import os
import re
import hashlib
import secrets
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from backend.common.bt06_gatt import SERVICE_UUID, TX_UUID, RX_UUID, ProtocolError
from backend.common.device_settings import decode_settings, settings_capture
from backend.common.history_store import sync_directory
from backend.common.settings import atomic_json
from backend.common.settings_commands import STOP, SAVE, FINISH, configuration_frames, configuration_reply
from backend.common.settings_preview import settings_preview
from backend.common.storage import parse_time
from .history_reader import known_device, retrieve
from .settings_reader import retrieve_settings


def binding(config):
    device = config['device']
    if not device:
        return None
    return (config['adapter'], device['address'].lower(), device['id'], device['firmware'])


def complete(observation, *, after_commit=False):
    decoded = decode_settings(observation['payloads'])
    if observation['read_errors'] or decoded['decode_errors'] or len(observation['payloads']) != 8:
        raise ProtocolError('Geräteeinstellungen nicht vollständig geprüft; Schreiben gesperrt.')
    if after_commit and decoded['values'].get('status_variant')=='zero_summary':
        return decoded['values']
    if decoded['values'].get('recording_code') not in (1, 2, 4, 5, 16):
        raise ProtocolError('Aufzeichnungszustand unbekannt oder Startverzögerung aktiv; Schreiben gesperrt.')
    return decoded['values']


def same_configuration(before, after):
    keys = set(before) | set(after)
    if any(before.get(key) != after.get(key) for key in keys - {'device_clock', 'log_status'}):
        raise ProtocolError('Geräteeinstellungen haben sich geändert. Neu auslesen, Entwurf erneut prüfen und vorbereiten.')


class ChangeJournal:
    """Durable intent before every command; a crash never authorizes a retry."""
    def __init__(self, root, context):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        sync_directory(root.parent)
        self.id = uuid.uuid4().hex
        self.report = {'id': self.id, 'status': 'checking', 'may_have_changed': False,
                       'device_id': context['preview']['device_id'], 'changes': context['preview']['changes'],
                       'histories': [], 'started_at': datetime.now(timezone.utc).isoformat()}
        self.path = root / (self.id + '.json')
        fd = os.open(root / (self.id + '.csv'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.capture = os.fdopen(fd, 'w', encoding='utf-8', newline='')
        self.writer = csv.writer(self.capture, delimiter=';', lineterminator='\n')
        self.writer.writerow(['Hostzeit', 'Phase', 'Richtung', 'DatenHex'])
        self.capture.flush(); os.fsync(self.capture.fileno())
        try:
            self.save()
        except BaseException:
            self.capture.close()
            raise

    def save(self, **values):
        self.report.update(values)
        atomic_json(self.path, self.report)
        atomic_json(self.root / 'latest.json', self.report)

    def note(self, phase, direction, raw):
        self.writer.writerow([datetime.now(timezone.utc).isoformat(), phase, direction, raw.hex()])
        self.capture.flush(); os.fsync(self.capture.fileno())

    def history(self, result):
        self.report['histories'].append({'logger': result['logger'], 'id': result['id'], 'count': result['count'],
                                          'scope': result['last_transfer_scope']})
        self.save()

    def close(self):
        self.capture.close()


class ConfigurationWorkflow:
    def __init__(self, receiver, jobs, settings_store, history_store):
        self.receiver, self.jobs = receiver, jobs
        self.settings_store, self.history_store = settings_store, history_store
        self.root = settings_store.root / 'changes'
        self.lock = threading.RLock()
        self.pending = None

    def status(self):
        with self.lock:
            pending = self.pending
            if pending and (time.monotonic() >= pending['deadline']
                            or binding(self.receiver.status()['config']) != pending['binding']):
                self.pending = pending = None
            if pending:
                latest = self.settings_store.latest(pending['preview']['device_id'])
                if not latest or latest['capture'] != pending['preview']['base_capture']:
                    self.pending = pending = None
            prepared = deepcopy(pending['public']) if pending else None
            if prepared:
                prepared['expires_in_seconds'] = max(0, int(pending['deadline'] - time.monotonic()))
            path = self.root / 'latest.json'
            report = json.loads(path.read_text()) if path.exists() else None
            if report and report['status'] in ('checking', 'writing') and not self.jobs.busy():
                report['notice'] = 'Auftrag unterbrochen. Gerätezustand erneut lesen; nicht automatisch wiederholen.'
            return {'prepared': prepared, 'last_change': report, 'automatic_retry': False, 'reset_available': False}

    def cancel(self, request):
        if request != {}:
            raise ValueError('Vorbereitung verwerfen benötigt ein leeres Objekt.')
        with self.lock:
            self.pending = None
        return self.status()

    def prepare(self, request):
        config = self.receiver.status()['config']
        saved = self.settings_store.latest(config['device']['id']) if config['device'] else None
        preview = settings_preview(config, saved, request)
        if not preview['changes']:
            raise ValueError('Keine Änderung vorzubereiten.')
        with (self.settings_store.root / ('bt06-' + saved['device_id']) / saved['capture']).open() as stream:
            original, errors, _ = settings_capture(csv.DictReader(stream, delimiter=';'))
        if errors:
            raise ValueError('Bisheriger Einstellungsstand unvollständig. Neu lesen.')
        desired = {item['field']: item['after'] for item in preview['changes']}
        configuration_frames(original, desired)
        selected_binding = binding(config)

        async def operation(actual_config, progress):
            if binding(actual_config) != selected_binding:
                raise ProtocolError('Geräteauswahl geändert; erneut vorbereiten.')
            with self.lock:
                self.pending = None
            async with self.session(actual_config, progress) as client:
                observation = await retrieve_settings(actual_config, progress, client=client)
                values = complete(observation)
                fresh = self.settings_store.save(actual_config['device']['id'], observation)
                same_configuration(original, observation['payloads'])
                snapshot = await self.full_history(actual_config, client, progress, observation['payloads'])
                plan = settings_preview(actual_config, fresh, {'base_capture': fresh['capture'], 'changes': desired})
                configuration_frames(observation['payloads'], desired)
            public = {'kind': 'configuration-prepared', 'token': secrets.token_urlsafe(32), 'preview': plan,
                      'values_before': values,
                      'history': {'id': snapshot['id'], 'count': snapshot['count'], 'scope': 'full'},
                      'recording_before': values['recording'], 'will_stop': values['recording_code'] == 16,
                      'will_restart': False,
                      'notice': 'Speichern kann die Gerätehistorie löschen. Aufzeichnung bleibt danach gestoppt. Kein Reset und kein automatischer Neustart der Aufzeichnung.'}
            with self.lock:
                self.pending = {'public': public, 'binding': selected_binding, 'deadline': time.monotonic() + 600,
                                'payloads': observation['payloads'], 'desired': desired, 'preview': plan,
                                'recording_code': values['recording_code']}
            return deepcopy(public)
        return self.jobs.start_task('configuration_prepare', operation)

    def apply(self, request):
        required = {'token', 'confirm_history_loss', 'confirm_stop'}
        if (not isinstance(request, dict) or set(request) != required
                or request['confirm_history_loss'] is not True or request['confirm_stop'] is not True):
            raise ValueError('Konkrete Vorbereitung, möglicher Historienverlust und gestoppte Aufzeichnung müssen ausdrücklich bestätigt werden.')
        with self.lock:
            self.status()
            context = self.pending
            if (not context or not isinstance(request['token'], str)
                    or not secrets.compare_digest(context['public']['token'], request['token'])):
                raise ValueError('Vorbereitung fehlt, abgelaufen oder bereits verbraucht. Erneut vorbereiten.')
            latest = self.settings_store.latest(context['preview']['device_id'])
            if not latest or latest['capture'] != context['preview']['base_capture']:
                self.pending = None
                raise ValueError('Einstellungsstand ersetzt. Änderungen erneut vorbereiten.')
            # Single use, including start failure, timeout and failed acknowledgement.
            self.pending = None
            context = deepcopy(context)

        async def operation(config, progress):
            if binding(config) != context['binding']:
                raise ProtocolError('Geräteauswahl geändert; kein Schreiben.')
            journal = ChangeJournal(self.root, context)
            try:
                async with self.session(config, progress) as client:
                    before = await retrieve_settings(config, progress, client=client)
                    values = complete(before)
                    same_configuration(context['payloads'], before['payloads'])
                    if values['recording_code'] != context['recording_code']:
                        raise ProtocolError('Aufzeichnungszustand geändert. Neu vorbereiten.')
                    frames = configuration_frames(before['payloads'], context['desired'])
                    journal.history(await self.full_history(config, client, progress, before['payloads']))
                    if values['recording_code'] == 16:
                        progress('stopping_logger')
                        await self.send(client, STOP, 'stop', journal)
                        stopped = await retrieve_settings(config, progress, client=client)
                        stopped_saved = self.settings_store.save(config['device']['id'], stopped)
                        journal.save(stopped_settings_capture=stopped_saved['capture'])
                        if complete(stopped)['recording_code'] not in (1, 2, 4, 5):
                            raise ProtocolError('Loggerstopp nicht bestätigt; keine Parameteränderung.')
                        same_configuration(before['payloads'], stopped['payloads'])
                        # Stop does not authorize erasing a value recorded after the first read.
                        journal.history(await self.full_history(config, client, progress, stopped['payloads']))
                    progress('writing_settings')
                    ready = await retrieve_settings(config, progress, client=client)
                    if complete(ready)['recording_code'] not in (1, 2, 4, 5):
                        raise ProtocolError('Logger zeichnet wieder auf; keine Parameteränderung.')
                    same_configuration(before['payloads'], ready['payloads'])
                    for frame in frames:
                        await self.send(client, frame, 'parameters', journal)
                    progress('verifying_settings')
                    staged = await retrieve_settings(config, progress, client=client)
                    staged_saved = self.settings_store.save(config['device']['id'], staged)
                    journal.save(staged_settings_capture=staged_saved['capture'],staged_settings_sha256=staged_saved['capture_sha256'])
                    if complete(staged)['recording_code'] not in (1, 2, 4, 5):
                        raise ProtocolError('Logger zeichnet vor dem Speichern wieder auf; kein Save.')
                    visibility = self.verify(before['payloads'], staged['payloads'], context['desired'], before_commit=True)
                    journal.save(precommit_visibility=visibility)
                    progress('committing_settings')
                    await self.send(client, SAVE, 'save', journal)
                    await self.send(client, FINISH, 'finish', journal)
                    progress('verifying_settings')
                    after = await retrieve_settings(config, progress, client=client)
                    saved = self.settings_store.save(config['device']['id'], after)
                    actual = complete(after, after_commit=True)
                    self.verify(before['payloads'], after['payloads'], context['desired'])
                    kind, outcome = self.outcome(actual)
                    journal.save(**outcome, settings_capture=saved['capture'])
                    return {'kind':kind, 'report':deepcopy(journal.report), 'settings':saved}
            except BaseException:
                journal.save(status='uncertain' if journal.report['may_have_changed'] else 'blocked',
                             notice='Kein bestätigter Gesamterfolg. Zustand neu lesen; keine automatische Wiederholung, kein Rollback und kein automatischer Start.')
                raise
            finally:
                journal.close()
        return self.jobs.start_task('configuration_write', operation)

    def verify_last(self, request):
        """Reconcile completed acknowledgements by reading, never resend writes."""
        if request!={}:
            raise ValueError('Nachprüfung benötigt ein leeres Objekt; keine neuen Zielwerte.')
        config=self.receiver.status()['config']
        report_path=self.root/'latest.json'
        if not report_path.exists():
            raise ValueError('Kein Konfigurationsauftrag nachzuprüfen.')
        report=json.loads(report_path.read_text())
        if (not config['device'] or config['device']['id']!=report.get('device_id')
                or config['device']['firmware']!='2.05' or report.get('status') not in ('uncertain','writing','parameters_verified')):
            raise ValueError('Kein passender unbestätigter Auftrag für das gewählte Gerät.')
        if not isinstance(report.get('id'),str) or not re.fullmatch('[0-9a-f]{32}',report['id']):
            raise ValueError('Ungültiger Auftragsbeleg.')
        capture=report.get('staged_settings_capture','')
        if not isinstance(capture,str) or not re.fullmatch(r'[0-9a-f]{32}\.csv',capture):
            raise ValueError('Originaler Zwischenbeleg fehlt; keine Bestätigung möglich.')
        folder=self.settings_store.root/('bt06-'+report['device_id'])
        original=(folder/capture).read_bytes()
        if report.get('staged_settings_sha256') and hashlib.sha256(original).hexdigest()!=report['staged_settings_sha256']:
            raise ValueError('Zwischenbeleg beschädigt; keine Bestätigung möglich.')
        import io
        before,errors,_=settings_capture(csv.DictReader(io.StringIO(original.decode('utf-8')),delimiter=';'))
        if errors:
            raise ValueError('Zwischenbeleg unvollständig.')
        desired={item['field']:item['after'] for item in report['changes']}
        frames=configuration_frames(before,desired)
        with (self.root/(report['id']+'.csv')).open(encoding='utf-8') as stream:
            rows=list(csv.DictReader(stream,delimiter=';'))
        expected=([STOP] if rows and rows[0]['DatenHex']==STOP.hex() else [])+frames+[SAVE,FINISH]
        if len(rows)!=2*len(expected):
            raise ValueError('Nicht alle Schreib-/Save-/Abschlussantworten belegt; keine Wiederholung.')
        for index,frame in enumerate(expected):
            tx,rx=rows[2*index:2*index+2]
            if tx['Richtung']!='TX' or rx['Richtung']!='RX' or tx['DatenHex']!=frame.hex():
                raise ValueError('Schreibbeleg widersprüchlich.')
            configuration_reply(frame,bytes.fromhex(rx['DatenHex']))
        if not report.get('histories'):
            raise ValueError('Vollständiger gespeicherter Historienbeleg fehlt.')
        for history in report['histories']:
            if (history['scope']!='full' or history['logger']!='bt06-'+report['device_id']
                    or len(self.history_store.rows(history['logger'],history['id']))!=history['count']):
                raise ValueError('Gespeicherter Historienbeleg nicht verifiziert.')
        selected=binding(config)
        cached=None
        latest=self.settings_store.latest(report['device_id'])
        if latest and parse_time(latest['observed_at'])>parse_time(rows[-1]['Hostzeit']):
            with (folder/latest['capture']).open(encoding='utf-8') as stream:
                payloads,read_errors,_=settings_capture(csv.DictReader(stream,delimiter=';'))
            observation={'payloads':payloads,'read_errors':read_errors}
            try:
                actual=complete(observation,after_commit=True)
                self.verify(before,payloads,desired)
                self.outcome(actual)
                cached=(latest,actual)
            except ProtocolError:
                pass

        async def operation(actual_config,progress):
            if binding(actual_config)!=selected:
                raise ProtocolError('Geräteauswahl geändert; keine Bestätigung.')
            if cached:
                saved,actual=cached
                source='stored_postcommit_capture'
            else:
                async with self.session(actual_config,progress) as client:
                    observation=await retrieve_settings(actual_config,progress,client=client)
                    saved=self.settings_store.save(actual_config['device']['id'],observation)
                    actual=complete(observation,after_commit=True)
                    self.verify(before,observation['payloads'],desired)
                source='fresh_read'
            kind,outcome=self.outcome(actual)
            if json.loads(report_path.read_text())['id']!=report['id']:
                raise ProtocolError('Auftragsbeleg inzwischen ersetzt; keine Bestätigung.')
            report.update(**outcome,settings_capture=saved['capture'],reconciled_read_only=True,
                          reconciled_at=datetime.now(timezone.utc).isoformat(),verification_source=source,
                          verification_observed_at=saved['observed_at'])
            atomic_json(self.root/(report['id']+'.json'),report)
            atomic_json(report_path,report)
            return {'kind':kind,'report':deepcopy(report),'settings':saved}
        return self.jobs.start_task('configuration_verify',operation)

    async def full_history(self, config, client, progress, payloads):
        progress('securing_history')
        transfer = await retrieve(config, progress, client=client)
        if transfer.get('selection') is not None or transfer['settings'] != payloads['log_settings']:
            raise ProtocolError('Kein unveränderter vollständiger Historienstand; Schreiben blockiert.')
        progress('saving')
        result = self.history_store.publish(config['device']['id'], **transfer)
        if result['last_transfer_scope'] != 'full':
            raise ProtocolError('Vollständiger Historienabruf nicht bestätigt.')
        return result

    @staticmethod
    def outcome(actual):
        if actual.get('status_variant')=='zero_summary':
            return 'configuration-parameters-verified', {
                'status':'parameters_verified','recording_state_verified':False,
                'notice':'Alle Zielparameter zurückgelesen. Status ohne Aufzeichnungsdetails; kein automatischer Start. Aktuellen Advertising-Zustand beachten.'}
        if actual.get('recording_code') not in (1,2,4,5):
            raise ProtocolError('Aufzeichnungszustand nach Speichern unerwartet. Zustand manuell prüfen.')
        return 'configuration-verified', {'status':'verified','recording_state_verified':True,
                'notice':'Geänderte Werte zurückgelesen. Aufzeichnung gestoppt; kein automatischer Start.'}

    @staticmethod
    def verify(before, after, desired, *, before_commit=False):
        expected = dict(before)
        changed = set()
        for frame in configuration_frames(before, desired):
            key = {b'\x43\x33': 'device_info', b'\x43\x35': 'broadcast_settings', b'\x43\x02': 'log_settings', b'\x43\x20':'temperature_alarm', b'\x43\x23':'humidity_alarm'}[frame[2:4]]
            expected[key] = frame[4:-1]
            changed.add(key)
        if before_commit:
            # A getter can still expose committed settings before Save. Only
            # the entire original or intended block is admissible; unrelated
            # bytes and every unedited block must remain exact.
            visibility = {}
            for key in changed:
                actual = after.get(key)
                if actual not in (before[key], expected[key]):
                    raise ProtocolError('Zwischenprüfung: Geräteparameter weichen von Ausgangs- und Zielwert ab; kein Save.')
                visibility[key] = 'target_visible' if actual == expected[key] else 'previous_visible'
            same_configuration({key: value for key, value in before.items() if key not in changed},
                               {key: value for key, value in after.items() if key not in changed})
            return visibility
        same_configuration(expected, after)

    @staticmethod
    async def send(client, frame, phase, journal):
        service = client.services.get_service(SERVICE_UUID)
        tx, rx = service.get_characteristic(TX_UUID), service.get_characteristic(RX_UUID)
        queue = asyncio.Queue(maxsize=1)
        overflow = False
        def notify(sender, raw):
            nonlocal overflow
            if queue.full() or len(raw) > 64:
                overflow = True
            else:
                queue.put_nowait(bytes(raw))
        await asyncio.wait_for(client.start_notify(rx, notify), 8)
        try:
            journal.save(status='writing', may_have_changed=True, last_phase=phase)
            journal.note(phase, 'TX', frame)
            await asyncio.wait_for(client.write_gatt_char(tx, frame, response=True), 8)
            reply = await asyncio.wait_for(queue.get(), 8)
            journal.note(phase, 'RX', reply)
            if overflow:
                raise ProtocolError('Mehrdeutige Schreibantwort; nicht erneut senden.')
            configuration_reply(frame, reply)
        finally:
            await asyncio.wait_for(client.stop_notify(rx), 8)

    @staticmethod
    def session(config, progress, *, identity_callback=None):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def connected():
            from bleak import BleakClient
            progress('finding_device')
            target = await known_device(config)
            from backend.common.bt06 import advertised_reading
            manufacturer = target.details.get('props', {}).get('ManufacturerData', {})
            manufacturer = {key: getattr(value, 'value', value) for key, value in manufacturer.items()}
            identity = advertised_reading(manufacturer)
            if (not identity or identity['device_id'] != config['device']['id']
                    or identity['firmware'] != config['device']['firmware']):
                raise ProtocolError('Aktuelles Advertising bestätigt Gerätekennung und Firmware nicht; kein Schreiben.')
            if identity_callback:
                identity_callback(identity)
            client = BleakClient(target, pair=False, timeout=45)
            try:
                progress('connecting')
                await asyncio.wait_for(client.connect(), 50)
                service = client.services.get_service(SERVICE_UUID)
                tx = service.get_characteristic(TX_UUID) if service else None
                rx = service.get_characteristic(RX_UUID) if service else None
                if not tx or not rx or 'write' not in tx.properties or 'notify' not in rx.properties:
                    raise ProtocolError('BT06-GATT-Pfad nicht verifiziert.')
                yield client
            finally:
                await asyncio.wait_for(client.disconnect(), 10)
        return connected()
