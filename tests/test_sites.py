import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from backend.common.sites import SiteStore
from backend.common.live_store import LiveStore
from backend.common.bt06 import decode
from test_live import frame

CRITERIA={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':60,'surface_mode':'none','surface_value':None}


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.store=SiteStore(self.root/'config/sites.json',clock=lambda:self.now)

    def tick(self):self.now+=timedelta(seconds=1)

    def save(self,name='Ort A',id=None,**changes):
        self.tick();value={'name':name,'room':'Testraum','description':'Synthetischer Standort','criteria':copy.deepcopy(CRITERIA)};value.update(changes)
        return self.store.save({'revision':self.store.snapshot()['revision'],'id':id,'values':value})['site']

    def assign(self,logger,site_id):
        self.tick();self.store.assign({'revision':self.store.snapshot()['revision'],'logger':logger,'site_id':site_id})
        return self.now.isoformat()

    def test_create_update_persistence_and_private_permissions(self):
        site=self.save();original=site['id'];updated=self.save('Ort umbenannt',id=original)
        self.assertEqual(updated['id'],original)
        reopened=SiteStore(self.store.path)
        self.assertEqual(reopened.snapshot()['sites'][0]['name'],'Ort umbenannt')
        self.assertEqual(self.store.path.stat().st_mode&0o777,0o600)

    def test_logger_move_retains_old_assignment_and_uses_exclusive_end(self):
        a=self.save('A');b=self.save('B');first=self.assign('bt06-12345678',a['id']);second=self.assign('bt06-12345678',b['id'])
        self.assertEqual(self.store.resolve('bt06-12345678',first)['site_id'],a['id'])
        self.assertEqual(self.store.resolve('bt06-12345678',second)['site_id'],b['id'])
        history=self.store.history()['assignments'];self.assertEqual(len(history),2)
        self.assertEqual(history[1]['end'],second)
        end=self.assign('bt06-12345678',None);self.assertIsNone(self.store.resolve('bt06-12345678',end))
        self.assertEqual(self.store.resolve('bt06-12345678',first)['site_snapshot']['name'],'A')

    def test_replacing_logger_closes_both_conflicting_intervals(self):
        a=self.save('A');b=self.save('B');self.assign('bt06-12345678',a['id']);self.assign('bt06-23456789',b['id'])
        at=self.assign('bt06-12345678',b['id'])
        self.assertIsNone(self.store.resolve('bt06-23456789',at))
        self.assertEqual(len(self.store.snapshot()['active_assignments']),1)
        self.assertEqual(self.store.snapshot()['assignment_count'],3)

    def test_site_edit_versions_active_assignment_and_old_criteria(self):
        site=self.save('Alt');old=self.assign('bt06-12345678',site['id'])
        self.save('Neu',id=site['id'],criteria={**CRITERIA,'air_threshold':65})
        self.assertEqual(self.store.resolve('bt06-12345678',old)['site_snapshot']['name'],'Alt')
        latest=self.store.resolve('bt06-12345678',self.now.isoformat())['site_snapshot']
        self.assertEqual(latest['name'],'Neu');self.assertEqual(latest['criteria']['air_threshold'],65)
        self.assertEqual(self.store.snapshot()['assignment_count'],2)

    def test_new_live_rows_keep_site_id_and_old_originals_unchanged(self):
        live=LiveStore(self.root/'data',self.store);reading=decode(frame()).json()
        before=self.now.isoformat();live.append(reading,-50,before)
        a=self.save('A');self.assign('bt06-12345678',a['id']);self.tick();middle=self.now.isoformat();live.append(reading,-50,middle)
        b=self.save('B');self.assign('bt06-12345678',b['id']);self.tick();live.append(reading,-50,self.now.isoformat())
        rows=list(live.rows('bt06-12345678'))
        self.assertEqual([row['Messstelle'] for row in rows],['bt06-12345678',a['id'],b['id']])
        self.assertEqual(self.store.resolve('bt06-12345678',middle)['site_id'],a['id'])

    def test_stale_revision_backdating_and_duplicate_assignment_are_rejected(self):
        site=self.save();self.assign('bt06-12345678',site['id']);before=self.store.path.read_bytes()
        with self.assertRaises(ValueError):self.store.assign({'revision':0,'logger':'bt06-12345678','site_id':None})
        with self.assertRaises(ValueError):self.store.assign({'revision':self.store.snapshot()['revision'],'logger':'bt06-12345678','site_id':site['id']})
        self.now-=timedelta(days=1)
        with self.assertRaises(ValueError):self.store.assign({'revision':self.store.snapshot()['revision'],'logger':'bt06-12345678','site_id':None})
        self.assertEqual(self.store.path.read_bytes(),before)
        with self.assertRaises(ValueError):self.store.assign({'revision':self.store.snapshot()['revision'],'logger':'demo-room','site_id':site['id']})

    def test_failed_atomic_write_does_not_change_memory_or_file(self):
        site=self.save();before=self.store.path.read_bytes();value=self.store.snapshot()
        self.tick()
        with patch('backend.common.sites.atomic_json',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):self.store.assign({'revision':value['revision'],'logger':'bt06-12345678','site_id':site['id']})
        self.assertEqual(self.store.path.read_bytes(),before);self.assertEqual(self.store.snapshot(),value)

    def test_corrupt_registry_and_overlapping_history_are_not_silently_repaired(self):
        site=self.save();self.assign('bt06-12345678',site['id']);value=json.loads(self.store.path.read_text())
        duplicate=copy.deepcopy(value['assignments'][0]);duplicate['id']='1'*32;value['assignments'].append(duplicate)
        self.store.path.write_text(json.dumps(value));before=self.store.path.read_bytes()
        with self.assertRaises(ValueError):SiteStore(self.store.path)
        self.assertEqual(self.store.path.read_bytes(),before)
