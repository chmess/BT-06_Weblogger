import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

from backend.common.device_settings import DeviceSettingsStore,decode_settings,settings_capture,memory_estimate
from backend.common.bt06_gatt import SERVICE_UUID,TX_UUID,RX_UUID,read_request
from backend.common.history_store import HistoryStore
from backend.linux.history_jobs import HistoryJobs
from backend.linux.settings_reader import retrieve_settings
from settings_fixture import observation
from test_history_jobs import FakeReceiver,config


class SettingsTests(unittest.TestCase):
    def test_nominal_memory_window_is_not_claimed_as_free_remaining_time(self):
        estimate=memory_estimate(1500)
        self.assertEqual(estimate['capacity_records'],32000)
        self.assertEqual(estimate['nominal_seconds'],48000000)
        self.assertAlmostEqual(estimate['nominal_days'],555.5555555555555)
        self.assertIsNone(estimate['remaining_seconds'])
        self.assertIsNone(memory_estimate(None));self.assertIsNone(memory_estimate(True))
    def test_only_verified_fields_are_decoded_and_mode_stays_unknown(self):
        result=decode_settings(observation()['payloads']);v=result['values']
        self.assertEqual(result['decode_errors'],{})
        self.assertEqual(v['name'],'Demo BT06');self.assertEqual(v['record_interval_seconds'],1230)
        self.assertEqual(v['broadcast_interval_seconds'],12.5);self.assertEqual(v['transmit_power_dbm'],0)
        self.assertIsNone(v['long_range']);self.assertEqual(v['transmit_rate_code'],255)
        self.assertEqual(v['temperature_alarm']['low']['limit'],-4.5)
        self.assertTrue(v['temperature_alarm']['low']['enabled']);self.assertFalse(v['temperature_alarm']['high']['enabled'])
        self.assertEqual(v['humidity_alarm']['high']['limit'],65)
        self.assertNotIn('start_delay',v);self.assertIn('start_delay',result['unverified'])
        self.assertFalse(v['clock_verified'])

    def test_unknown_formats_never_produce_defaults(self):
        payloads=observation()['payloads']
        payloads.update(device_info=b'invalid',broadcast_settings=bytes([99,0,0]),log_settings=bytes(15),temperature_alarm=b'invalid')
        result=decode_settings(payloads)
        for key in ('device_info','broadcast_settings','log_settings','temperature_alarm'):self.assertIn(key,result['decode_errors'])
        for key in ('name','broadcast_interval_seconds','record_interval_seconds','temperature_alarm'):self.assertNotIn(key,result['values'])

    def test_store_verifies_original_and_preserves_previous_on_write_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            store=DeviceSettingsStore(Path(temp)/'settings');sample=observation()
            first=store.save('12345678',sample);self.assertEqual(store.latest('12345678'),first)
            self.assertEqual(first['observed_at'],sample['capture'][-1]['Hostzeit'])
            with patch('backend.common.device_settings.atomic_json',side_effect=OSError('synthetic disk')):
                with self.assertRaises(OSError):store.save('12345678',sample)
            self.assertEqual(store.latest('12345678'),first)
            path=store.root/'bt06-12345678'/'latest.json';data=json.loads(path.read_text());data['values']['record_interval_seconds']=1;path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):store.latest('12345678')

    def test_capture_rejects_setters_and_missing_replies(self):
        sample=observation()
        for rows in (sample['capture'][:-1],[{**sample['capture'][0],'DatenHex':'2a03433523'}]+sample['capture'][1:],sample['capture'][1:]):
            with self.assertRaises(ValueError):settings_capture(rows)
        rejected=observation('transmit_rate')
        payloads,errors,_=settings_capture(rejected['capture'])
        self.assertNotIn('transmit_rate',payloads);self.assertEqual(errors['transmit_rate']['status'],5)

    def test_reader_never_sends_setters_and_disconnects(self):
        sample=observation('transmit_rate');rows=sample['capture'];sent=[];closed=[]
        answers={bytes.fromhex(rows[i]['DatenHex']):bytes.fromhex(rows[i+1]['DatenHex']) for i in range(0,len(rows),2)}
        class Client:
            def __init__(self,target,**options):
                test.assertFalse(options['pair'])
                tx=SimpleNamespace(properties=['write']);rx=SimpleNamespace(properties=['notify'])
                service=SimpleNamespace(get_characteristic=lambda uuid:tx if uuid==TX_UUID else rx if uuid==RX_UUID else None)
                self.services=SimpleNamespace(get_service=lambda uuid:service if uuid==SERVICE_UUID else None)
            async def connect(self):pass
            async def start_notify(self,rx,notify):self.notify=notify
            async def write_gatt_char(self,tx,raw,**options):
                test.assertIn(raw,answers);sent.append(raw);self.notify(None,answers[raw])
            async def stop_notify(self,rx):pass
            async def disconnect(self):closed.append(True)
        test=self
        with patch('backend.linux.settings_reader.known_device',AsyncMock(return_value=object())),patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakClient=Client)}):
            result=asyncio.run(retrieve_settings(config(),lambda *args,**kwargs:None))
        self.assertEqual(len(sent),8);self.assertTrue(closed)
        self.assertEqual(result['payloads'],sample['payloads']);self.assertEqual(result['read_errors'],sample['read_errors'])

    def test_shared_job_restores_receiver_without_creating_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);receiver=FakeReceiver();history=HistoryStore(root/'history');settings=DeviceSettingsStore(root/'settings')
            jobs=HistoryJobs(receiver,history,settings)
            with patch('backend.linux.history_jobs.retrieve_settings',AsyncMock(return_value=observation())):
                jobs.start({'mode':'settings'});jobs.worker.join(3)
            self.assertEqual(jobs.status()['state'],'done');self.assertEqual(receiver.resumed,1)
            self.assertEqual(jobs.status()['result']['kind'],'device-settings');self.assertEqual(history.snapshots(),[])

    def test_zero_summary_is_known_but_never_guesses_recording_or_empty_history(self):
        sample=observation();sample['payloads']['log_status']=bytes(8)
        result=decode_settings(sample['payloads'])
        self.assertEqual(result['decode_errors'],{})
        self.assertEqual(result['values']['status_variant'],'zero_summary')
        self.assertIsNone(result['values']['recording_code'])
        self.assertNotIn('history_count',result['values'])
        for raw in (bytes(7),bytes(9),b'\x01'+bytes(7)):
            sample['payloads']['log_status']=raw
            self.assertIn('log_status',decode_settings(sample['payloads'])['decode_errors'])

    def test_legacy_zero_summary_is_upgraded_from_verified_original_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp:
            sample=observation();sample['payloads']['log_status']=bytes(8)
            for row in sample['capture']:
                if row['Richtung']=='RX' and row['DatenHex'].startswith('264c0101'):
                    row['DatenHex']=(bytes.fromhex('264c0101')+bytes(8)+b'#').hex()
            store=DeviceSettingsStore(Path(temp)/'settings');saved=store.save('12345678',sample)
            path=store.root/'bt06-12345678'/'latest.json'
            legacy=json.loads(path.read_text());legacy.pop('decoder_version')
            for key in ('recording','recording_code','status_variant'):legacy['values'].pop(key)
            legacy['decode_errors']={'log_status':'Antwortformat oder Feldwert nicht verifiziert.'}
            path.write_text(json.dumps(legacy));before=path.read_bytes()
            upgraded=store.latest('12345678')
            self.assertEqual(upgraded['values'],saved['values']);self.assertEqual(upgraded['decode_errors'],{})
            self.assertEqual(path.read_bytes(),before)
            legacy['values']['name']='Tampered';path.write_text(json.dumps(legacy))
            with self.assertRaises(ValueError):store.latest('12345678')


if __name__=='__main__':unittest.main()
