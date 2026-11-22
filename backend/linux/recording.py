"""Explicit recording start after durable full-history or empty-inventory proof."""
import csv
import hashlib
import json
import re
import secrets
import threading
import time
from copy import deepcopy
from datetime import datetime,timezone

from backend.common.bt06_gatt import ProtocolError,ReadCommand,read_request
from backend.common.device_settings import settings_capture
from backend.common.recording_store import RecordingProofStore
from backend.common.settings import atomic_json
from backend.common.settings_commands import START,configuration_reply
from backend.common.storage import parse_time
from .configuration import ConfigurationWorkflow,ChangeJournal,binding,complete,same_configuration
from .history_inventory import inventory
from .settings_reader import retrieve_settings


class RecordingWorkflow:
    def __init__(self,receiver,jobs,settings_store,history_store,configuration):
        self.receiver,self.jobs,self.settings_store=receiver,jobs,settings_store
        self.history_store,self.configuration=history_store,configuration
        self.root=history_store.root.parent/'recording'
        self.proofs=RecordingProofStore(self.root)
        self.lock=threading.RLock();self.pending=None

    def status(self):
        with self.lock:
            pending=self.pending
            if pending and (time.monotonic()>=pending['deadline'] or binding(self.receiver.status()['config'])!=pending['binding']):
                self.pending=pending=None
            if pending:
                latest=self.settings_store.latest(pending['public']['device_id'])
                if not latest or latest['capture']!=pending['capture']:self.pending=pending=None
            prepared=deepcopy(pending['public']) if pending else None
            if prepared:prepared['expires_in_seconds']=max(0,int(pending['deadline']-time.monotonic()))
            path=self.root/'changes/latest.json'
            report=json.loads(path.read_text()) if path.exists() else None
            diagnostic=self.root/'diagnostics/latest.json'
            return {'prepared':prepared,'last_start':report,'automatic_retry':False,
                    'inventory_diagnostic':json.loads(diagnostic.read_text()) if diagnostic.exists() else None}

    def cancel(self,value):
        if value!={}:raise ValueError('Startvorbereitung verwerfen benötigt ein leeres Objekt.')
        with self.lock:self.pending=None
        return self.status()

    @staticmethod
    def startable(observation,advertised,count):
        values=complete(observation,after_commit=True)
        if values['recording_code']==16 or advertised.get('recording')=='zeichnet auf':
            raise ProtocolError('Logger zeichnet bereits auf; kein erneuter Start.')
        if advertised.get('recording') not in ('initialisiert','gestoppt'):
            raise ProtocolError('Advertising bestätigt keinen zulässigen Ausgangszustand; kein Start.')
        if values.get('status_variant')=='zero_summary' and count:
            raise ProtocolError('Status ohne Details bei vorhandenem Bestand; Start gesperrt.')
        return values

    def saved_payloads(self,capture,device_id,digest=None):
        if not isinstance(capture,str) or not re.fullmatch(r'[0-9a-f]{32}\.csv',capture):raise ValueError('Ungültiger Einstellungsbeleg.')
        path=self.settings_store.root/('bt06-'+device_id)/capture
        if digest and hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Einstellungsbeleg beschädigt.')
        with path.open(encoding='utf-8') as stream:values,errors,_=settings_capture(list(csv.DictReader(stream,delimiter=';')))
        if errors:raise ValueError('Einstellungsbeleg unvollständig.')
        return values

    async def protect(self,config,client,progress,payloads,allow_unread_loss=False):
        failures=[]
        def failure(rows,error):failures.append(self.proofs.diagnostic(config['device']['id'],rows,error))
        try:
            observation=await inventory(client,progress,on_failure=failure)
        except ProtocolError:
            if not allow_unread_loss or not failures or payloads['log_status']!=bytes(8):raise
            diagnostic=failures[-1]
            rows=self.proofs.read_diagnostic(diagnostic['id'],config['device']['id'])
            if (len(rows)!=4 or rows[0]['DatenHex']!=read_request(ReadCommand.LOG_STATUS).hex()
                    or rows[1]['DatenHex']!=(bytes.fromhex('264c0101')+bytes(8)+b'#').hex()
                    or rows[2]['DatenHex']!=read_request(ReadCommand.SELECT_ALL_HISTORY).hex()
                    or rows[3]['DatenHex']!='266c000323'):raise
            candidates=[item for item in self.history_store.snapshots() if item['logger']=='bt06-'+config['device']['id'] and item.get('full_read_verified')]
            if not candidates:raise ProtocolError('Gesicherter Altbestand fehlt; kein Ausnahmestart.')
            saved=max(candidates,key=lambda item:item['count'])
            if len(self.history_store.rows(saved['logger'],saved['id']))!=saved['count']:raise ProtocolError('Altbestand nicht verifiziert.')
            return {'inventory_id':None,'diagnostic_id':diagnostic['id'],'count':None,'metadata_hex':None,'snapshot':None,
                    'unread_history_loss_accepted':True,'archived_reference':{'logger':saved['logger'],'id':saved['id'],'count':saved['count'],'scope':'full'}}
        if observation['status']!=payloads['log_status']:
            raise ProtocolError('Aufzeichnungsstatus während der Prüfung geändert; kein Start.')
        proof=self.proofs.save(config['device']['id'],observation)
        snapshot=None
        if proof['count']:
            snapshot=await self.configuration.full_history(config,client,progress,payloads)
            rows=self.history_store.rows(snapshot['logger'],snapshot['id'])
            if (len(rows)!=proof['count'] or int(rows[0]['GeraeteSekunden'])!=proof['first_device_seconds']
                    or int(rows[-1]['GeraeteSekunden'])!=proof['last_device_seconds']):
                raise ProtocolError('Vollauslesung widerspricht Umfangsbeleg; kein Start.')
            end=await inventory(client,progress,on_failure=failure)
            if end['metadata']!=observation['metadata']:
                raise ProtocolError('Historie während der Prüfung geändert; kein Start.')
        return {'inventory_id':proof['id'],'count':proof['count'],'metadata_hex':proof['metadata_hex'],
                'snapshot':({'logger':snapshot['logger'],'id':snapshot['id'],'count':snapshot['count'],'scope':'full'} if snapshot else None)}

    def prepare(self,value):
        if not isinstance(value,dict) or not (value=={} or set(value)=={'allow_unread_history_loss'} and value['allow_unread_history_loss'] is True):raise ValueError('Ungültige Startvorbereitung.')
        allow_unread=value.get('allow_unread_history_loss') is True
        selected=binding(self.receiver.status()['config'])
        if not selected or selected[-1]!='2.05':raise ValueError('Verifizierten BT06 mit Firmware 2.05 auswählen.')
        async def operation(config,progress):
            if binding(config)!=selected:raise ProtocolError('Geräteauswahl geändert; erneut vorbereiten.')
            with self.lock:self.pending=None
            advertised={}
            async with ConfigurationWorkflow.session(config,progress,identity_callback=advertised.update) as client:
                observation=await retrieve_settings(config,progress,client=client)
                saved=self.settings_store.save(config['device']['id'],observation)
                self.startable(observation,advertised,0)
                if allow_unread and advertised['recording']!='initialisiert':raise ProtocolError('Ausnahme nur im Initialzustand zulässig.')
                protection=await self.protect(config,client,progress,observation['payloads'],allow_unread)
                values=self.startable(observation,advertised,protection['count'])
            public={'kind':'recording-prepared','token':secrets.token_urlsafe(32),'device_id':config['device']['id'],
                    'interval_seconds':values['record_interval_seconds'],'temperature_unit':values['temperature_unit'],
                    'protection':protection,'advertising_before':advertised['recording'],
                    'allow_unread_history_loss':allow_unread,
                    'notice':('Gerätebestand nicht auslesbar. Eventuell noch ungesicherte Gerätedaten dürfen beim bestätigten Start verloren gehen. ' if protection.get('unread_history_loss_accepted') else 'Aktueller Gesamtbestand wird vor Start erneut geprüft und gesichert. ')+
                             'Intervall und Geräteuhr werden nicht geändert; Gerätezeit bleibt ungeprüft.'}
            with self.lock:
                self.pending={'public':public,'binding':selected,'deadline':time.monotonic()+600,'capture':saved['capture'],
                              'payloads':observation['payloads'],'state':(values.get('recording_code'),values.get('status_variant')),'allow_unread':allow_unread}
            return deepcopy(public)
        return self.jobs.start_task('recording_prepare',operation)

    def apply(self,value):
        if (not isinstance(value,dict) or set(value)-{'token','confirm_history_loss','confirm_start','confirm_unread_history_loss'} or not {'token','confirm_history_loss','confirm_start'}<=set(value)
                or value['confirm_history_loss'] is not True or value['confirm_start'] is not True):
            raise ValueError('Konkreten Aufzeichnungsstart und möglichen Historienverlust ausdrücklich bestätigen.')
        with self.lock:
            self.status();context=self.pending
            if not context or not isinstance(value['token'],str) or not secrets.compare_digest(value['token'],context['public']['token']):
                raise ValueError('Startvorbereitung fehlt, abgelaufen oder verbraucht.')
            if context['allow_unread'] and value.get('confirm_unread_history_loss') is not True:
                raise ValueError('Möglichen Verlust noch nicht ausgelesener Gerätedaten ausdrücklich bestätigen.')
            if not context['allow_unread'] and 'confirm_unread_history_loss' in value:raise ValueError('Unpassende Zusatzbestätigung.')
            if context['public']['protection'].get('unread_history_loss_accepted'):
                self.proofs.read_diagnostic(context['public']['protection']['diagnostic_id'],context['public']['device_id'])
            else:self.proofs.read(context['public']['protection']['inventory_id'],context['public']['device_id'])
            context=deepcopy(context);self.pending=None

        async def operation(config,progress):
            if binding(config)!=context['binding']:raise ProtocolError('Geräteauswahl geändert; kein Start.')
            journal=ChangeJournal(self.root/'changes',{'preview':{'device_id':config['device']['id'],
                        'changes':[{'field':'recording','before':context['public']['advertising_before'],'after':'zeichnet auf'}]}})
            try:
                journal.save(action='recording_start',target_binding=list(context['binding']),interval_seconds=context['public']['interval_seconds'])
                advertised={}
                async with ConfigurationWorkflow.session(config,progress,identity_callback=advertised.update) as client:
                    before=await retrieve_settings(config,progress,client=client)
                    saved=self.settings_store.save(config['device']['id'],before)
                    same_configuration(context['payloads'],before['payloads'])
                    self.startable(before,advertised,0)
                    if context['allow_unread'] and advertised['recording']!='initialisiert':raise ProtocolError('Initialzustand geändert.')
                    protection=await self.protect(config,client,progress,before['payloads'],context['allow_unread'])
                    values=self.startable(before,advertised,protection['count'])
                    if (values.get('recording_code'),values.get('status_variant'))!=context['state'] or protection['metadata_hex']!=context['public']['protection']['metadata_hex']:
                        raise ProtocolError('Zustand oder Historienumfang geändert; Start erneut vorbereiten.')
                    journal.save(settings_before_capture=saved['capture'],settings_before_sha256=saved['capture_sha256'],
                                 protection=protection,advertising_before=advertised['recording'])
                    if protection['snapshot']:journal.history({**protection['snapshot'],'last_transfer_scope':'full'})
                    if protection.get('archived_reference'):journal.history({**protection['archived_reference'],'last_transfer_scope':'full'})
                    journal.save(unread_history_loss_confirmed=context['allow_unread'])
                    progress('starting_logger')
                    await ConfigurationWorkflow.send(client,START,'start',journal)
                    journal.save(start_acknowledged=True,start_ack_at=datetime.now(timezone.utc).isoformat())
                    progress('verifying_recording')
                    after=await retrieve_settings(config,progress,client=client)
                    observed=self.settings_store.save(config['device']['id'],after)
                    journal.save(settings_after_capture=observed['capture'])
                    actual=complete(after,after_commit=True)
                    same_configuration(before['payloads'],after['payloads'])
                    active=actual.get('recording_code')==16
                    journal.save(status='recording' if active else 'start_pending',
                                 notice='Aufzeichnung am Gerät bestätigt.' if active else 'Start bestätigt; aktive Aufzeichnung noch nicht nachgewiesen. Nur lesend prüfen, Start nicht wiederholen.',
                                 verification_source='gatt_status' if active else None)
                    return {'kind':'recording-started' if active else 'recording-start-pending','report':deepcopy(journal.report)}
            except BaseException:
                journal.save(status='uncertain' if journal.report['may_have_changed'] else 'blocked',
                             notice='Aufnahmestart nicht vollständig bestätigt. Nur lesend prüfen; Start niemals automatisch wiederholen.')
                raise
            finally:journal.close()
        return self.jobs.start_task('recording_start',operation)

    def verify(self,value):
        if value!={}:raise ValueError('Startprüfung erwartet ein leeres Objekt.')
        path=self.root/'changes/latest.json'
        if not path.exists():raise ValueError('Kein Startauftrag vorhanden.')
        report=json.loads(path.read_text());config=self.receiver.status()['config']
        if (list(binding(config) or ())!=report.get('target_binding') or not config['device']
                or report.get('device_id')!=config['device']['id'] or not re.fullmatch('[0-9a-f]{32}',report.get('id',''))):
            raise ValueError('Kein passender Startauftrag; nicht wiederholen.')
        manual=report['protection'].get('unread_history_loss_accepted')
        if manual:
            if report.get('unread_history_loss_confirmed') is not True:raise ValueError('Ausnahmefreigabe fehlt.')
            self.proofs.read_diagnostic(report['protection']['diagnostic_id'],report['device_id'])
            proof={'count':None,'metadata_hex':None}
            archived=report['protection']['archived_reference']
            if len(self.history_store.rows(archived['logger'],archived['id']))!=archived['count']:raise ValueError('Altbestand beschädigt.')
        else:proof=self.proofs.read(report['protection']['inventory_id'],report['device_id'])
        if proof['count']!=report['protection']['count'] or proof['metadata_hex']!=report['protection']['metadata_hex']:
            raise ValueError('Historienumfang widersprüchlich.')
        snapshot=report['protection']['snapshot']
        if proof['count']:
            if not snapshot or snapshot['scope']!='full' or snapshot['logger']!='bt06-'+report['device_id']:
                raise ValueError('Vollständige Historie fehlt.')
            original=self.history_store.rows(snapshot['logger'],snapshot['id'])
            if len(original)!=proof['count']:raise ValueError('Historienbeleg unvollständig.')
        with (self.root/'changes'/(report['id']+'.csv')).open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream,delimiter=';'))
        if len(rows) not in (1,2) or rows[0]['Richtung']!='TX' or rows[0]['DatenHex']!=START.hex():
            raise ValueError('Startbeleg unvollständig.')
        if len(rows)==2:
            if rows[1]['Richtung']!='RX':raise ValueError('Startantwort nicht verifiziert.')
            configuration_reply(START,bytes.fromhex(rows[1]['DatenHex']))
        reference_at=rows[-1]['Hostzeit'];parse_time(reference_at)
        before=self.saved_payloads(report['settings_before_capture'],report['device_id'],report['settings_before_sha256'])
        async def operation(actual_config,progress):
            if list(binding(actual_config) or ())!=report['target_binding']:raise ProtocolError('Geräteauswahl geändert.')
            live=self.receiver.status();latest=live.get('latest') or {}
            cached=self.settings_store.latest(report['device_id'])
            active=False;source=None
            if cached and not cached['decode_errors'] and not cached['read_errors'] and parse_time(cached['observed_at'])>parse_time(reference_at):
                payloads=self.saved_payloads(cached['capture'],report['device_id'])
                same_configuration(before,payloads)
                if (live.get('fresh') and latest.get('device_id')==report['device_id'] and latest.get('firmware')=='2.05'
                        and latest.get('recording')=='zeichnet auf' and report['advertising_before'] in ('initialisiert','gestoppt')
                        and parse_time(latest['received_at'])>parse_time(reference_at)):
                    active=True;source='fresh_advertising_transition'
            if not active:
                async with ConfigurationWorkflow.session(actual_config,progress) as client:
                    observation=await retrieve_settings(actual_config,progress,client=client)
                    saved=self.settings_store.save(report['device_id'],observation)
                    actual=complete(observation,after_commit=True);same_configuration(before,observation['payloads'])
                    active=actual.get('recording_code')==16;source='gatt_status' if active else None
                    report['settings_after_capture']=saved['capture']
            if json.loads(path.read_text())['id']!=report['id']:raise ProtocolError('Startauftrag inzwischen ersetzt.')
            report.update(status='recording' if active else 'start_pending',verification_source=source,
                          notice='Aufzeichnung am Gerät bestätigt.' if active else 'Aktive Aufzeichnung noch nicht bestätigt; Start nicht wiederholen.',
                          verified_at=datetime.now(timezone.utc).isoformat())
            atomic_json(self.root/'changes'/(report['id']+'.json'),report);atomic_json(path,report)
            return {'kind':'recording-started' if active else 'recording-start-pending','report':deepcopy(report)}
        return self.jobs.start_task('recording_verify',operation)
