import csv
import json
import tempfile
import unittest
from pathlib import Path

from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore,OVERLAP
from history_fixture import capture,range_capture


class DeltaStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=HistoryStore(Path(self.temp.name)/'history')
        self.times=[1700000000+i*600 for i in range(20)]
        self.base=self.store.publish('12345678',**decode_capture(capture(self.times)))
    def tearDown(self):self.temp.cleanup()
    def append(self):
        self.times.append(self.times[-1]+600)
        begin=self.times[-1-OVERLAP]-1
        transfer=decode_capture(range_capture(self.times,begin,self.times[-1]+1))
        transfer['base_snapshot']=self.base['id']
        self.base=self.store.publish('12345678',**transfer)
        return self.base
    def stored_rows(self,meta):
        folder=self.store.root/meta['logger']/meta['id'];count=0
        for name in meta['files']:
            if name!='capture.csv':
                with (folder/name).open() as stream:count+=len(list(csv.DictReader(stream,delimiter=';')))
        return count
    def test_only_new_row_is_stored_and_old_row_ids_are_preserved(self):
        original=self.store.rows(self.base['logger'],self.base['id'])
        new=self.append();self.assertEqual(new['storage'],'delta');self.assertEqual(self.stored_rows(new),1)
        self.assertEqual(new['schema_version'],2)
        self.assertEqual(self.store.rows(new['logger'],new['id'])[:20],original)
        restarted=HistoryStore(self.store.root)
        self.assertEqual(len(restarted.rows(new['logger'],new['id'])),21)
        self.assertEqual(len(restarted.series()),1)
    def test_periodic_checkpoint_bounds_delta_chain_without_claiming_full_read(self):
        original=self.store.rows(self.base['logger'],self.base['id'])
        last=None
        for _ in range(35):last=self.append()
        snapshots=self.store.snapshots();checkpoints=[m for m in snapshots if m['storage']=='full']
        self.assertEqual(len(checkpoints),2)
        self.assertTrue(any(m['transfer_scope']=='range' and not m['full_read_verified'] for m in checkpoints))
        self.assertLess(last['delta_depth'],32)
        self.assertEqual(len(self.store.rows(last['logger'],last['id'])),55)
        self.assertEqual(self.store.rows(last['logger'],last['id'])[:20],original)
        self.assertEqual(len(self.store.series()),1)
        self.assertEqual(self.store.series()[0]['member_count'],36)
        self.assertLess(sum(self.stored_rows(meta) for meta in snapshots),150)
    def test_corrupt_or_missing_base_blocks_read_and_duplicate_acknowledgement(self):
        old=self.base;new=self.append();folder=self.store.root/old['logger']/old['id']
        path=next(folder.glob('*/*.csv'));path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(ValueError):self.store.rows(new['logger'],new['id'])
        with self.assertRaises(ValueError):self.store.series()
    def test_legacy_full_snapshot_remains_readable(self):
        path=self.store.root/self.base['logger']/self.base['id']/'manifest.json'
        meta=json.loads(path.read_text());meta['schema_version']=1
        for key in ('storage','delta_depth'):meta.pop(key)
        path.write_text(json.dumps(meta))
        self.assertEqual(len(self.store.rows(meta['logger'],meta['id'])),20)
        self.assertEqual(len(self.store.series()),1)


if __name__=='__main__':unittest.main()
