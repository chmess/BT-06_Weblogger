import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from backend.common.climate_warnings import ClimateWarnings
from backend.common.sites import SiteStore
from backend.common.events import EventStore
from backend.common.live_store import LiveStore
from backend.common.bt06 import MANUFACTURER_ID
from backend.linux.receiver import Receiver
from test_live import frame,config

LOGGER='bt06-12345678'
CRITERIA={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':1,'surface_mode':'none','surface_value':None}


class ClimateWarningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.sites=SiteStore(self.root/'config/sites.json',clock=lambda:self.now)
        self.site=self.sites.save({'revision':0,'id':None,'values':{'name':'Testort','room':'','description':'','criteria':CRITERIA}})['site']['id']
        self.now+=timedelta(seconds=1);self.sites.assign({'revision':1,'logger':LOGGER,'site_id':self.site})
        self.start=self.now;self.events=EventStore(self.root/'events');self.monitor=ClimateWarnings(self.sites,self.events)

    def row(self,seconds,rh=80,temperature=20):
        return {'Schema':'2','Zeitstempel':(self.start+timedelta(seconds=seconds)).isoformat(),'Quelle':'BLE-Advertising','Zeitbasis':'Host-Empfang','Messstelle':self.site,
                'Temperatur':str(temperature).replace('.',',') if temperature is not None else '', 'Feuchte':str(rh).replace('.',',') if rh is not None else ''}

    def sample(self,seconds,rh=80,temperature=20):
        self.now=self.start+timedelta(seconds=seconds);self.monitor.observe(LOGGER,self.row(seconds,rh,temperature),60)
        return self.monitor.status(self.now)

    def kinds(self):return [item['Typ'] for item in self.events.query(limit=100)['events']]

    def test_minimum_hysteresis_single_warning_and_verified_release(self):
        self.assertEqual(self.sample(0)['entries'][0]['channels']['air']['state'],'pending')
        result=self.sample(60);self.assertEqual(result['active_count'],1)
        self.assertEqual(self.sample(120,69)['active_count'],1)
        self.assertEqual(self.sample(180,68)['active_count'],1)
        self.assertEqual(self.sample(240,67)['entries'][0]['channels']['air']['state'],'below_threshold')
        kinds=self.kinds();self.assertEqual(kinds.count('climate.warning'),1);self.assertEqual(kinds.count('climate.cleared'),1)
        self.assertNotIn('climate.unknown',kinds)

    def test_gap_timeout_and_invalid_values_never_clear_warning(self):
        self.sample(0);self.sample(60)
        result=self.monitor.status(self.start+timedelta(seconds=151))
        self.assertEqual(result['active_count'],0);self.assertEqual(result['entries'][0]['channels']['air']['state'],'unknown')
        self.monitor.status(self.start+timedelta(seconds=152));self.assertEqual(self.kinds().count('climate.unknown'),1)
        self.assertEqual(self.sample(180)['entries'][0]['channels']['air']['state'],'pending')
        self.sample(240);self.sample(300,None)
        self.assertEqual(self.kinds().count('climate.unknown'),2);self.assertNotIn('climate.cleared',self.kinds())
        self.assertEqual(self.sample(360,69)['entries'][0]['channels']['air']['state'],'below_threshold')

    def test_arriving_sample_across_gap_restarts_phase_even_without_status_poll(self):
        self.sample(0);self.sample(60)
        self.now=self.start+timedelta(seconds=180);self.monitor.observe(LOGGER,self.row(180),60)
        result=self.monitor.status(self.now)
        self.assertEqual(result['entries'][0]['channels']['air']['state'],'pending')
        self.assertEqual(self.kinds().count('climate.unknown'),1)
        self.sample(240);self.assertEqual(self.kinds().count('climate.warning'),2)

    def test_pause_restart_host_backwards_and_cadence_change_reset_evidence(self):
        self.sample(0);self.sample(60)
        self.monitor.pause(now=self.now);self.monitor.pause(now=self.now)
        self.assertEqual(self.kinds().count('climate.unknown'),1)
        self.sample(120);self.sample(180)
        self.assertEqual(self.monitor.status(self.start+timedelta(seconds=100))['active_count'],0)
        self.sample(240);self.sample(300)
        self.monitor.observe(LOGGER,self.row(360),120)
        result=self.monitor.status(self.start+timedelta(seconds=360))
        self.assertEqual(result['entries'][0]['channels']['air']['state'],'pending')
        fresh=ClimateWarnings(self.sites,self.events)
        self.assertEqual(fresh.status(self.now)['entries'],[])
        fresh.observe(LOGGER,self.row(360),60)
        self.assertEqual(fresh.status(self.start+timedelta(seconds=360))['active_count'],0)

    def test_assignment_changes_and_unassigned_originals_cannot_warn(self):
        self.sample(0);self.sample(60)
        self.now=self.start+timedelta(seconds=61)
        self.sites.save({'revision':2,'id':self.site,'values':{'name':'Neu','room':'','description':'','criteria':CRITERIA}})
        self.assertEqual(self.monitor.status(self.now)['active_count'],0)
        self.assertEqual(self.kinds().count('climate.unknown'),1)
        self.assertEqual(self.sample(120)['entries'][0]['site_name'],'Neu')
        self.assertEqual(self.sample(180)['active_count'],1)
        row=self.row(240);row['Messstelle']=LOGGER;self.monitor.observe(LOGGER,row,60)
        self.assertEqual(self.monitor.status(self.start+timedelta(seconds=240))['active_count'],0)
        other=ClimateWarnings(self.sites,self.events);row['Quelle']='Simulation';other.observe(LOGGER,row,60)
        self.assertEqual(other.status(self.now)['entries'],[])

    def test_surface_model_is_explicit_and_warning_channels_are_independent(self):
        self.assertNotIn('surface',self.sample(0)['entries'][0]['channels'])
        self.now+=timedelta(seconds=1)
        self.sites.save({'revision':2,'id':self.site,'values':{'name':'Test','room':'','description':'','criteria':{**CRITERIA,'surface_mode':'fixed','surface_value':10}}})
        self.sample(60,rh=60);result=self.sample(120,rh=60)
        self.assertEqual(result['entries'][0]['channels']['air']['state'],'below_threshold')
        self.assertEqual(result['entries'][0]['channels']['surface']['state'],'warning')
        self.assertEqual(result['entries'][0]['channels']['condensation']['state'],'warning')
        result=self.sample(180,rh=60,temperature=None)
        self.assertEqual(result['entries'][0]['channels']['surface']['state'],'unknown')
        self.assertEqual(result['active_count'],0)

    def test_warning_event_failure_does_not_retry_or_claim_durable_event(self):
        self.sample(0)
        with patch.object(self.events,'append',side_effect=OSError('disk')):
            result=self.sample(60)
        self.assertEqual(result['active_count'],1)
        self.assertFalse(result['entries'][0]['channels']['air']['event_saved'])
        self.assertIsNotNone(self.events.status()['error'])
        self.sample(120);self.assertEqual(self.events.status()['failed_this_session'],1)
        self.assertNotIn('climate.warning',self.kinds())

    def test_receiver_observes_only_successfully_persisted_rows(self):
        store=LiveStore(self.root/'data',self.sites)
        receiver=Receiver(self.root/'receiver.json',store,threading.Lock(),warnings=self.monitor)
        receiver.config=config();device=SimpleNamespace(address=config()['device']['address'])
        advertisement=SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame(humidity=800)},rssi=-50)
        receiver.on_advertisement(device,advertisement,self.start)
        receiver.on_advertisement(device,advertisement,self.start+timedelta(seconds=30))
        self.assertEqual(receiver.value['saved_this_session'],1)
        with patch.object(store,'append',side_effect=OSError('disk')):
            receiver.on_advertisement(device,advertisement,self.start+timedelta(seconds=60))
        self.assertEqual(self.monitor.status(self.start+timedelta(seconds=60))['active_count'],0)
        receiver.on_advertisement(device,advertisement,self.start+timedelta(seconds=60))
        self.assertEqual(receiver.value['saved_this_session'],2)
        self.assertEqual(self.monitor.status(self.start+timedelta(seconds=60))['active_count'],1)
        self.assertEqual(len(list(store.rows(LOGGER))),2)
