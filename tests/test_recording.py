import copy
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from backend.common.bt06_gatt import ReadCommand,read_request
from backend.common.settings_commands import START,STOP,SAVE,FINISH
from backend.common.recording_store import RecordingProofStore,decode_inventory
from backend.linux.recording import RecordingWorkflow
from test_configuration import ConfigurationFixture


class RecordingTests(ConfigurationFixture):
    def setUp(self):
        super().setUp()
        raw=bytearray(self.payloads['log_status']);raw[3]=5;self.payloads['log_status']=bytes(raw)
        self.recording=RecordingWorkflow(self.receiver,self.jobs,self.settings,self.history,self.workflow)
        self.starts=[]
        # Observe the actual transport call, so tests prove durable protection
        # exists before the first potentially erasing frame is dispatched.
        original=self.workflow.send
        async def guarded(client,frame,phase,journal):
            if frame==START:
                saved=json.loads((self.recording.root/'changes/latest.json').read_text())
                proof=self.recording.proofs.read(saved['protection']['inventory_id'],'12345678')
                if proof['count']:
                    snapshot=saved['protection']['snapshot']
                    self.assertEqual(len(self.history.rows(snapshot['logger'],snapshot['id'])),proof['count'])
                self.starts.append(frame)
            return await original(client,frame,phase,journal)
        item=patch('backend.linux.recording.ConfigurationWorkflow.send',side_effect=guarded)
        item.start();self.addCleanup(item.stop)

    def prepare_start(self):
        self.recording.prepare({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        return self.recording.status()['prepared']

    def start(self,prepared):
        self.recording.apply({'token':prepared['token'],'confirm_history_loss':True,'confirm_start':True})
        self.jobs.worker.join(5)

    def test_nonempty_history_is_read_completely_and_exactly_one_start_is_sent(self):
        prepared=self.prepare_start()
        self.assertEqual(prepared['protection']['count'],3);self.assertEqual(self.starts,[])
        self.assertEqual(len(self.history.snapshots()),1)
        self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertEqual(self.jobs.status()['result']['kind'],'recording-started')
        self.assertEqual(self.starts,[START])
        for index,frame in enumerate(self.sent):
            if frame==read_request(ReadCommand.SELECT_ALL_HISTORY):
                self.assertEqual(self.sent[index-1],read_request(ReadCommand.LOG_STATUS))
        allowed={read_request(command) for command in ReadCommand}
        self.assertEqual([frame for frame in self.sent if frame not in allowed],[START])
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'],600)
        self.assertEqual(self.receiver.resumed,2)
        with self.assertRaises(ValueError):self.start(prepared)

    def empty_device(self):
        self.payloads['log_status']=bytes(8)
        self.payloads['log_settings']=(1500).to_bytes(2,'little')+bytes(13)
        self.metadata_override=bytes(10)

    def test_empty_history_requires_ten_byte_zero_proof_and_creates_no_measurement_snapshot(self):
        self.empty_device();prepared=self.prepare_start()
        self.assertEqual(prepared['interval_seconds'],1500)
        self.assertEqual(prepared['protection']['count'],0)
        self.assertIsNone(prepared['protection']['snapshot'])
        self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertEqual(self.history.snapshots(),[])
        self.assertNotIn(read_request(ReadCommand.RECEIVE_HISTORY),self.sent)
        self.assertEqual(self.starts,[START])

    def test_zero_status_alone_does_not_prove_empty_history(self):
        self.payloads['log_status']=bytes(8)
        self.recording.prepare({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[])
        for raw in (bytes(8),bytes(9),bytes(11),bytes(2)+(1).to_bytes(4,'little')+bytes(4)):
            with self.subTest(raw=raw),self.assertRaises(ValueError):decode_inventory(raw)

    def test_rejected_inventory_is_preserved_and_never_becomes_an_empty_proof(self):
        self.empty_device();self.inventory_reply_status=3
        self.recording.prepare({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'error')
        self.assertEqual(self.starts,[]);self.assertIsNone(self.recording.status()['prepared'])
        diagnostic=self.recording.status()['inventory_diagnostic']
        self.assertFalse(diagnostic['valid_inventory_proof'])
        raw=(self.recording.root/'diagnostics'/(diagnostic['id']+'.csv')).read_text()
        self.assertIn('266c0003',raw)
        self.assertIn(read_request(ReadCommand.LOG_STATUS).hex(),raw)

    def test_running_device_or_changed_settings_never_receive_start(self):
        raw=bytearray(self.payloads['log_status']);raw[3]=16;self.payloads['log_status']=bytes(raw)
        self.recording.prepare({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[])
        raw[3]=5;self.payloads['log_status']=bytes(raw);prepared=self.prepare_start()
        self.payloads['broadcast_settings']=bytes([6,100,0])
        self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[])

    def test_proof_corruption_disk_error_and_changed_inventory_block_before_start(self):
        prepared=self.prepare_start()
        key=prepared['protection']['inventory_id'];path=self.recording.root/'proofs'/(key+'.csv')
        original=path.read_bytes();path.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.start(prepared)
        path.write_bytes(original)
        with patch.object(self.history,'publish',side_effect=OSError('synthetic disk')):
            self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[])
        prepared=self.prepare_start();self.metadata_override=bytes(10)
        self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[])

    def test_missing_confirmation_expiry_replaced_capture_restart_and_cancel_are_safe(self):
        self.empty_device();prepared=self.prepare_start()
        for key in ('confirm_start','confirm_history_loss'):
            value={'token':prepared['token'],'confirm_start':True,'confirm_history_loss':True};value[key]=1
            with self.assertRaises(ValueError):self.recording.apply(value)
        self.recording.pending['deadline']=0
        with self.assertRaises(ValueError):self.start(prepared)
        prepared=self.prepare_start();self.recording.cancel({})
        with self.assertRaises(ValueError):self.start(prepared)
        prepared=self.prepare_start()
        restarted=RecordingWorkflow(self.receiver,self.jobs,self.settings,self.history,self.workflow)
        with self.assertRaises(ValueError):restarted.apply({'token':prepared['token'],'confirm_start':True,'confirm_history_loss':True})
        self.assertEqual(self.starts,[])

    def test_lost_ack_is_never_retried_and_only_a_reading_can_confirm_recording(self):
        self.empty_device();prepared=self.prepare_start();self.lost_start_ack=True
        self.start(prepared)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.starts,[START])
        self.assertEqual(self.recording.status()['last_start']['status'],'uncertain')
        with self.assertRaises(ValueError):self.start(prepared)
        self.recording.verify({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertEqual(self.jobs.status()['result']['kind'],'recording-started')
        self.assertEqual(self.starts,[START])

    def test_ack_with_zero_summary_is_pending_not_success_and_fresh_advertising_transition_can_confirm(self):
        self.empty_device();prepared=self.prepare_start();self.start_status=bytes(8)
        self.start(prepared)
        self.assertEqual(self.jobs.status()['result']['kind'],'recording-start-pending')
        count=self.connections
        live={'config':self.receiver.config,'fresh':True,'latest':{'device_id':'12345678','firmware':'2.05',
               'recording':'zeichnet auf','received_at':datetime.now(timezone.utc).isoformat()}}
        with patch.object(self.receiver,'status',return_value=live):
            self.recording.verify({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertEqual(self.recording.status()['last_start']['verification_source'],'fresh_advertising_transition')
        self.assertEqual(self.connections,count);self.assertEqual(self.starts,[START])


if __name__=='__main__':unittest.main()
