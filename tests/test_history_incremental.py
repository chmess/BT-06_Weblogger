import tempfile
import unittest
from pathlib import Path

from backend.common.bt06_gatt import ReadCommand, read_request, requested_range
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore, OVERLAP
from history_fixture import capture, range_capture


class IncrementalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temp.name) / 'history')
        self.seconds = [1700000000 + i * 600 for i in range(20)]
        self.base = self.publish(capture(self.seconds))

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, rows, **extra):
        return self.store.publish('12345678', **decode_capture(rows), **extra)

    def transfer(self, seconds=None, values=None):
        seconds = seconds or self.seconds + [self.seconds[-1] + 600, self.seconds[-1] + 1200]
        begin = self.seconds[-OVERLAP] - 1
        end = seconds[-1] + 1
        transfer = decode_capture(range_capture(seconds, begin, end, values))
        transfer['base_snapshot'] = self.base['id']
        return transfer

    def test_range_frames_are_bounded_and_fixed_read_only(self):
        wire = read_request(ReadCommand.SELECT_ALL_HISTORY, selection=(1000, 3000))
        self.assertEqual(wire.hex(), '2a0e6c00020000e8030000b80b000023')
        self.assertEqual(requested_range(wire), (1000, 3000))
        for invalid in ((0, 10), (10, 10), (20, 10), (True, 10), (10, 2**32), [10, 20]):
            with self.assertRaises(ValueError):
                read_request(ReadCommand.SELECT_ALL_HISTORY, selection=invalid)
        with self.assertRaises(ValueError):
            read_request(ReadCommand.LOG_SETTINGS, selection=(1, 10))
        with self.assertRaises(ValueError):
            requested_range(wire[:5] + b'\x01' + wire[6:])

    def test_appended_range_matches_full_import_and_repeats_without_copy(self):
        transfer = self.transfer()
        result = self.store.publish('12345678', **transfer)
        self.assertEqual(result['count'], 22)
        self.assertEqual(result['new_count'], 2)
        self.assertEqual(result['received_count'], OVERLAP + 2)
        self.assertEqual(result['transfer_scope'], 'range')
        self.assertFalse(result['full_read_verified'])
        rows = self.store.rows(result['logger'], result['id'])
        original = self.store.rows(self.base['logger'], self.base['id'])
        self.assertEqual([(r['GeraeteSekunden'],r['RohwerteHex']) for r in rows[:20]], [(r['GeraeteSekunden'],r['RohwerteHex']) for r in original])
        full = self.publish(capture(self.seconds + [self.seconds[-1] + 600, self.seconds[-1] + 1200]))
        self.assertTrue(full['duplicate'])
        self.assertEqual(result['id'], full['id'])
        self.assertEqual(full['last_transfer_scope'], 'full')
        self.assertTrue(self.store.publish('12345678', **transfer)['duplicate'])
        series = self.store.series()
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]['count'], 22)
        self.assertEqual(series[0]['member_count'], 2)
        self.assertEqual(self.store.incremental_base(result['logger'])['count'], 22)

    def test_no_new_values_requires_full_overlap_and_does_not_create_snapshot(self):
        transfer = self.transfer(self.seconds)
        result = self.store.publish('12345678', **transfer)
        self.assertTrue(result['duplicate'])
        self.assertEqual(result['new_count'], 0)
        self.assertEqual(result['received_count'], OVERLAP)
        self.assertEqual(result['last_transfer_scope'], 'range')
        self.assertEqual(len(self.store.snapshots()), 1)

    def test_overlap_changed_count_reset_or_missing_base_never_publish(self):
        changed = [bytes.fromhex('c8005802')] * 22
        changed[7] = bytes.fromhex('c9005802')
        mismatch = self.transfer(values=changed)
        count = self.transfer()
        count['full_metadata'] = (23).to_bytes(2,'little') + count['full_metadata'][2:]
        reset = self.transfer()
        reset['full_metadata'] = reset['full_metadata'][:2] + bytes(4) + reset['full_metadata'][6:]
        missing = self.transfer();missing['base_snapshot'] = None
        for transfer in (mismatch, count, reset, missing):
            with self.assertRaises(ValueError):
                self.store.publish('12345678', **transfer)
        self.assertEqual(len(self.store.snapshots()), 1)
        self.assertEqual(len(self.store.rows(self.base['logger'],self.base['id'])), 20)

    def test_divergent_series_are_not_merged_and_disable_automatic_base_choice(self):
        values = [bytes.fromhex('c9005802')] * 20
        second = self.publish(capture(self.seconds, values))
        heads = self.store.series()
        self.assertEqual(len(heads), 2)
        self.assertTrue(all(h['separate_series']==2 for h in heads))
        self.assertIsNone(self.store.incremental_base(self.base['logger']))
        # Changed CSV is never accepted from a warm series cache.
        path = next((self.store.root/second['logger']/second['id']).glob('*/*.csv'))
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(ValueError):
            self.store.series()

    def test_prefixes_with_repeated_time_remain_distinct_records(self):
        before = len(self.store.snapshots())
        times = self.seconds[:]
        times[-1] = times[-2]
        result = self.publish(capture(times))
        self.assertEqual(len(self.store.snapshots()), before + 1)
        self.assertEqual(len(self.store.rows(result['logger'],result['id'])), 20)
        self.assertEqual(len(self.store.series()), 2)


class IncrementalReaderTests(unittest.TestCase):
    def test_reader_downloads_range_or_keeps_verified_full_fallback(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from backend.common.bt06_gatt import SERVICE_UUID, TX_UUID, RX_UUID
        from backend.linux.history_reader import retrieve
        from test_history_jobs import config
        seconds=[1700000000+i*600 for i in range(22)]
        base={'snapshot':'a'*64,'count':20,'first':seconds[0],'last':seconds[19],
              'begin':seconds[4]-1,'overlap':16,'unit':'C','interval_seconds':600}
        for use_range,automatic,fresh in ((True,False,False),(False,False,False),(True,True,False),(False,True,False),(True,True,True)):
            selected_base=dict(base)
            if not use_range:selected_base['first']-=600
            rows=range_capture(seconds,base['begin'],seconds[-1]+1) if use_range else capture(seconds)
            wire={bytes.fromhex(rows[i]['DatenHex']):bytes.fromhex(rows[i+1]['DatenHex']) for i in range(len(rows)-1) if rows[i]['Richtung']=='TX'}
            stream_start=next(i for i,r in enumerate(rows) if r['Richtung']=='TX' and bytes.fromhex(r['DatenHex'])==read_request(ReadCommand.RECEIVE_HISTORY))+2
            chunks=[bytes.fromhex(r['DatenHex']) for r in rows[stream_start:]]
            sent=[]
            test_case=self
            class Client:
                def __init__(self,*args,**options):
                    test_case.assertEqual(options['timeout'],(8 if fresh else 35) if automatic else 45)
                    test_case.assertFalse(options['pair'])
                    tx=SimpleNamespace(properties=['write']);rx=SimpleNamespace(properties=['notify'])
                    service=SimpleNamespace(get_characteristic=lambda uuid:tx if uuid==TX_UUID else rx if uuid==RX_UUID else None)
                    self.services=SimpleNamespace(get_service=lambda uuid:service if uuid==SERVICE_UUID else None)
                async def connect(self):pass
                async def disconnect(self):pass
                async def start_notify(self,rx,callback):self.notify=callback
                async def stop_notify(self,rx):pass
                async def write_gatt_char(self,tx,raw,**kwargs):
                    sent.append(raw)
                    response=wire.get(raw)
                    if response is None:
                        if raw!=read_request(ReadCommand.DEVICE_CLOCK):raise AssertionError('Unknown request')
                        response=b'\x26\x72\x51\x01'+bytes([46,1,1,0,0,0])+b'\x23'
                    self.notify(None,response)
                    if raw==read_request(ReadCommand.RECEIVE_HISTORY):
                        for chunk in chunks:self.notify(None,chunk)
            with patch('backend.linux.history_reader.known_device',AsyncMock(return_value=SimpleNamespace(details={'bt06_fresh_discovery':fresh}))), patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakClient=Client)}):
                if automatic and not use_range:
                    with self.assertRaises(ValueError):asyncio.run(retrieve(config(),lambda *args,**kwargs:None,base=selected_base,automatic=True))
                    self.assertNotIn(read_request(ReadCommand.RECEIVE_HISTORY),sent)
                    continue
                transfer=asyncio.run(retrieve(config(),lambda *args,**kwargs:None,base=selected_base,automatic=automatic))
            self.assertEqual('selection' in transfer,use_range)
            self.assertEqual(int.from_bytes(transfer['metadata'][:2],'little'),18 if use_range else 22)
            self.assertEqual(sum(raw[:4]==bytes.fromhex('2a0e6c00') for raw in sent),2 if use_range else 1)


if __name__=='__main__':unittest.main()
