import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from backend.common.settings import atomic_json
from backend.linux.configuration import ConfigurationWorkflow
from backend.linux.recording import RecordingWorkflow


class RecoveryStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        self.receiver=Mock();self.jobs=Mock();self.jobs.busy.return_value=False
        settings=SimpleNamespace(root=root/'settings');history=SimpleNamespace(root=root/'history')
        self.configuration=ConfigurationWorkflow(self.receiver,self.jobs,settings,history)
        self.recording=RecordingWorkflow(self.receiver,self.jobs,settings,history,self.configuration)

    def test_interrupted_reports_are_derived_read_only_without_retries(self):
        for workflow,key,path in ((self.configuration,'last_change',self.configuration.root/'latest.json'),(self.recording,'last_start',self.recording.root/'changes/latest.json')):
            for phase in ('checking','writing'):
                atomic_json(path,{'id':'synthetic','status':phase,'may_have_changed':True,'notice':'Old in-progress notice'})
                original=path.read_bytes();result=workflow.status()
                self.assertIsNone(result['prepared']);self.assertFalse(result['automatic_retry']);self.assertTrue(result[key]['interrupted'])
                self.assertIn('unterbrochen',result[key]['notice']);self.assertEqual(path.read_bytes(),original)
        self.jobs.start.assert_not_called();self.receiver.start.assert_not_called()

    def test_running_jobs_and_finished_reports_are_not_falsely_interrupted(self):
        for workflow,key,path,done in ((self.configuration,'last_change',self.configuration.root/'latest.json','verified'),(self.recording,'last_start',self.recording.root/'changes/latest.json','recording')):
            self.jobs.busy.return_value=True;atomic_json(path,{'status':'writing','notice':'In progress'})
            self.assertNotIn('interrupted',workflow.status()[key])
            self.jobs.busy.return_value=False;atomic_json(path,{'status':done,'notice':'Confirmed result'})
            result=workflow.status()[key];self.assertNotIn('interrupted',result);self.assertEqual(result['notice'],'Confirmed result')
