import asyncio
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.common.bt06_gatt import SERVICE_UUID, TX_UUID, RX_UUID, ReadCommand, read_request
from backend.common.device_settings import DeviceSettingsStore, SETTINGS_QUERIES
from backend.common.history_store import HistoryStore
from backend.common.settings_commands import STOP, SAVE, FINISH, configuration_frames, configuration_reply
from backend.linux.configuration import ConfigurationWorkflow
from backend.linux.history_jobs import HistoryJobs
from history_fixture import capture
from settings_fixture import observation
from test_history_jobs import FakeReceiver


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = DeviceSettingsStore(self.root / 'settings')
        self.history = HistoryStore(self.root / 'history')
        self.receiver = FakeReceiver()
        self.jobs = HistoryJobs(self.receiver, self.history, self.settings)
        self.workflow = ConfigurationWorkflow(self.receiver, self.jobs, self.settings, self.history)
        self.sample = observation()
        self.sample['payloads']['log_settings'] = (600).to_bytes(2, 'little') + bytes(13)
        for row in self.sample['capture']:
            if row['Richtung'] == 'RX' and row['DatenHex'].startswith('26720201'):
                row['DatenHex'] = (bytes.fromhex('26720201') + self.sample['payloads']['log_settings'] + b'#').hex()
        self.saved = self.settings.save('12345678', self.sample)
        self.payloads = copy.deepcopy(self.sample['payloads'])
        self.sent = []; self.connections = 0; self.fail_opcode = None; self.corrupt_readback = False
        self.fail_history = False
        self.deferred_setter = False; self.pending_log = None; self.third_value = False; self.ignore_save = False
        self.final_status = None
        test = self
        rows = capture()
        metadata = bytes.fromhex(rows[3]['DatenHex'])[4:-1]
        chunks = [bytes.fromhex(row['DatenHex']) for row in rows[8:]]
        class Client:
            def __init__(self, target, **options):
                test.assertFalse(options['pair'])
                tx = SimpleNamespace(properties=['write']); rx = SimpleNamespace(properties=['notify'])
                service = SimpleNamespace(get_characteristic=lambda key: tx if key == TX_UUID else rx if key == RX_UUID else None)
                self.services = SimpleNamespace(get_service=lambda key: service if key == SERVICE_UUID else None)
            async def connect(self):test.connections += 1
            async def disconnect(self):pass
            async def start_notify(self, rx, notify):self.notify = notify
            async def stop_notify(self, rx):pass
            async def write_gatt_char(self, tx, wire, **options):
                test.sent.append(wire)
                if wire in (STOP, SAVE, FINISH) or wire[2:4] == b'\x43\x02':
                    durable = json.loads((test.workflow.root / 'latest.json').read_text())
                    test.assertTrue(durable['may_have_changed'])
                    test.assertGreaterEqual(len(durable['histories']), 1 if wire == STOP or STOP not in test.sent else 2)
                    for item in durable['histories']:
                        test.assertEqual(len(test.history.rows(item['logger'], item['id'])), item['count'])
                if wire[2:4] == test.fail_opcode:raise TimeoutError()
                if wire == STOP:
                    raw = bytearray(test.payloads['log_status']); raw[3] = 5; test.payloads['log_status'] = bytes(raw)
                elif wire[2:4] == b'\x43\x02':
                    if test.deferred_setter:
                        test.pending_log = wire[4:-1]
                    else:
                        test.payloads['log_settings'] = ((900).to_bytes(2,'little') + wire[6:-1]) if test.third_value else wire[4:-1]
                elif wire == SAVE and test.pending_log is not None and not test.ignore_save:
                    test.payloads['log_settings'] = test.pending_log
                elif wire == SAVE and test.corrupt_readback:
                    test.payloads['broadcast_settings'] = bytes([6,100,0])
                elif wire == FINISH and test.final_status is not None:
                    test.payloads['log_status']=test.final_status
                commands = {read_request(command): key for key, command in SETTINGS_QUERIES}
                if wire in commands:
                    self.notify(None, b'\x26' + wire[2:4] + b'\x01' + test.payloads[commands[wire]] + b'#')
                elif wire == read_request(ReadCommand.SELECT_ALL_HISTORY):
                    self.notify(None, b'\x26' + wire[2:4] + b'\x01' + metadata + b'#')
                else:
                    self.notify(None, b'\x26' + wire[2:4] + b'\x01#')
                    if wire == read_request(ReadCommand.RECEIVE_HISTORY):
                        if test.fail_history:raise TimeoutError()
                        for chunk in chunks:self.notify(None, chunk)
        advertising = bytearray(24); advertising[:3] = bytes.fromhex('090205'); advertising[4:8] = bytes.fromhex('12345678')
        target = SimpleNamespace(details={'props': {'ManufacturerData': {0xff23: bytes(advertising)}}})
        patches = [patch('backend.linux.configuration.known_device', AsyncMock(return_value=target)),
                   patch.dict('sys.modules', {'bleak': SimpleNamespace(BleakClient=Client)})]
        for item in patches:item.start(); self.addCleanup(item.stop)

    def prepare(self):
        self.workflow.prepare({'base_capture': self.saved['capture'], 'changes': {'record_interval_seconds': 1500}})
        self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'done', self.jobs.status())
        return self.workflow.status()['prepared']

    def apply(self, prepared):
        return self.workflow.apply({'token': prepared['token'], 'confirm_history_loss': True, 'confirm_stop': True})

    def mutations(self):
        return [wire for wire in self.sent if wire[2:4] in (b'\x52\xa1', b'\x43\x02', b'\x52\xa3', b'\x43\xff')]

    def test_prepare_is_read_only_apply_saves_before_stop_and_after_stop_and_verifies(self):
        prepared = self.prepare()
        self.assertEqual(self.mutations(), [])
        self.assertEqual(prepared['history']['count'], 3)
        self.assertFalse(prepared['will_restart'])
        self.assertEqual(self.receiver.resumed, 1)
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'done', self.jobs.status())
        changes = self.mutations()
        self.assertEqual(changes, [STOP, bytes.fromhex('2a124302dc05') + bytes(13) + b'#', SAVE, FINISH])
        self.assertNotIn(bytes.fromhex('2a0352a023'), self.sent)
        self.assertEqual(self.connections, 2)
        self.assertEqual(self.receiver.resumed, 2)
        report = self.workflow.status()['last_change']
        self.assertEqual(report['status'], 'verified'); self.assertEqual(len(report['histories']), 2)
        self.assertTrue(all(item['scope'] == 'full' for item in report['histories']))
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'], 1500)
        self.assertEqual(self.settings.latest('12345678')['values']['recording_code'], 5)
        self.assertEqual(self.history.snapshots()[0]['count'], 3)
        with self.assertRaises(ValueError):self.apply(prepared)

    def test_missing_confirmation_expiry_replaced_capture_and_restart_never_authorize_writes(self):
        prepared = self.prepare()
        for key in ('confirm_history_loss', 'confirm_stop'):
            value = {'token': prepared['token'], 'confirm_history_loss': True, 'confirm_stop': True}
            value[key] = 1
            with self.assertRaises(ValueError):self.workflow.apply(value)
        self.assertEqual(self.mutations(), [])
        self.workflow.pending['deadline'] = 0
        with self.assertRaises(ValueError):self.apply(prepared)
        self.saved = self.settings.latest('12345678'); prepared = self.prepare()
        self.settings.save('12345678', self.sample)
        with self.assertRaises(ValueError):self.apply(prepared)
        self.saved = self.settings.latest('12345678'); prepared = self.prepare()
        restarted = ConfigurationWorkflow(self.receiver, self.jobs, self.settings, self.history)
        with self.assertRaises(ValueError):restarted.apply({'token': prepared['token'], 'confirm_history_loss': True, 'confirm_stop': True})

    def test_failed_storage_or_changed_settings_never_send_stop_or_setter(self):
        prepared = self.prepare()
        with patch.object(self.history, 'publish', side_effect=OSError('synthetic disk')):
            self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        self.assertEqual(self.mutations(), [])
        self.assertEqual(self.workflow.status()['last_change']['status'], 'blocked')
        self.assertEqual(self.receiver.resumed, 2)
        self.saved = self.settings.latest('12345678'); prepared = self.prepare()
        self.payloads['device_info'] = b'Changed'.ljust(15, b'\xff')
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error'); self.assertEqual(self.mutations(), [])

    def test_uncertain_write_is_durable_single_use_and_never_retried_or_restarted(self):
        prepared = self.prepare(); self.fail_opcode = b'\x43\x02'
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        report = self.workflow.status()['last_change']
        self.assertEqual(report['status'], 'uncertain'); self.assertTrue(report['may_have_changed'])
        self.assertEqual(self.mutations()[0], STOP); self.assertEqual(len(self.mutations()), 2)
        self.assertEqual(self.receiver.resumed, 2)
        self.assertNotIn(SAVE, self.sent); self.assertNotIn(FINISH, self.sent)
        self.assertTrue((self.workflow.root / (report['id'] + '.csv')).read_text().find('2a124302dc05') >= 0)
        with self.assertRaises(ValueError):self.apply(prepared)

    def test_readback_mismatch_is_uncertain_even_after_positive_save_ack(self):
        prepared = self.prepare(); self.corrupt_readback = True
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        self.assertEqual(self.workflow.status()['last_change']['status'], 'uncertain')
        self.assertEqual(self.receiver.resumed, 2)

    def test_codec_limits_unknown_fields_and_reply_echo(self):
        for field in (2, 3, 4, 5, 7, 14):
            payloads = copy.deepcopy(self.payloads); raw = bytearray(payloads['log_settings']); raw[field] = 1; payloads['log_settings'] = bytes(raw)
            with self.assertRaises(ValueError):configuration_frames(payloads, {'record_interval_seconds': 1500})
        for seconds in (True, 0, 65536, 1500.0):
            with self.assertRaises(ValueError):configuration_frames(self.payloads, {'record_interval_seconds': seconds})
        frame = configuration_frames(self.payloads, {'record_interval_seconds': 1500})[0]
        configuration_reply(frame, bytes.fromhex('2643020123'))
        for reply in ('2643350123', '2643020523', '264302010023'):
            with self.assertRaises(ValueError):configuration_reply(frame, bytes.fromhex(reply))
        self.assertEqual(configuration_frames(self.payloads, {'name': 'Test'})[0][4:-1], b'Test'.ljust(15, b'\xff'))
        radio = configuration_frames(self.payloads, {'broadcast_interval_seconds': 1})[0]
        self.assertEqual(radio, bytes.fromhex('2a064335060a0023'))

    def test_stop_save_and_finish_failures_never_repeat_commands(self):
        for opcode, expected_count in ((b'\x52\xa1',1),(b'\x52\xa3',3),(b'\x43\xff',4)):
            with self.subTest(opcode=opcode):
                self.saved = self.settings.latest('12345678')
                # Each case starts from a new simulated physical logger state.
                self.payloads = copy.deepcopy(self.sample['payloads'])
                self.sent = []; self.fail_opcode = None
                prepared = self.prepare(); self.fail_opcode = opcode
                self.apply(prepared); self.jobs.worker.join(5)
                self.assertEqual(self.jobs.status()['state'], 'error')
                self.assertEqual(self.workflow.status()['last_change']['status'], 'uncertain')
                self.assertEqual(len(self.mutations()), expected_count)
                self.assertEqual(sum(wire[2:4] == opcode for wire in self.sent), 1)
                # A staged observation from a failed Save may differ from the reset fake.
                self.saved = self.settings.save('12345678', self.sample)

    def test_second_full_read_failure_leaves_stop_visible_but_never_sets_or_saves(self):
        prepared = self.prepare()
        publish = self.history.publish
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:raise OSError('synthetic post-stop disk failure')
            return publish(*args, **kwargs)
        with patch.object(self.history, 'publish', side_effect=fail_second):
            self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.mutations(), [STOP])
        self.assertEqual(self.workflow.status()['last_change']['status'], 'uncertain')
        self.assertEqual(self.receiver.resumed, 2)

    def test_wrong_advertising_identity_blocks_before_first_gatt_request(self):
        with patch('backend.linux.configuration.known_device', AsyncMock(return_value=SimpleNamespace(details={'props': {}}))):
            self.workflow.prepare({'base_capture': self.saved['capture'], 'changes': {'record_interval_seconds': 1500}})
            self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.workflow.status()['prepared'])
        self.assertEqual(self.receiver.resumed, 1)

    def test_cancel_or_selection_change_discards_preparation_without_writes(self):
        prepared = self.prepare()
        self.workflow.cancel({})
        with self.assertRaises(ValueError):self.apply(prepared)
        self.saved = self.settings.latest('12345678'); prepared = self.prepare()
        self.receiver.config['device'] = None
        self.assertIsNone(self.workflow.status()['prepared'])
        with self.assertRaises(ValueError):self.apply(prepared)
        self.assertEqual(self.mutations(), [])

    def test_getter_can_expose_committed_old_value_until_save_but_final_target_is_required(self):
        prepared = self.prepare(); self.deferred_setter = True
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'done', self.jobs.status())
        report = self.workflow.status()['last_change']
        self.assertEqual(report['precommit_visibility'], {'log_settings':'previous_visible'})
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'], 1500)
        self.assertEqual(len(self.mutations()), 4)

    def test_third_intermediate_value_is_saved_as_evidence_but_never_committed(self):
        prepared = self.prepare(); self.third_value = True
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        report = self.workflow.status()['last_change']
        self.assertEqual(report['status'], 'uncertain')
        self.assertTrue(report['staged_settings_capture'])
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'], 900)
        self.assertNotIn(SAVE, self.sent)
        self.assertNotIn(FINISH, self.sent)

    def test_old_value_after_save_ack_is_never_reported_as_success(self):
        prepared = self.prepare(); self.deferred_setter = True; self.ignore_save = True
        self.apply(prepared); self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'], 'error')
        self.assertEqual(self.workflow.status()['last_change']['status'], 'uncertain')
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'], 600)
        self.assertEqual(len(self.mutations()), 4)

    def test_already_stopped_device_is_not_stopped_again_and_full_history_is_still_required(self):
        raw=bytearray(self.payloads['log_status']);raw[3]=5;self.payloads['log_status']=bytes(raw)
        self.deferred_setter=True
        prepared=self.prepare()
        self.assertFalse(prepared['will_stop'])
        self.apply(prepared);self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertNotIn(STOP,self.sent)
        self.assertEqual(len(self.workflow.status()['last_change']['histories']),1)
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'],1500)

    def test_zero_summary_after_commit_verifies_parameters_without_claiming_stopped_state(self):
        prepared=self.prepare();self.final_status=bytes(8)
        self.apply(prepared);self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        self.assertEqual(self.jobs.status()['result']['kind'],'configuration-parameters-verified')
        report=self.workflow.status()['last_change']
        self.assertEqual(report['status'],'parameters_verified');self.assertFalse(report['recording_state_verified'])
        self.assertEqual(self.settings.latest('12345678')['values']['record_interval_seconds'],1500)

    def uncertain_after_finished_commit(self):
        prepared=self.prepare();self.final_status=b'\x01'*8
        self.apply(prepared);self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'error')
        self.assertEqual(self.workflow.status()['last_change']['status'],'uncertain')

    def test_read_only_reconciliation_checks_all_acknowledgements_and_never_repeats_writes(self):
        self.uncertain_after_finished_commit();before=list(self.mutations())
        self.payloads['log_status']=bytes(8)
        report=self.workflow.status()['last_change'];path=self.workflow.root/(report['id']+'.csv');raw=path.read_bytes()
        self.workflow.verify_last({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        report=self.workflow.status()['last_change'];self.assertTrue(report['reconciled_read_only'])
        self.assertEqual(report['status'],'parameters_verified')
        self.assertEqual(self.mutations(),before);self.assertEqual(path.read_bytes(),raw)

    def test_reconciliation_without_complete_acknowledgements_never_connects(self):
        prepared=self.prepare();self.fail_opcode=b'\x52\xa3'
        self.apply(prepared);self.jobs.worker.join(5)
        count=self.connections
        with self.assertRaises(ValueError):self.workflow.verify_last({})
        self.assertEqual(self.connections,count)

    def test_reconciliation_still_rejects_old_target_and_damaged_original(self):
        self.uncertain_after_finished_commit();before=list(self.mutations())
        self.payloads['log_status']=bytes(8);self.payloads['log_settings']=(600).to_bytes(2,'little')+bytes(13)
        self.workflow.verify_last({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'error');self.assertEqual(self.mutations(),before)
        report=self.workflow.status()['last_change']
        path=self.settings.root/'bt06-12345678'/report['staged_settings_capture'];path.write_bytes(b'corrupt')
        count=self.connections
        with self.assertRaises(ValueError):self.workflow.verify_last({})
        self.assertEqual(self.connections,count)

    def test_verified_postcommit_original_can_reconcile_without_any_new_bluetooth_request(self):
        prepared=self.prepare();self.final_status=bytes(8)
        self.apply(prepared);self.jobs.worker.join(5)
        connections=self.connections;sent=list(self.sent)
        self.workflow.verify_last({});self.jobs.worker.join(5)
        self.assertEqual(self.jobs.status()['state'],'done',self.jobs.status())
        report=self.workflow.status()['last_change']
        self.assertEqual(report['verification_source'],'stored_postcommit_capture')
        self.assertTrue(report['reconciled_read_only'])
        self.assertEqual(self.connections,connections);self.assertEqual(self.sent,sent)


if __name__ == '__main__':unittest.main()
