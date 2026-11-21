import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
from backend.common.bt06_gatt import ProtocolError
from history_fixture import capture


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temp.name) / 'data/history')
        self.transfer = decode_capture(capture())

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, transfer=None):
        return self.store.publish('12345678', **(transfer or self.transfer))

    def test_duplicate_is_idempotent_after_restart_and_original_time_is_preserved(self):
        first = self.publish()
        rows = self.store.rows(first['logger'], first['id'])
        self.assertEqual(len(rows), 3)
        self.assertEqual({r['Zeitstempel'] for r in rows}, {''})
        self.assertEqual({r['Batterie'] for r in rows}, {''})
        self.assertFalse(first['clock_verified'])
        self.store = HistoryStore(self.store.root)
        second = self.publish()
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['imported_at'], second['imported_at'])
        self.assertEqual(len(self.store.snapshots()), 1)
        self.assertEqual(self.store.rows(first['logger'], first['id']), rows)

    def test_overlapping_or_changed_histories_stay_separate(self):
        first = self.publish()
        changed = decode_capture(capture(values=[bytes.fromhex('c9005802')] * 3))
        second = self.publish(changed)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(len(self.store.snapshots()), 2)
        self.assertEqual(len(self.store.rows(first['logger'], first['id'])), 3)

    def test_failure_before_publication_keeps_old_snapshot_and_retry_succeeds(self):
        first = self.publish()
        changed = decode_capture(capture(values=[bytes.fromhex('c9005802')] * 3))
        with patch('backend.common.history_store.os.rename', side_effect=OSError('synthetic full disk')):
            with self.assertRaises(OSError):
                self.publish(changed)
        self.assertEqual([s['id'] for s in self.store.snapshots()], [first['id']])
        self.assertTrue(list(self.store.root.glob('*/.pending-*')))
        self.publish(changed)
        self.assertEqual(len(self.store.snapshots()), 2)

    def test_corruption_blocks_duplicate_acknowledgement_and_read(self):
        first = self.publish()
        path = next((self.store.root / first['logger'] / first['id']).glob('*/*.csv'))
        path.write_bytes(path.read_bytes()[:-1])
        damaged = path.read_bytes()
        with self.assertRaises(ValueError):
            self.publish()
        with self.assertRaises(ValueError):
            self.store.rows(first['logger'], first['id'])
        self.assertEqual(path.read_bytes(), damaged)

    def test_month_split_repeated_time_backwards_clock_and_range(self):
        from datetime import datetime, timezone
        first = int(datetime(2024, 3, 31, 23, 50, tzinfo=timezone.utc).timestamp())
        result = self.publish(decode_capture(capture(seconds=[first, first, first + 600])))
        self.assertEqual(len([f for f in result['files'] if f != 'capture.csv']), 2)
        self.assertEqual(len(self.store.rows(result['logger'], result['id'])), 3)
        self.assertEqual(len(list(self.store.filtered_rows(result['logger'], result['id'], '2024-04-01T00:00:00+00:00'))), 1)
        reverse = self.publish(decode_capture(capture(seconds=[first + 1200, first + 600, first])))
        self.assertFalse(reverse['monotonic'])
        self.assertEqual(len(self.store.rows(reverse['logger'], reverse['id'])), 3)
        with self.assertRaises(ValueError):
            list(self.store.chart_rows(reverse['logger'], reverse['id']))

    def test_incomplete_and_metadata_mismatch_never_publish(self):
        for transfer in ({**self.transfer, 'chunks': self.transfer['chunks'][:-1]},
                         {**self.transfer, 'metadata': self.transfer['metadata'][:2] + bytes(8)}):
            with self.assertRaises(ValueError):
                self.publish(transfer)
        self.assertEqual(self.store.snapshots(), [])

    def test_capture_rejects_unknown_writes_and_missing_ack_or_end(self):
        rows = capture()
        for invalid in ([{**rows[0], 'DatenHex': '2a034c0223'}] + rows[1:], rows[:-4], rows[1:]):
            with self.assertRaises(ValueError):
                self.publish(decode_capture(invalid))
        with self.assertRaises(ValueError):
            self.store.metadata('bt06-12345678', '../escape')
        self.assertEqual(self.store.snapshots(), [])


if __name__ == '__main__':
    unittest.main()
