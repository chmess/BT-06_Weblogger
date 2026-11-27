import json
import http.client
import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from backend.common.sites import SiteStore
from backend.common.site_selection import select_site
from backend.common.storage import chart_data,csv_text
from backend.common.live_store import LIVE_FIELDS
from backend.common.statistics import summarize
from backend.common.risk import analyze
from backend.server import Application,make_server

CRITERIA={'air_threshold':70,'surface_threshold':80,'hysteresis':2,'minimum_minutes':0,'surface_mode':'none','surface_value':None}
LOGGER='bt06-12345678'


class SiteSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.store=SiteStore(self.root/'config/sites.json',clock=lambda:self.now)
        self.site=self.store.save({'revision':0,'id':None,'values':{'name':'Alter Name','room':'Test','description':'','criteria':CRITERIA}})['site']['id']
        self.now+=timedelta(seconds=1)
        self.store.assign({'revision':1,'logger':LOGGER,'site_id':self.site})
        self.start=self.now

    def row(self,seconds,site=None):
        row=dict.fromkeys(LIVE_FIELDS,'')
        row.update(Schema='2',DatensatzID=str(seconds),Zeitstempel=(self.start+timedelta(seconds=seconds)).isoformat(),Temperatur='20,0',Feuchte='80,0',Messstelle=site or self.site,Quelle='BLE-Advertising',Zeitbasis='Host-Empfang')
        return row

    def selected(self,rows):return select_site(self.store,LOGGER,self.site,rows)[0]

    def version(self,seconds=120):
        self.now=self.start+timedelta(seconds=seconds)
        self.store.save({'revision':self.store.snapshot()['revision'],'id':self.site,'values':{'name':'Neuer Name '+str(seconds),'room':'Test','description':'','criteria':CRITERIA}})

    def test_original_id_and_exclusive_host_boundaries_are_both_required(self):
        self.now=self.start+timedelta(seconds=120)
        self.store.assign({'revision':2,'logger':LOGGER,'site_id':None})
        rows=[self.row(-1),self.row(0),self.row(60,LOGGER),self.row(119),self.row(120),self.row(121)]
        result=list(self.selected(rows));self.assertEqual([row['DatensatzID'] for row in result],['0','119'])
        other,_=select_site(self.store,'bt06-23456789',self.site,rows);self.assertEqual(list(other),[])
        self.assertEqual(list(self.selected([])),[])

    def test_assignment_boundaries_break_chart_statistics_and_phases(self):
        self.version()
        rows=[self.row(n) for n in (0,60,120,180)]
        selected=list(self.selected(rows));self.assertNotEqual(selected[1].site_segment,selected[2].site_segment)
        chart=chart_data(iter(selected),1,budget=8)
        self.assertEqual(chart['raw_count'],4)
        self.assertEqual(sum(p[1] is None for p in chart['points']),1)
        self.assertTrue(any(p[1] is None for p in chart['climate']['points']))
        result=summarize(iter(selected),1)
        self.assertEqual(result['metrics']['humidity_pct']['observed_seconds'],120)
        self.assertEqual(result['gap_count'],1)
        report=analyze(iter(selected),1,CRITERIA)
        self.assertEqual(report['air']['observed_seconds'],120)
        self.assertEqual(report['air']['phase_count'],2)
        self.assertEqual(report['air']['phases'][0]['end_reason'],'assignment_boundary')
        self.assertEqual(summarize(iter(rows),1)['metrics']['humidity_pct']['observed_seconds'],180)

    def test_decimation_keeps_every_assignment_boundary(self):
        rows=[self.row(n) for n in range(0,600,60)];self.version(600)
        rows.extend(self.row(n) for n in range(600,1200,60));self.version(1200)
        rows.extend(self.row(n) for n in range(1200,1800,60))
        chart=chart_data(self.selected(rows),1,budget=8)
        self.assertEqual(sum(p[1] is None for p in chart['points']),2)
        self.assertEqual(chart['raw_count'],30)

    def test_csv_is_exact_original_subset_without_internal_columns(self):
        rows=[self.row(0),self.row(60,LOGGER),self.row(120)]
        self.assertEqual(csv_text(self.selected(rows),LIVE_FIELDS),csv_text([rows[0],rows[2]],LIVE_FIELDS))
        self.assertNotIn('site_segment',rows[0])

    def test_selection_captures_one_registry_revision_before_iteration(self):
        rows=[self.row(0),self.row(60),self.row(120)]
        selected,context=select_site(self.store,LOGGER,self.site,iter(rows));self.version(60)
        result=list(selected)
        self.assertEqual(len({row.site_segment for row in result}),1)
        self.assertEqual(context['revision'],2);self.assertEqual(context['current_name'],'Alter Name')
        with self.assertRaises(ValueError):select_site(self.store,LOGGER,'site-'+'f'*32,[])
        with self.assertRaises(ValueError):select_site(self.store,LOGGER,'../private',[])

    def test_api_reuses_filter_for_chart_statistics_risk_and_both_exports(self):
        app=Application(self.root,'/klima');app.sites=self.store
        self.version()
        rows=[self.row(0),self.row(60,LOGGER),self.row(120)]
        server=make_server(app,0);thread=threading.Thread(target=server.serve_forever);thread.start()
        def get(path):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            connection.request('GET','/klima/api/'+path);response=connection.getresponse();result=response.status,response.read();connection.close();return result
        try:
            with patch.object(app,'loggers',return_value=[{'id':LOGGER}]),patch.object(app.live_store,'rows',side_effect=lambda *args:iter(rows)):
                query=f'?source=live&logger={LOGGER}&site={self.site}'
                for route in ('history','statistics','risk'):
                    extra='&air_threshold=70&surface_threshold=80&hysteresis=2&minimum_minutes=0&surface_mode=none&surface_value=' if route=='risk' else ''
                    code,body=get(route+query+extra);self.assertEqual(code,200,body)
                    data=json.loads(body);self.assertEqual(data['site_selection']['site_id'],self.site)
                    if route!='risk':self.assertEqual(data['raw_count'],2)
                code,body=get('export'+query);self.assertEqual(code,200)
                self.assertEqual(body.decode('utf-8-sig'),csv_text([rows[0],rows[2]],LIVE_FIELDS))
                code,body=get('export'+query+'&fields=Zeitstempel,Temperatur,Taupunkt_C&climate=1');self.assertEqual(code,200,body)
                self.assertNotIn('site_segment',body.decode())
                self.assertEqual(get('export/options'+query)[0],200)
                self.assertEqual(get('history'+query+'&site='+self.site)[0],400)
                self.assertEqual(get('history'+query.replace('source=live','source=device'))[0],400)
                self.assertEqual(get('history'+query.replace('source=live','source=simulation'))[0],400)
                self.assertEqual(get('history'+query.replace(self.site,'site-'+'f'*32))[0],400)
                code,body=get(f'export?source=live&logger={LOGGER}')
                self.assertEqual(code,200);self.assertEqual(body.decode('utf-8-sig'),csv_text(rows,LIVE_FIELDS))
        finally:server.shutdown();server.server_close();thread.join()
