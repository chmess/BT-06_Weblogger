import csv
import json
import tempfile
import unittest
from pathlib import Path
from backend.common.simulation import generate
from backend.common.simulation_diagnostics import inspect_simulation
from backend.common.storage import FIELDS


class SimulationDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.meta=generate(self.root,{'days':1,'interval_minutes':60,'end':'2026-10-25T20:00:00+00:00'})
        self.folder=self.root/self.meta['id']

    def inspect(self,**limits):return inspect_simulation(self.root,self.meta['id'],**limits)

    def path(self):return next((self.folder/self.meta['loggers'][0]['id']).glob('*/*.csv'))

    def rewrite(self,change):
        path=self.path()
        with path.open() as stream:rows=list(csv.DictReader(stream,delimiter=';'))
        change(rows)
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,FIELDS,delimiter=';',lineterminator='\n');writer.writeheader();writer.writerows(rows)

    def test_daily_and_gapped_dst_runs_match_manifest_without_modification(self):
        before={path:(path.read_bytes(),path.stat().st_mtime_ns) for path in self.folder.rglob('*') if path.is_file()}
        result=self.inspect();self.assertEqual(result['state'],'ok');self.assertTrue(result['complete']);self.assertFalse(result['checksums_available'])
        self.assertEqual(result['rows_checked'],sum(item['count'] for item in self.meta['loggers']));self.assertEqual(result['loggers_checked'],3)
        for path,(content,mtime) in before.items():self.assertEqual(path.read_bytes(),content);self.assertEqual(path.stat().st_mtime_ns,mtime)
        gap=generate(self.root,{'days':1,'interval_minutes':60,'scenario':'gaps','end':'2026-10-25T20:00:00+00:00'})
        self.assertEqual(inspect_simulation(self.root,gap['id'])['state'],'ok')

    def test_wrong_source_identifier_time_grid_and_values_are_errors(self):
        original=self.path().read_bytes()
        for field,value in [('Quelle','BLE-Advertising'),('DatensatzID','bad'),('Zeitstempel','2026-10-01T00:00:00+00:00'),('Temperatur','nan'),('Feuchte','101')]:
            self.path().write_bytes(original);self.rewrite(lambda rows:rows[0].update({field:value}))
            result=self.inspect();self.assertEqual(result['state'],'error');self.assertFalse(result['complete'])
            self.assertNotIn('BLE-Advertising',str(result))
        self.path().write_bytes(original)

    def test_missing_rows_broken_tail_and_manifest_are_not_repaired(self):
        path=self.path();original=path.read_bytes();self.rewrite(lambda rows:rows.pop())
        self.assertEqual(self.inspect()['state'],'error')
        path.write_bytes(original[:-1]);self.assertEqual(self.inspect()['state'],'error');self.assertEqual(path.read_bytes(),original[:-1])
        path.write_bytes(original);manifest=self.folder/'manifest.json';meta=json.loads(manifest.read_text());meta['created_at']=None;manifest.write_text(json.dumps(meta))
        self.assertEqual(self.inspect()['state'],'error')
        manifest.write_text('private raw invalid bytes');result=self.inspect();self.assertEqual(result['state'],'error');self.assertNotIn('private raw',str(result))

    def test_limits_remain_partial(self):
        for limit in ({'max_files':1},{'max_bytes':1},{'max_rows':1},{'max_seconds':0}):
            result=self.inspect(**limit);self.assertEqual(result['state'],'partial');self.assertFalse(result['complete'])

    def test_symbolic_links_unexpected_files_and_path_traversal_are_rejected(self):
        path=self.path();original=path.read_bytes();target=self.root/'outside.csv';target.write_bytes(original);path.unlink();path.symlink_to(target)
        self.assertEqual(self.inspect()['state'],'error');path.unlink();path.write_bytes(original)
        (self.folder/'unexpected.txt').write_text('not generated')
        self.assertEqual(self.inspect()['state'],'error')
        with self.assertRaises(ValueError):inspect_simulation(self.root,'../private')
