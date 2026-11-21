import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.linux.auto_sync import AutoSync
from test_history_jobs import config


class Clock:
    def __init__(self):self.mono=0.;self.wall=1800000000.
    def advance(self,seconds):self.mono+=seconds;self.wall+=seconds


class Jobs:
    def __init__(self):self.active=False;self.calls=[];self.callback=None
    def busy(self):return self.active
    def start(self,options,**kwargs):
        self.calls.append((options,kwargs));self.active=True;self.callback=kwargs['on_complete']
    def finish(self,state='done',error=None,resume_error=None):
        self.active=False;self.callback({'state':state,'error':error,'resume_error':resume_error})


class AutoSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'autosync.json'
        self.clock=Clock();self.selected=config();self.live_state='receiving';self.fresh=True;self.diag='idle'
        self.receiver=SimpleNamespace(status=lambda:{'config':self.selected,'state':self.live_state,'fresh':self.fresh})
        self.jobs=Jobs();self.bluetooth=SimpleNamespace(status=lambda:{'state':self.diag})
        self.auto=self.make()
    def tearDown(self):self.auto.close();self.temp.cleanup()
    def make(self):return AutoSync(self.path,self.receiver,self.jobs,self.bluetooth,threading.RLock(),lambda:self.clock.mono,lambda:self.clock.wall)
    def enable(self):self.auto.configure({'enabled':True,'interval_minutes':15})

    def test_disabled_default_explicit_save_first_delay_and_device_binding(self):
        self.auto.tick();self.assertEqual(self.jobs.calls,[])
        self.enable();self.auto.tick();self.assertEqual(self.jobs.calls,[])
        self.clock.advance(900);self.auto.tick()
        self.assertEqual(len(self.jobs.calls),1)
        self.assertTrue(self.jobs.calls[0][1]['automatic'])
        self.assertEqual(self.jobs.calls[0][0],{'mode':'incremental'})
        self.assertTrue(self.auto.status()['active'])
        self.jobs.finish();self.assertEqual(self.auto.status()['next_in_seconds'],900)
        self.assertIsNotNone(self.auto.status()['last_success_at'])
        self.selected['device']['id']='87654321';self.clock.advance(900);self.auto.tick()
        self.assertEqual(len(self.jobs.calls),1);self.assertIn('Loggerauswahl',self.auto.status()['wait_reason'])

    def test_paused_stale_or_busy_never_starts_or_pauses_receiver(self):
        self.enable();self.clock.advance(900)
        for state,fresh,diag,busy in [('stopped',True,'idle',False),('receiving',False,'idle',False),('receiving',True,'running',False),('receiving',True,'idle',True)]:
            self.live_state,self.fresh,self.diag,self.jobs.active=state,fresh,diag,busy
            self.auto.tick();self.assertEqual(self.jobs.calls,[])
        self.jobs.active=False;self.auto.tick();self.assertEqual(len(self.jobs.calls),1)

    def test_failure_backoff_is_persisted_and_clock_jump_does_not_trigger(self):
        self.enable();self.clock.advance(900);self.auto.tick();self.jobs.finish('error','synthetic timeout')
        self.assertEqual(self.auto.status()['failures'],1)
        self.assertEqual(self.auto.status()['next_in_seconds'],1800)
        restarted=self.make();self.assertEqual(restarted.status()['next_in_seconds'],1800);restarted.close()
        self.clock.wall+=86400;self.auto.tick();self.assertEqual(len(self.jobs.calls),1)
        self.clock.advance(1800);self.auto.tick();self.jobs.finish('error','synthetic timeout')
        self.assertEqual(self.auto.status()['next_in_seconds'],3600)
        self.clock.advance(3600);self.auto.tick();self.jobs.finish()
        self.assertEqual(self.auto.status()['failures'],0)
        self.assertEqual(self.auto.status()['next_in_seconds'],900)

    def test_disable_during_running_prevents_any_followup(self):
        self.enable();self.clock.advance(900);self.auto.tick()
        self.auto.configure({'enabled':False,'interval_minutes':15})
        self.jobs.finish();self.assertIsNone(self.auto.status()['next_in_seconds'])
        self.clock.advance(999999);self.auto.tick();self.assertEqual(len(self.jobs.calls),1)

    def test_persistence_failure_blocks_automatic_device_access(self):
        self.enable();self.clock.advance(900)
        with patch('backend.linux.auto_sync.atomic_json',side_effect=OSError('synthetic disk')):
            self.auto.tick()
        self.assertEqual(self.jobs.calls,[]);self.assertIsNotNone(self.auto.status()['persistence_error'])
        self.assertFalse(self.auto.status()['active']);self.assertIsNone(self.auto.status()['next_in_seconds'])

    def test_real_job_completion_restores_receiver_and_updates_schedule(self):
        from backend.common.history_capture import decode_capture
        from backend.common.history_store import HistoryStore
        from backend.linux.history_jobs import HistoryJobs
        from history_fixture import capture,range_capture
        from test_history_jobs import FakeReceiver
        for success in (True,False):
            with self.subTest(success=success), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);store=HistoryStore(root/'history');times=[1700000000+i*600 for i in range(20)]
                base=store.publish('12345678',**decode_capture(capture(times)))
                receiver=FakeReceiver()
                receiver.status=lambda:{'config':receiver.config,'state':'receiving','fresh':True}
                jobs=HistoryJobs(receiver,store);clock=Clock()
                auto=AutoSync(root/'autosync.json',receiver,jobs,self.bluetooth,threading.RLock(),lambda:clock.mono,lambda:clock.wall)
                async def read(config,progress,base=None,automatic=False):
                    self.assertTrue(automatic)
                    if not success:raise TimeoutError()
                    newer=times+[times[-1]+600]
                    transfer=decode_capture(range_capture(newer,times[-16]-1,newer[-1]+1))
                    transfer['base_snapshot']=base['snapshot']
                    return transfer
                with patch('backend.linux.history_jobs.retrieve',read):
                    auto.configure({'enabled':True,'interval_minutes':15});clock.advance(900);auto.tick();jobs.worker.join(3)
                self.assertFalse(jobs.worker.is_alive());self.assertEqual(receiver.resumed,1)
                self.assertFalse(auto.status()['active'])
                self.assertEqual(auto.status()['failures'],0 if success else 1)
                self.assertEqual(len(store.snapshots()),2 if success else 1)
                auto.close();jobs.close()

    def test_validation_and_missing_selection(self):
        for options in ({},{'enabled':True,'interval_minutes':1},{'enabled':True,'interval_minutes':True},{'enabled':True,'interval_minutes':15,'device_id':'12345678'}):
            with self.assertRaises(ValueError):self.auto.configure(options)
        self.selected['device']=None
        with self.assertRaises(ValueError):self.enable()
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):self.make()
        self.assertEqual(self.path.read_text(),'{broken')


if __name__=='__main__':unittest.main()
