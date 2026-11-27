import csv
import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.common.live_store import LIVE_FIELDS
from backend.common.storage_diagnostics import inspect_live


class StorageDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'bt06-12345678/2026/2026-01.csv'

    def write(self,rows=None,path=None):
        path=path or self.path;path.parent.mkdir(parents=True,exist_ok=True)
        base=dict.fromkeys(LIVE_FIELDS,'')
        base.update(Schema='2',DatensatzID='test-1',Zeitstempel='2026-01-01T00:00:00+00:00',Temperatur='20,00',Feuchte='80,00',Quelle='BLE-Advertising',Zeitbasis='Host-Empfang')
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,LIVE_FIELDS,delimiter=';',lineterminator='\n');writer.writeheader();writer.writerows(rows if rows is not None else [base])
        return base

    def test_good_file_and_empty_are_distinct_and_do_not_modify_files(self):
        self.assertEqual(inspect_live(self.root)['state'],'empty')
        self.write();original=self.path.read_bytes();modified=self.path.stat().st_mtime_ns
        result=inspect_live(self.root)
        self.assertEqual(result['state'],'ok');self.assertTrue(result['complete'])
        self.assertEqual(result['files_checked'],1);self.assertEqual(result['rows_checked'],1)
        self.assertEqual(self.path.read_bytes(),original);self.assertEqual(self.path.stat().st_mtime_ns,modified)

    def test_damage_is_reported_without_raw_payload_or_repair(self):
        for content in (b'wrong;header\n',b'private-raw-value',b'\xff\n'):
            self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_bytes(content)
            result=inspect_live(self.root)
            self.assertEqual(result['state'],'error');self.assertEqual(result['files_checked'],0)
            self.assertNotIn('private-raw-value',str(result));self.assertEqual(self.path.read_bytes(),content)

    def test_duplicate_ids_time_order_month_and_nonfinite_values(self):
        row=self.write()
        cases=[row,{**row,'DatensatzID':'other','Zeitstempel':'2025-01-01T00:01:00+00:00'},
               {**row,'DatensatzID':'other','Temperatur':'nan'}, {**row,'DatensatzID':'other','Feuchte':'101'},
               {**row,'DatensatzID':'other','Zeitstempel':'2026-01-01T00:00:00+00:00'},
               {**row,'DatensatzID':'other','Schema':'1'}]
        for bad in cases:
            self.write([row,bad]);self.assertEqual(inspect_live(self.root)['state'],'error')

    def test_busy_file_is_skipped_without_waiting_or_claiming_success(self):
        self.write()
        with self.path.open('rb') as writer:
            fcntl.flock(writer,fcntl.LOCK_EX)
            result=inspect_live(self.root)
        self.assertEqual(result['state'],'partial');self.assertFalse(result['complete'])
        self.assertEqual(result['files_checked'],0);self.assertIn('geschrieben',result['skipped'][0]['reason'])

    def test_byte_row_time_and_file_limits_remain_partial(self):
        row=self.write();self.write([row,{**row,'DatensatzID':'other','Zeitstempel':'2026-01-01T00:01:00+00:00'}])
        for limit in ({'max_bytes':1},{'max_rows':1},{'max_seconds':0},{'max_files':0}):
            result=inspect_live(self.root,**limit)
            self.assertEqual(result['state'],'partial');self.assertFalse(result['complete']);self.assertEqual(result['files_checked'],0)
        self.assertEqual(inspect_live(self.root,max_rows=2)['state'],'ok')

    def test_ignores_other_sources_and_rejects_symbolic_links(self):
        history=self.root/'history/bt06-12345678/2026/2026-01.csv';history.parent.mkdir(parents=True);history.write_text('not a host file')
        self.assertEqual(inspect_live(self.root)['state'],'empty')
        self.path.parent.mkdir(parents=True);self.path.symlink_to(history)
        result=inspect_live(self.root);self.assertEqual(result['state'],'error');self.assertIn('Link',result['errors'][0]['reason'])

    def test_unreadable_directory_is_not_reported_as_empty_or_healthy(self):
        self.write()
        with patch('backend.common.storage_diagnostics.os.scandir',side_effect=PermissionError('private raw detail')):
            result=inspect_live(self.root)
        self.assertEqual(result['state'],'error');self.assertFalse(result['complete'])
        self.assertNotIn('private raw detail',str(result))
