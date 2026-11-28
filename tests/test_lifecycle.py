import http.client
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from backend.linux.runtime import InstanceLock

ROOT=Path(__file__).resolve().parents[1]


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='bt06-lifecycle-');cls.program=Path(cls.temp.name)/'Programm mit Leerzeichen';cls.program.mkdir()
        for folder in ('backend','web'):shutil.copytree(ROOT/folder,cls.program/folder,ignore=shutil.ignore_patterns('__pycache__'))
        (cls.program/'tools').mkdir();shutil.copy2(ROOT/'tools/process_status.py',cls.program/'tools/process_status.py')
        for name in ('app.py','start.sh','status.sh','stop.sh'):shutil.copy2(ROOT/name,cls.program/name)
        old_path=sys.path[:]
        try:
            spec=importlib.util.spec_from_file_location('isolated_process_status',cls.program/'tools/process_status.py');cls.control=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.control)
        finally:sys.path[:]=old_path

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.data=Path(tempfile.mkdtemp(prefix='Daten mit Leerzeichen ',dir=self.temp.name));self.children=[]

    def tearDown(self):
        for process in self.children:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.fail('Isolierter Testprozess beendet sich nicht.')
            if process.stdout:process.stdout.close()
            if process.stderr:process.stderr.close()

    def command(self,name,*args):
        return subprocess.run([str(self.program/name),*map(str,args)],cwd='/tmp',capture_output=True,text=True,timeout=15)

    def control_command(self,*args):
        return subprocess.run([sys.executable,str(self.program/'tools/process_status.py'),*map(str,args)],cwd='/tmp',capture_output=True,text=True,timeout=15)

    def start(self,data=None):
        data=data or self.data
        process=subprocess.Popen([str(self.program/'start.sh'),'--root',str(data),'--port','0','--base-path','/klima'],cwd='/tmp',stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.children.append(process)
        self.assertTrue(select.select([process.stdout],[],[],10)[0],'Keine Startmeldung')
        line=process.stdout.readline();match=re.search(r'127\.0\.0\.1:(\d+)/klima/',line)
        self.assertIsNotNone(match,line+process.stderr.read() if process.poll() is not None else line)
        port=int(match[1]);deadline=time.monotonic()+5
        while True:
            try:
                connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2);connection.request('GET','/klima/api/status');response=connection.getresponse();self.assertEqual(response.status,200);response.read();connection.close();break
            except (OSError,http.client.HTTPException):
                if time.monotonic()>deadline:raise
                time.sleep(.05)
        return process,port

    def stop(self,process,data=None):
        result=self.command('stop.sh','--root',data or self.data);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(process.wait(timeout=5),0)

    def hard_stop(self,process):
        self.assertIn(process,self.children)
        self.assertEqual((Path('/proc')/str(process.pid)/'cwd').resolve(),self.program.resolve())
        process.kill();self.assertEqual(process.wait(timeout=5),-9)

    def test_sigkill_restart_keeps_committed_data_and_does_not_retry_device_actions(self):
        from backend.common.configuration import Configuration
        from backend.common.history_store import HistoryStore
        from backend.common.history_capture import decode_capture
        from backend.common.settings import atomic_json
        from history_fixture import capture
        config=Configuration(self.data/'config');settings=config.settings.get();settings['theme']='light';config.settings.save(settings)
        archive=HistoryStore(self.data/'data/history').publish('12345678',**decode_capture(capture()))
        paths=[self.data/'config/application.json',*list((self.data/'data/history').rglob('*'))]
        original={path:path.read_bytes() for path in paths if path.is_file()}
        reports=[]
        for folder in ('data/device-settings/changes','data/recording/changes'):
            path=self.data/folder/'latest.json';atomic_json(path,{'id':'synthetic-interrupted','status':'writing','may_have_changed':True,'notice':'Synthetic in-progress notice'})
            reports.append((path,path.read_bytes()))
        process,_=self.start();record=json.loads((self.data/'runtime/app.lock').read_text());self.hard_stop(process)
        self.assertIn('beendet',self.command('status.sh','--root',self.data).stdout)
        restarted,port=self.start();current=json.loads((self.data/'runtime/app.lock').read_text());self.assertNotEqual(record['pid'],current['pid'])
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        for route,key in (('device-settings/configuration','last_change'),('recording','last_start')):
            connection.request('GET','/klima/api/'+route);response=connection.getresponse();self.assertEqual(response.status,200);result=json.loads(response.read())
            self.assertIsNone(result['prepared']);self.assertFalse(result['automatic_retry']);self.assertTrue(result[key]['interrupted'])
        connection.request('GET','/klima/api/sync');result=json.loads(connection.getresponse().read());self.assertEqual(result['state'],'idle')
        connection.request('GET','/klima/api/live');live=json.loads(connection.getresponse().read());self.assertFalse(live['config']['enabled']);self.assertEqual(live['warnings']['entries'],[])
        connection.request('GET',f"/klima/api/export?source=device&logger={archive['logger']}&snapshot={archive['id']}");response=connection.getresponse();self.assertEqual(response.status,200);self.assertIn(b'Geraetekalender',response.read());connection.close()
        for path,content in original.items():self.assertEqual(path.read_bytes(),content)
        for path,content in reports:self.assertEqual(path.read_bytes(),content)
        self.stop(restarted)

    def test_killed_atomic_writer_does_not_publish_pending_settings_or_partial_run(self):
        from backend.common.configuration import Configuration
        config=Configuration(self.data/'config');settings=config.settings.get();settings['theme']='light';config.settings.save(settings)
        target=self.data/'config/application.json';original=target.read_bytes()
        stage=self.data/'simulation/.generating-interrupted';stage.mkdir(parents=True);(stage/'manifest.json').write_text('synthetic incomplete data')
        code="from pathlib import Path;from unittest.mock import patch;import json,sys,time;from backend.common.settings import atomic_json;path=Path(sys.argv[1]);value=json.loads(path.read_text());value['settings']['theme']='dark';value['revision']+=1\ndef paused(*args):\n print('READY',flush=True);time.sleep(30)\nwith patch('backend.common.settings.os.replace',side_effect=paused):atomic_json(path,value)"
        writer=subprocess.Popen([sys.executable,'-c',code,str(target)],cwd=self.program,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.children.append(writer)
        self.assertTrue(select.select([writer.stdout],[],[],5)[0]);self.assertEqual(writer.stdout.readline().strip(),'READY');self.hard_stop(writer)
        self.assertEqual(target.read_bytes(),original);pending=list(target.parent.glob('.pending-*'));self.assertEqual(len(pending),1)
        restarted,port=self.start();connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        connection.request('GET','/klima/api/settings');self.assertEqual(json.loads(connection.getresponse().read())['theme'],'light')
        connection.request('GET','/klima/api/runs');self.assertEqual(json.loads(connection.getresponse().read())['runs'],[]);connection.close()
        self.assertEqual(target.read_bytes(),original);self.assertTrue(pending[0].exists());self.assertEqual((stage/'manifest.json').read_text(),'synthetic incomplete data');self.stop(restarted)

    def test_portable_root_restart_preserves_original_and_preferences(self):
        process,port=self.start();self.assertEqual(self.command('status.sh','--root',self.data).returncode,0)
        original=self.data/'data/original.csv';original.parent.mkdir(exist_ok=True);original.write_bytes(b'SYNTHETIC ORIGINAL\n')
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5);connection.request('GET','/klima/api/session');token=json.loads(connection.getresponse().read())['csrf_token']
        connection.request('GET','/klima/api/settings');settings=json.loads(connection.getresponse().read());settings['theme']='light'
        connection.request('POST','/klima/api/settings',json.dumps(settings),{'Content-Type':'application/json','Origin':f'http://127.0.0.1:{port}','X-CSRF-Token':token});response=connection.getresponse();self.assertEqual(response.status,200);response.read();connection.close()
        saved=(self.data/'config/application.json').read_bytes();self.stop(process)
        self.assertIn('beendet',self.command('status.sh','--root',self.data).stdout)
        restarted,port=self.start();self.assertEqual((self.data/'config/application.json').read_bytes(),saved);self.assertEqual(original.read_bytes(),b'SYNTHETIC ORIGINAL\n');self.stop(restarted)

    def test_duplicate_instance_and_forged_fingerprint_never_signal_owner(self):
        process,_=self.start();lock=self.data/'runtime/app.lock';record=json.loads(lock.read_text())
        duplicate=self.command('start.sh','--root',self.data,'--port','0');self.assertNotEqual(duplicate.returncode,0);self.assertEqual(json.loads(lock.read_text()),record)
        for changed in ({**record,'pid':os.getpid()},{**record,'start_ticks':record['start_ticks']+1},{**record,'data_root':'/not-this-data'},[],{**record,'schema_version':99},{**record,'start_ticks':'invalid'}):
            lock.write_text(json.dumps(changed));result=self.command('stop.sh','--root',self.data);self.assertNotEqual(result.returncode,0);self.assertIsNone(process.poll())
        # Older PID-only records remain readable, but still require actual flock ownership.
        lock.write_text(json.dumps({'pid':process.pid}));self.assertEqual(self.command('status.sh','--root',self.data).returncode,0)
        lock.write_text(json.dumps(record));self.stop(process)

    def test_update_guard_sees_other_data_roots_of_same_program(self):
        a,_=self.start();other=self.data.parent/(self.data.name+' other');b,_=self.start(other)
        unused=self.data.parent/'unused root'
        self.assertNotEqual(self.control_command('require-stopped','--root',unused).returncode,0)
        self.stop(a);self.assertNotEqual(self.control_command('require-stopped','--root',unused).returncode,0)
        self.stop(b,other);self.assertEqual(self.control_command('require-stopped','--root',unused).returncode,0)

    def test_app_name_in_python_c_arguments_is_not_a_server_identity(self):
        code="from pathlib import Path;import time;from backend.linux.runtime import InstanceLock;guard=InstanceLock(Path(__import__('sys').argv[1])/'runtime/app.lock');guard.__enter__();print('READY',flush=True);time.sleep(30)"
        process=subprocess.Popen([sys.executable,'-c',code,str(self.data),'app.py','serve'],cwd=self.program,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.children.append(process)
        self.assertTrue(select.select([process.stdout],[],[],5)[0]);self.assertEqual(process.stdout.readline().strip(),'READY')
        result=self.command('stop.sh','--root',self.data);self.assertNotEqual(result.returncode,0);self.assertIsNone(process.poll())
        process.terminate();process.wait(timeout=5)

    def test_systemd_main_process_is_distinguished_from_portable_child(self):
        group=Path('/proc/self/cgroup').read_text()
        if not any(line.rsplit('/',1)[-1].endswith('.service') for line in group.splitlines()):self.skipTest('Kein Dienst-Cgroup für diese reine Zuordnungsprüfung')
        with patch.object(self.control.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=str(os.getpid()))):self.assertIsNotNone(self.control.managed_unit(os.getpid()))
        with patch.object(self.control.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='0')):self.assertIsNone(self.control.managed_unit(os.getpid()))

    def test_failed_lock_record_write_releases_lock_immediately(self):
        lock=self.data/'runtime/failure.lock'
        with patch('backend.linux.runtime.json.dump',side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                with InstanceLock(lock):self.fail('must not enter')
        with InstanceLock(lock):
            self.assertEqual(json.loads(lock.read_text())['schema_version'],2);self.assertEqual(lock.stat().st_mode&0o777,0o600)
        target=self.data/'synthetic-original.csv';target.write_bytes(b'UNCHANGED');lock.unlink();lock.symlink_to(target)
        with self.assertRaises(OSError):
            with InstanceLock(lock):self.fail('must not follow link')
        self.assertEqual(target.read_bytes(),b'UNCHANGED')
