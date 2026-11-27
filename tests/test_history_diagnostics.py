import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore,OVERLAP
from backend.common.history_diagnostics import inspect_history
from history_fixture import capture,range_capture


class HistoryDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=HistoryStore(Path(self.temp.name)/'history');self.times=[1700000000+i*600 for i in range(20)]
        self.base=self.store.publish('12345678',**decode_capture(capture(self.times)))

    def inspect(self,meta=None,**limits):
        meta=meta or self.base
        return inspect_history(self.store,meta['logger'],meta['id'],**limits)

    def manifest(self,meta=None):
        meta=meta or self.base;return self.store.root/meta['logger']/meta['id']/'manifest.json'

    def extend(self):
        self.times.append(self.times[-1]+600)
        transfer=decode_capture(range_capture(self.times,self.times[-1-OVERLAP]-1,self.times[-1]+1));transfer['base_snapshot']=self.base['id']
        return self.store.publish('12345678',**transfer)

    def test_full_and_delta_chain_verify_without_modifying_originals_or_clock(self):
        newer=self.extend();before={path:(path.read_bytes(),path.stat().st_mtime_ns) for path in self.store.root.rglob('*') if path.is_file()}
        result=self.inspect(newer)
        self.assertEqual(result['state'],'ok');self.assertTrue(result['complete']);self.assertFalse(result['clock_verified'])
        self.assertEqual(result['snapshots_checked'],2);self.assertEqual(result['files_checked'],6);self.assertEqual(result['rows_checked'],21)
        self.assertEqual(result['row_work_planned'],41)
        for path,(content,mtime) in before.items():self.assertEqual(path.read_bytes(),content);self.assertEqual(path.stat().st_mtime_ns,mtime)
        self.assertEqual(self.inspect()['state'],'ok')

    def test_tampered_or_missing_base_is_an_error_without_repair(self):
        newer=self.extend();path=self.manifest().parent/'capture.csv';content=path.read_bytes();path.write_bytes(content+b'broken')
        result=self.inspect(newer);self.assertEqual(result['state'],'error');self.assertFalse(result['complete']);self.assertEqual(result['rows_checked'],0)
        self.assertEqual(path.read_bytes(),content+b'broken');path.unlink()
        self.assertEqual(self.inspect(newer)['state'],'error')

    def test_invalid_manifest_and_inconsistent_chain_depth_are_errors(self):
        newer=self.extend();path=self.manifest(newer);meta=json.loads(path.read_text());meta['delta_depth']=0;path.write_text(json.dumps(meta))
        self.assertEqual(self.inspect(newer)['state'],'error')
        path.write_text('{invalid private raw bytes')
        result=self.inspect(newer);self.assertEqual(result['state'],'error');self.assertNotIn('private raw',str(result))

    def test_work_size_file_and_time_limits_do_not_claim_complete(self):
        for limit in ({'max_row_work':1},{'max_bytes':1},{'max_files':1},{'max_seconds':0}):
            result=self.inspect(**limit)
            self.assertEqual(result['state'],'partial');self.assertFalse(result['complete']);self.assertEqual(result['files_checked'],0)
        with patch.object(self.store,'rows',side_effect=AssertionError('must not read content')):
            self.assertEqual(self.inspect(max_row_work=1)['state'],'partial')

    def test_symbolic_links_and_invalid_identifiers_are_rejected(self):
        path=self.manifest().parent/'capture.csv';original=path.read_bytes();path.unlink();other=Path(self.temp.name)/'outside.csv';other.write_bytes(original);path.symlink_to(other)
        self.assertEqual(self.inspect()['state'],'error')
        with self.assertRaises(ValueError):inspect_history(self.store,'../private',self.base['id'])
        with self.assertRaises(ValueError):inspect_history(self.store,self.base['logger'],'../private')

    def test_busy_store_is_partial_and_logical_verification_failure_is_visible(self):
        class Busy:
            def acquire(self,blocking=False):return False
        with patch.object(self.store,'lock',Busy()):self.assertEqual(self.inspect()['state'],'partial')
        with patch.object(self.store,'rows',side_effect=ValueError('private raw detail')):
            result=self.inspect();self.assertEqual(result['state'],'error');self.assertNotIn('private raw detail',str(result))
