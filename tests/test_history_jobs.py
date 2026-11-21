import asyncio
import threading
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.common.bt06_gatt import SERVICE_UUID, TX_UUID, RX_UUID, ReadCommand, read_request
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
from backend.linux.history_jobs import HistoryJobs
from backend.linux.history_reader import retrieve
from backend.linux.receiver import Receiver
from backend.linux.ble_jobs import BusyError
from history_fixture import capture


def config(enabled=True):
    return {'schema_version': 1, 'enabled': enabled, 'device': {'id':'12345678','address':'AA:BB:CC:DD:EE:FF','firmware':'2.05','name':'Synthetic logger'}, 'adapter':'hci0','save_interval_seconds':60}


class FakeReceiver:
    validate = staticmethod(Receiver.validate)
    def __init__(self, enabled=True):
        self.config = config(enabled)
        self.radio_lock = threading.Lock()
        if enabled:
            self.radio_lock.acquire()
        self.resumed = 0
    def status(self):
        return {'config': self.config}
    def stop(self, persist=True):
        assert persist is False
        if self.radio_lock.locked():
            self.radio_lock.release()
    def start(self):
        if not self.radio_lock.acquire(blocking=False):
            raise BusyError('synthetic busy')
        self.resumed += 1


class HistoryJobTests(unittest.TestCase):
    def test_verified_reader_uses_no_pairing_and_only_read_allowlist(self):
        rows = capture()
        operations = {}
        for index, row in enumerate(rows):
            if row['Richtung'] == 'TX':
                operations[bytes.fromhex(row['DatenHex'])] = bytes.fromhex(rows[index + 1]['DatenHex'])
        wire = [bytes.fromhex(r['DatenHex']) for r in rows[8:]]
        calls = []
        class Client:
            def __init__(self, target, **options):
                calls.append(('client', options))
                tx=SimpleNamespace(uuid=TX_UUID,properties=['write'])
                rx=SimpleNamespace(uuid=RX_UUID,properties=['notify'])
                service=SimpleNamespace(get_characteristic=lambda uuid:tx if uuid==TX_UUID else rx if uuid==RX_UUID else None)
                self.services=SimpleNamespace(get_service=lambda uuid:service if uuid==SERVICE_UUID else None)
            async def connect(self):
                calls.append(('connect', {}))
            async def start_notify(self, rx, callback):
                self.notify = callback
            async def write_gatt_char(self, tx, raw, **options):
                self_test.assertIn(raw, {read_request(command) for command in ReadCommand})
                self_test.assertTrue(options['response'])
                if raw not in operations:
                    command = ReadCommand.DEVICE_CLOCK if raw==read_request(ReadCommand.DEVICE_CLOCK) else None
                    self_test.assertIsNotNone(command)
                    response=b'\x26'+command.value+b'\x01'+bytes([44,3,31,0,30,0])+b'\x23'
                else:
                    response=operations[raw]
                self.notify(None,response)
                if raw==read_request(ReadCommand.RECEIVE_HISTORY):
                    for chunk in wire:self.notify(None,chunk)
            async def stop_notify(self, rx):pass
            async def disconnect(self):calls.append(('disconnect', {}))
        self_test=self
        with patch('backend.linux.history_reader.known_device', AsyncMock(return_value=object())), patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakClient=Client)}):
            transfer=asyncio.run(retrieve(config(),lambda *args,**kwargs:None))
        self.assertEqual(calls[0][1]['pair'],False)
        self.assertEqual(calls[-1][0],'disconnect')
        self.assertEqual(transfer['metadata'],decode_capture(rows)['metadata'])

    def test_success_error_and_save_failure_restore_previous_receive_intent(self):
        async def success(*args):return decode_capture(capture())
        async def failure(*args):raise TimeoutError()
        for enabled in (True,False):
            for mode in ('success','timeout','disk'):
                with self.subTest(enabled=enabled,mode=mode), tempfile.TemporaryDirectory() as temp:
                    receiver=FakeReceiver(enabled)
                    store=HistoryStore(Path(temp)/'history')
                    job=HistoryJobs(receiver,store)
                    with patch('backend.linux.history_jobs.retrieve',success if mode!='timeout' else failure), patch.object(store,'publish',side_effect=OSError('synthetic disk')) if mode=='disk' else nullcontext():
                        job.start({});job.worker.join(3)
                    self.assertFalse(job.worker.is_alive())
                    self.assertEqual(job.status()['state'],'done' if mode=='success' else 'error')
                    self.assertEqual(receiver.resumed,1 if enabled else 0)
                    self.assertEqual(receiver.config['enabled'],enabled)

    def test_busy_rejected_and_shutdown_cancels_without_resume(self):
        ready=threading.Event()
        async def waiting(*args):
            ready.set();await asyncio.sleep(100)
        with tempfile.TemporaryDirectory() as temp:
            receiver=FakeReceiver()
            job=HistoryJobs(receiver,HistoryStore(Path(temp)/'history'))
            with patch('backend.linux.history_jobs.retrieve',waiting):
                job.start({});self.assertTrue(ready.wait(2))
                with self.assertRaises(BusyError):job.start({})
                job.close()
            self.assertFalse(job.worker.is_alive())
            self.assertEqual(receiver.resumed,0)
            self.assertEqual(job.status()['state'],'error')
            self.assertFalse(receiver.radio_lock.locked())


if __name__=='__main__':unittest.main()
