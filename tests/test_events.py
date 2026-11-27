import csv
import io
import json
import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from backend.common.events import EventStore,FIELDS
from backend.common.live_store import LiveStore
from backend.common.bt06 import MANUFACTURER_ID
from backend.common.history_store import HistoryStore
from backend.common.history_capture import decode_capture
from backend.linux.receiver import Receiver
from backend.linux.history_jobs import HistoryJobs
from test_live import config,frame
from test_history_jobs import FakeReceiver
from history_fixture import capture


class EventTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.events=EventStore(self.root/'data/events')

    def test_monthly_csv_persistence_filters_and_export(self):
        first=self.events.append('application.started','info','Test; "Start"',at='2026-10-31T23:30:00Z')
        second=self.events.append('receiver.error','error','Speicherung fehlgeschlagen.',logger='bt06-12345678',source='receiver',details={'reason':'synthetic'},at='2026-11-01T01:00:00+01:00')
        self.assertEqual(len(list(self.events.root.glob('*/*.csv'))),2)
        result=EventStore(self.events.root).query(limit=1)
        self.assertEqual(result['events'][0]['EreignisID'],second['EreignisID']);self.assertTrue(result['truncated'])
        self.assertEqual(self.events.query(level='error')['events'],[second])
        self.assertEqual(self.events.query(logger='bt06-12345678',event_type='receiver.error')['events'],[second])
        self.assertEqual(list(self.events.rows(end='2026-10-31T23:59:59Z')),[first])
        self.assertEqual(list(csv.DictReader(io.StringIO(';'.join(FIELDS)+'\n'+next(self.events.root.glob('2026/2026-10.csv')).read_text().split('\n',1)[1]),delimiter=';'))[0]['Nachricht'],first['Nachricht'])
        self.assertEqual(self.events.root.stat().st_mode&0o777,0o700)
        self.assertEqual(next(self.events.root.glob('*/*.csv')).stat().st_mode&0o777,0o600)

    def test_concurrent_instances_keep_single_header_and_all_rows(self):
        stores=[self.events,EventStore(self.events.root)]
        def write(index):
            for _ in range(10):stores[index%2].append('application.started','info','Parallel.',at='2026-11-01T00:00:00Z')
        threads=[threading.Thread(target=write,args=(i,)) for i in range(4)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        result=self.events.query(limit=100)['events'];self.assertEqual(len(result),40)
        self.assertEqual(len({row['EreignisID'] for row in result}),40)

    def test_partial_tail_blocks_writes_and_reads_without_repair(self):
        self.events.append('application.started','info','Start.',at='2026-11-01T00:00:00Z')
        path=next(self.events.root.glob('*/*.csv'));path.write_bytes(path.read_bytes()+b'partial')
        original=path.read_bytes()
        self.assertIsNone(self.events.emit('application.stopped','info','Stop.',at='2026-11-01T00:01:00Z'))
        self.assertEqual(path.read_bytes(),original);self.assertEqual(self.events.status()['failed_this_session'],1)
        with self.assertRaises(ValueError):self.events.query()

    def test_corrupt_rows_and_headers_are_reported_without_modification(self):
        path=self.events.root/'2026/2026-11.csv';path.parent.mkdir(parents=True)
        for raw in ('broken\n','"unclosed\n',';'.join(FIELDS)+'\n1;bad\n'):
            path.write_text(raw)
            with self.assertRaises(ValueError):self.events.query()
            self.assertEqual(path.read_text(),raw)

    def test_unconfirmed_fsync_is_visible_and_never_retried(self):
        with patch('backend.common.events.os.fsync',side_effect=OSError('synthetic')):
            self.assertIsNone(self.events.emit('application.started','info','Start.',at='2026-11-01T00:00:00Z'))
        self.assertEqual(self.events.status()['stored_this_session'],0)
        self.assertEqual(self.events.status()['failed_this_session'],1)
        self.assertEqual(len(self.events.query()['events']),1)

    def test_invalid_filters_are_rejected_even_without_files(self):
        for options in ({'limit':0},{'limit':501},{'level':'critical'},{'event_type':'arbitrary'},{'logger':'../private'},
                        {'start':'2026-02-01T00:00:00Z','end':'2026-01-01T00:00:00Z'}):
            with self.subTest(options=options),self.assertRaises(ValueError):self.events.query(**options)

    def receiver(self):
        receiver=Receiver(self.root/'config/receiver.json',LiveStore(self.root/'data'),threading.Lock(),self.events)
        receiver.config=config();receiver.value['state']='receiving'
        device=SimpleNamespace(address=config()['device']['address'])
        return receiver,device

    def test_advertising_transitions_stale_recovery_and_internal_pause(self):
        receiver,device=self.receiver();now=datetime(2026,11,1,tzinfo=timezone.utc)
        advert=SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame()},rssi=-50)
        receiver.on_advertisement(device,advert,now);receiver.check_health(now+timedelta(seconds=91));receiver.check_health(now+timedelta(seconds=100))
        receiver.on_advertisement(device,advert,now+timedelta(seconds=100))
        before=len(self.events.query()['events']);receiver.stop(persist=False);receiver.check_health(now+timedelta(seconds=300))
        types=[row['Typ'] for row in self.events.query()['events']]
        self.assertEqual(len(types),before);self.assertEqual(types.count('receiver.fresh'),2)
        self.assertEqual(types.count('receiver.stale'),1);self.assertEqual(types.count('device.recording'),1)

    def test_memory_marker_does_not_claim_empty_storage(self):
        receiver,device=self.receiver();now=datetime(2026,11,1,tzinfo=timezone.utc)
        for i,full in enumerate((False,True,False)):
            raw=bytearray(frame());raw[12]|=4 if full else 0
            receiver.on_advertisement(device,SimpleNamespace(manufacturer_data={MANUFACTURER_ID:bytes(raw)},rssi=-50),now+timedelta(seconds=i*60))
        values=self.events.query(event_type='device.memory_full')['events'];self.assertEqual(len(values),2)
        self.assertIn('unbekannt',values[0]['Nachricht'])

    def test_receiver_error_dedup_recovery_and_event_failure_preserve_measurements(self):
        receiver,device=self.receiver();now=datetime(2026,11,1,tzinfo=timezone.utc)
        advert=SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame()},rssi=-50)
        with patch.object(receiver.store,'append',side_effect=OSError('synthetic')):
            receiver.on_advertisement(device,advert,now);receiver.on_advertisement(device,advert,now+timedelta(seconds=60))
        receiver.on_advertisement(device,advert,now+timedelta(seconds=120))
        self.assertEqual(len(self.events.query(event_type='receiver.error')['events']),1)
        self.assertEqual(len(self.events.query(event_type='receiver.recovered')['events']),1)
        with patch.object(self.events,'append',side_effect=OSError('synthetic')):
            receiver._fresh_state=False;receiver.on_advertisement(device,advert,now+timedelta(seconds=180))
        self.assertEqual(receiver.value['saved_this_session'],2);self.assertIsNone(receiver.value['error'])
        self.assertIsNotNone(self.events.status()['error'])

    def test_unconfirmed_start_remains_warning_and_logging_failure_cannot_block_completion(self):
        receiver=FakeReceiver();jobs=HistoryJobs(receiver,HistoryStore(self.root/'history'),events=self.events)
        result={'kind':'recording-start-pending','report':{'status':'start_pending'}}
        jobs.start_task('recording_start',AsyncMock(return_value=result));jobs.worker.join(5)
        event=self.events.query(event_type='task.completed')['events'][0]
        self.assertEqual(event['Stufe'],'warning');self.assertIn('unvollständig',event['Nachricht'])
        completions=[]
        with patch.object(self.events,'append',side_effect=OSError('synthetic')),patch('backend.linux.history_jobs.retrieve',AsyncMock(return_value=decode_capture(capture()))):
            jobs.start({'mode':'full'},on_complete=completions.append);jobs.worker.join(5)
        self.assertEqual(jobs.status()['state'],'done');self.assertEqual(len(completions),1)
        self.assertEqual(receiver.resumed,2);self.assertIsNotNone(self.events.status()['error'])

    def test_job_success_and_failure_are_logged_after_receiver_recovery(self):
        receiver=FakeReceiver();jobs=HistoryJobs(receiver,HistoryStore(self.root/'history'),events=self.events)
        with patch('backend.linux.history_jobs.retrieve',AsyncMock(return_value=decode_capture(capture()))):
            jobs.start({'mode':'full'});jobs.worker.join(5)
        self.assertEqual(jobs.status()['state'],'done');self.assertEqual(receiver.resumed,1)
        with patch('backend.linux.history_jobs.retrieve',AsyncMock(side_effect=TimeoutError())):
            jobs.start({'mode':'full'});jobs.worker.join(5)
        self.assertEqual(jobs.status()['state'],'error');self.assertEqual(receiver.resumed,2)
        self.assertEqual(len(self.events.query(event_type='task.completed')['events']),1)
        self.assertEqual(len(self.events.query(event_type='task.failed')['events']),1)
