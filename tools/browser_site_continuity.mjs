// Focused scenario using the existing disposable Chromium harness.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {join} from 'node:path';

export async function runSiteContinuity({evaluate,waitFor,click,screenshot,send,project,scratch}){
  await waitFor(`state.liveLoggers.length===2`);
  await click('[data-page="sites"]');await waitFor(`sitesData!==null`);
  await evaluate(`document.querySelector('#site-name').value='Synthetischer Loggerwechsel';document.querySelector('#site-name').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#site-form').requestSubmit()`);
  await waitFor(`document.querySelector('#site-draft-status').textContent==='Messstelle lokal gespeichert.'`);
  const site=await evaluate(`siteEditing`);
  for(const logger of ['bt06-12345678','bt06-23456789']){
    await evaluate(`document.querySelector('#assignment-logger').value=${JSON.stringify(logger)};document.querySelector('#assignment-site').value=${JSON.stringify(site)};document.querySelector('#assignment-site').dispatchEvent(new Event('change'));document.querySelector('#site-assign').click()`);
    await waitFor(`!siteBusy&&sitesData.active_assignments.some(item=>item.logger===${JSON.stringify(logger)})`);
    const fixture=spawnSync('python3',['-c',`import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_live import frame
from backend.common.bt06 import decode
from backend.common.configuration import Configuration
from backend.common.live_store import LiveStore
from backend.common.storage import parse_time
root=Path(sys.argv[1]);sites=Configuration(root/'config').sites
assignment=next(item for item in sites.value['assignments'] if item['logger']==sys.argv[2] and item['end'] is None)
payload=bytearray(frame());payload[4:8]=bytes.fromhex(sys.argv[2].removeprefix('bt06-'))
reading=decode(payload).json();store=LiveStore(root/'data',sites)
for ms in (0,1):store.append(reading,-50,(parse_time(assignment['start'])+timedelta(milliseconds=ms)).isoformat())
`,join(scratch,'data'),logger],{cwd:project,encoding:'utf8'});
    assert.equal(fixture.status,0,fixture.stderr);
  }
  await evaluate(`setSource('live');go('history');document.querySelector('#period').value='0';document.querySelector('#history-site').value=${JSON.stringify(site)};document.querySelector('#history-site').dispatchEvent(new Event('change'))`);
  await waitFor(`state.query?.get('site')===${JSON.stringify(site)}&&state.chartData.raw_count===2`);
  await evaluate(`document.querySelector('#logger-select').value='all';document.querySelector('#logger-select').dispatchEvent(new Event('change'))`);
  await waitFor(`state.query?.get('logger')==='all'&&state.chartData.raw_count===4`);
  assert.equal(await evaluate(`state.chartData.points.filter(point=>point[1]===null).length`),1);
  assert.equal(await evaluate(`state.chartData.site_selection.loggers.length`),2);
  assert.ok(await evaluate(`document.querySelector('#chart-caption').textContent.includes('übergreifend')`));
  await click('#chart-view-save');
  await evaluate(`go('statistics');analyzeStatistics(false)`);
  await waitFor(`state.statisticsReport?.site_selection?.logger==='all'`);
  assert.equal(await evaluate(`state.statisticsReport.raw_count`),4);
  await evaluate(`go('export');document.querySelector('#export-scope').value='statistics';prepareExport()`);
  await waitFor(`state.exportBase?.get('logger')==='all'&&!document.querySelector('#export-download').disabled`);
  const csv=await evaluate(`fetch('api/export?'+state.exportBase).then(response=>response.text())`);
  assert.equal(csv.trim().split('\n').length,5);assert.ok(csv.split('\n')[0].includes('Logger'));
  assert.ok(csv.includes('bt06-12345678')&&csv.includes('bt06-23456789'));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate(`go('history');state.chart.resize()`);
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await screenshot('site-continuity-mobile.png');
  await evaluate(`document.querySelector('#history-site').value='';document.querySelector('#history-site').dispatchEvent(new Event('change'))`);
  await waitFor(`state.query&&!state.query.has('site')&&state.query.get('logger')!=='all'`);
  assert.equal(await evaluate(`document.querySelector('#export-download').disabled`),true);
  assert.equal(await evaluate(`document.querySelector('#chart-view-load').disabled`),true);
  await evaluate(`setSource('device');loadHistory()`);
  await waitFor(`state.query?.get('source')==='device'`);
  assert.equal(await evaluate(`document.querySelector('#history-site-label').hidden`),true);
  assert.equal(await evaluate(`state.query.has('site')`),false);
  return ['two real-format synthetic loggers','historical site move','merged chart with assignment break','scoped statistics','CSV logger provenance','separate saved view','mobile width','filter reset invalidates export','device source remains separate'];
}
