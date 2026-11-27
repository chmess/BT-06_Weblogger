import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from backend.common.configuration import Configuration,MAX_BYTES
from backend.common.settings import DEFAULTS,atomic_json
from backend.common.sites import SiteStore

CRITERIA={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':60,'surface_mode':'none','surface_value':None}


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.now=datetime(2026,1,1,tzinfo=timezone.utc);self.config=Configuration(self.root,clock=lambda:self.now)

    def tick(self):self.now+=timedelta(seconds=1)
    def site(self,name,id=None):
        self.tick();return self.config.sites.save({'revision':self.config.sites.snapshot()['revision'],'id':id,'values':{'name':name,'room':'Test','description':'Synthetic','criteria':copy.deepcopy(CRITERIA)}})['site']
    def bind(self,site):
        self.tick();self.config.sites.assign({'revision':self.config.sites.snapshot()['revision'],'logger':'bt06-12345678','site_id':site['id']})
    def preview(self,document,include=True,settings=None):
        self.tick();return self.config.preview({'document':document,'include_sites':include,'settings':settings or document.get('settings',document)})
    def apply(self,plan):self.tick();return self.config.apply({'token':plan['token']})

    def test_legacy_migration_is_lazy_atomic_and_old_files_remain_untouched(self):
        folder=self.root/'legacy';atomic_json(folder/'settings.json',{**DEFAULTS,'theme':'light'})
        sites=SiteStore(folder/'sites.json',clock=lambda:self.now)
        sites.save({'revision':0,'id':None,'values':{'name':'Legacy','room':'','description':'','criteria':CRITERIA}})
        originals={path:path.read_bytes() for path in folder.glob('*.json')}
        config=Configuration(folder);self.assertFalse(config.path.exists());self.assertEqual(config.settings.get()['theme'],'light')
        config.settings.save({**DEFAULTS,'humidity_warning':65})
        self.assertTrue(config.path.exists());self.assertEqual(len(config.sites.snapshot()['sites']),1)
        for path,raw in originals.items():self.assertEqual(path.read_bytes(),raw)
        (folder/'settings.json').write_text('broken')
        reopened=Configuration(folder);self.assertEqual(reopened.settings.get()['humidity_warning'],65)
        self.assertEqual(reopened.path.stat().st_mode&0o777,0o600)

    def test_preference_and_site_writes_share_one_canonical_file(self):
        site=self.site('A');self.config.settings.save({**DEFAULTS,'theme':'light'});self.bind(site)
        reopened=Configuration(self.root);self.assertEqual(reopened.settings.get()['theme'],'light')
        self.assertEqual(reopened.sites.snapshot()['active_assignments'][0]['site_id'],site['id'])
        self.assertFalse((self.root/'sites.json').exists());self.assertFalse((self.root/'settings.json').exists())

    def test_legacy_import_preserves_current_sites_and_preview_does_not_write(self):
        site=self.site('A');self.bind(site);before=self.config.path.read_bytes();registry=copy.deepcopy(self.config.sites.value)
        legacy={**DEFAULTS,'theme':'light'};plan=self.preview(legacy)
        self.assertTrue(plan['legacy']);self.assertEqual(self.config.path.read_bytes(),before)
        result=self.apply(plan);self.assertEqual(result['settings']['theme'],'light');self.assertEqual(result['sites'],registry)
        with self.assertRaises(ValueError):self.apply(plan)

    def test_old_file_cannot_restore_a_later_logger_move(self):
        a=self.site('A');self.bind(a);self.tick();document=self.config.document()
        b=self.site('B');self.bind(b);current=copy.deepcopy(self.config.sites.value)
        plan=self.preview(document,settings={**DEFAULTS,'theme':'light'});self.apply(plan)
        self.assertEqual(self.config.sites.value,current)
        self.assertEqual(self.config.sites.resolve('bt06-12345678',self.now.isoformat())['site_id'],b['id'])

    def test_changed_site_metadata_starts_at_apply_not_preview(self):
        site=self.site('Alt');self.bind(site);self.tick();document=self.config.document()
        self.site('Neu',id=site['id']);plan=self.preview(document)
        self.tick();during_review=self.now.isoformat();self.apply(plan)
        self.assertEqual(self.config.sites.resolve('bt06-12345678',during_review)['site_snapshot']['name'],'Neu')
        self.assertEqual(self.config.sites.resolve('bt06-12345678',self.now.isoformat())['site_snapshot']['name'],'Alt')

    def test_fresh_import_restores_historical_checkpoint_without_activating_file_binding(self):
        site=self.site('A');self.bind(site);self.tick();sample=self.now.isoformat();self.tick();document=self.config.document()
        target=Configuration(self.root/'fresh',clock=lambda:self.now+timedelta(seconds=10))
        plan=target.preview({'document':document,'include_sites':True,'settings':document['settings']})
        target.apply({'token':plan['token']})
        self.assertEqual(target.sites.snapshot()['active_assignments'],[])
        self.assertEqual(target.sites.resolve('bt06-12345678',sample)['site_id'],site['id'])
        self.assertIsNone(target.sites.resolve('bt06-12345678',(self.now+timedelta(seconds=20)).isoformat()))

    def test_conflicting_history_blocks_sites_but_preferences_only_is_possible(self):
        site=self.site('Local');self.bind(site)
        other=Configuration(self.root/'other',clock=lambda:self.now-timedelta(seconds=1))
        a=other.sites.save({'revision':0,'id':None,'values':{'name':'Other','room':'','description':'','criteria':CRITERIA}})['site']
        self.tick();other.clock=lambda:self.now;other.sites.clock=other.clock
        other.sites.assign({'revision':other.sites.value['revision'],'logger':'bt06-12345678','site_id':a['id']})
        self.tick();document=other.document()
        with self.assertRaises(ValueError):self.preview(document)
        before=copy.deepcopy(self.config.sites.value);plan=self.preview(document,include=False,settings={**DEFAULTS,'theme':'light'});self.apply(plan)
        self.assertEqual(self.config.sites.value,before)

    def test_changed_configuration_and_expired_tokens_never_apply(self):
        plan=self.preview({**DEFAULTS,'theme':'light'});self.config.settings.save({**DEFAULTS,'humidity_warning':66})
        with self.assertRaises(ValueError):self.apply(plan)
        self.assertEqual(self.config.settings.get()['humidity_warning'],66)
        plan=self.preview(DEFAULTS)
        with patch('backend.common.configuration.time.monotonic',return_value=1e100):
            with self.assertRaises(ValueError):self.config.apply({'token':plan['token']})

    def test_write_failure_before_rename_keeps_whole_previous_configuration(self):
        self.site('A');before=self.config.path.read_bytes();preferences=self.config.settings.get();registry=copy.deepcopy(self.config.sites.value)
        plan=self.preview({**DEFAULTS,'theme':'light'})
        with patch('backend.common.configuration.atomic_json',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):self.apply(plan)
        self.assertEqual(self.config.path.read_bytes(),before);self.assertEqual(self.config.settings.get(),preferences)
        self.assertEqual(self.config.sites.value,registry);self.assertIsNotNone(self.config.status()['error'])
        with self.assertRaises(ValueError):self.config.settings.save(self.config.settings.get())

    def test_directory_sync_failure_follows_visible_atomic_file_without_claiming_success(self):
        self.site('A');plan=self.preview({**DEFAULTS,'theme':'light'})
        def uncertain(path,value):atomic_json(path,value);raise OSError('after rename')
        with patch('backend.common.configuration.atomic_json',side_effect=uncertain):
            with self.assertRaises(OSError):self.apply(plan)
        visible=json.loads(self.config.path.read_text());self.assertEqual(self.config.settings.get(),visible['settings'])
        self.assertEqual(self.config.sites.value,visible['sites']);self.assertIsNotNone(self.config.status()['error'])
        with self.assertRaises(ValueError):self.config.settings.save(DEFAULTS)
        self.assertIsNone(Configuration(self.root).status()['error'])

    def test_import_event_keeps_counts_without_duplicating_private_descriptions(self):
        from backend.common.events import EventStore
        self.site('A');self.site('B');self.tick();document=self.config.document()
        for site in document['sites']['sites']:site['description']='x'*1900
        events=EventStore(self.root/'events');self.config.events=events
        plan=self.preview(document);self.apply(plan)
        event=events.query(event_type='settings.imported')['events'][0]
        self.assertNotIn('site_changes',event['DetailsJSON']);self.assertEqual(json.loads(event['DetailsJSON'])['updated_sites'],2)
        self.assertEqual(events.status()['failed_this_session'],0)

    def test_invalid_canonical_file_never_falls_back_or_repairs(self):
        atomic_json(self.root/'settings.json',DEFAULTS);self.config.path.write_text('{broken')
        before=self.config.path.read_bytes()
        with self.assertRaises(ValueError):Configuration(self.root)
        self.assertEqual(self.config.path.read_bytes(),before)
        self.config.path.unlink()
        with self.config.path.open('wb') as stream:stream.truncate(MAX_BYTES+1)
        with self.assertRaises(ValueError):Configuration(self.root)
