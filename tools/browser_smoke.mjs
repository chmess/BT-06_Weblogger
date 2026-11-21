// Optional UI verification with installed Chromium and Node, no npm dependencies.
import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp, mkdir, writeFile, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const project=resolve(fileURLToPath(new URL('..',import.meta.url)));
const scratch=await mkdtemp(join(tmpdir(),'bt06-browser-'));
const artifacts=join(project,'test-results');await mkdir(artifacts,{recursive:true});
let app,browser;const pending=new Map();let nextId=0,buffer=Buffer.alloc(0),session;
const errors=[],external=[];let stderr='';
function send(method,params={},sessionId=session) {
  const id=++nextId;
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout: ${method}; ${stderr.slice(-1000)}`));},15000);
    pending.set(id,{resolve,reject,timer});browser.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
}
async function evaluate(expression) {
  const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function waitFor(expression) {
  return evaluate(`(async()=>{const stop=Date.now()+12000;while(Date.now()<stop){if(${expression})return true;await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait failed: '+${JSON.stringify(expression)});})()`);
}
async function click(selector) {await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);}
async function screenshot(name) {const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(artifacts,name),Buffer.from(result.data,'base64'));}
try {
  const snapshotFixture=spawnSync('python3',['-c',`import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from history_fixture import capture
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
HistoryStore(Path(sys.argv[1])/'data/history').publish('12345678',**decode_capture(capture()))
`,join(scratch,'data')],{cwd:project,encoding:'utf8'});
  assert.equal(snapshotFixture.status,0,snapshotFixture.stderr);
  app=spawn('python3',[join(project,'app.py'),'--root',join(scratch,'data'),'serve','--port','0','--base-path','/klima'],{cwd:project,stdio:['ignore','pipe','pipe']});
  let appError='';app.stderr.on('data',chunk=>{appError+=chunk.toString();});
  const url=await new Promise((resolve,reject)=>{
    let value='';const timer=setTimeout(()=>reject(new Error('App did not start')),10000);
    app.stdout.on('data',chunk=>{value+=chunk;const match=value.match(/http:\/\/127\.0\.0\.1:\d+\/klima\//);if(match){clearTimeout(timer);resolve(match[0]);}});
    app.on('exit',code=>{clearTimeout(timer);reject(new Error(`App exited ${code}: ${appError}`));});
  });
  browser=spawn('chromium',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-dev-shm-usage','--remote-debugging-pipe',`--user-data-dir=${join(scratch,'chromium')}`],{stdio:['ignore','ignore','pipe','pipe','pipe']});
  browser.stderr.on('data',chunk=>{stderr+=chunk.toString();});
  browser.stdio[4].on('data',chunk=>{
    buffer=Buffer.concat([buffer,chunk]);let end;
    while((end=buffer.indexOf(0))!==-1){const text=buffer.subarray(0,end).toString();buffer=buffer.subarray(end+1);if(!text)continue;const msg=JSON.parse(text);
      if(msg.id&&pending.has(msg.id)){const promise=pending.get(msg.id);pending.delete(msg.id);clearTimeout(promise.timer);if(msg.error)promise.reject(new Error(JSON.stringify(msg.error)));else promise.resolve(msg.result);}
      if(msg.method==='Runtime.exceptionThrown')errors.push(msg.params.exceptionDetails);
      if(msg.method==='Network.requestWillBeSent'&&!msg.params.request.url.startsWith(url)&&!msg.params.request.url.startsWith('data:'))external.push(msg.params.request.url);
    }
  });
  const target=await send('Target.createTarget',{url:'about:blank'},null);
  session=(await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
  await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:join(scratch,'downloads')},null);
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url});
  await waitFor(`document.querySelector('#template-note')?.textContent.includes('Allgemeine')`);
  assert.equal(await evaluate(`document.querySelector('#page-overview').hidden`),false);
  await screenshot('overview-empty.png');
  await click('[data-page="simulation"]');
  await evaluate(`document.querySelector('#simulation-form [name=days]').value='3';document.querySelector('#simulation-form [name=scenario]').value='gaps';document.querySelector('#simulation-form').requestSubmit()`);
  await waitFor(`document.querySelector('#chart-caption').textContent.includes('Testwerte')&&document.querySelector('#chart canvas')`);
  assert.equal(await evaluate(`document.querySelector('#page-history').hidden`),false);
  await screenshot('history-desktop.png');
  await evaluate(`state.chart.dispatchAction({type:'dataZoom',start:25,end:75})`);
  const zoom=await evaluate(`state.chart.getOption().dataZoom[0].start`);
  await evaluate(`state.chart.resize();renderChart(state.chartData)`);
  assert.equal(await evaluate(`state.chart.getOption().dataZoom[0].start`),zoom);
  await click('[data-page="overview"]');assert.equal(await evaluate(`document.querySelectorAll('.card').length`),3);
  await screenshot('overview-desktop.png');
  await click('[data-page="settings"]');
  await evaluate(`document.querySelector('#settings-form [name=theme]').value='light';document.querySelector('#settings-form [name=humidity_warning]').value='65';document.querySelector('#settings-form').requestSubmit()`);
  await waitFor(`document.documentElement.dataset.theme==='light'&&document.querySelector('#notice').textContent.includes('gespeichert')`);
  const saved=await evaluate(`fetch('api/settings').then(r=>r.json())`);assert.equal(saved.humidity_warning,65);assert.equal(saved.theme,'light');
  const restore={...saved,theme:'dark',humidity_warning:68};const upload=join(scratch,'settings.json');await writeFile(upload,JSON.stringify(restore));
  const documentNode=await send('DOM.getDocument');const input=await send('DOM.querySelector',{nodeId:documentNode.root.nodeId,selector:'#settings-file'});
  await send('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[upload]});
  await waitFor(`document.querySelector('#dirty').textContent==='Ungespeichert'&&document.querySelector('#settings-form [name=humidity_warning]').value==='68'`);
  assert.equal((await evaluate(`fetch('api/settings').then(r=>r.json())`)).humidity_warning,65);
  await evaluate(`document.querySelector('#settings-form').requestSubmit()`);
  await waitFor(`document.documentElement.dataset.theme==='dark'&&document.querySelector('#dirty').textContent==='Gespeichert'`);
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await screenshot('settings-mobile.png');
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="history"]');await waitFor(`document.querySelector('#page-history').hidden===false`);await screenshot('history-mobile.png');
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="logger"]');await screenshot('logger-mobile.png');
  assert.equal(await evaluate(`document.querySelector('#ble-status').textContent.includes('fehlt')`),true);
  // Synthetic protocol vectors only, in the disposable QA root. Never use production files.
  const fixture=spawnSync('python3',['-c',`import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,sys.argv[1])
from backend.common.bt06 import decode
from backend.common.live_store import LiveStore
p=bytearray(24);p[:3]=bytes.fromhex('090205');p[4:8]=bytes.fromhex('12345678');p[11]=100;p[12]=2;p[15:19]=bytes.fromhex('c9002602')
reading=decode(p).json();reading['quality']='SYNTHETISCHER_TESTVEKTOR'
store=LiveStore(Path(sys.argv[2])/'data')
for seconds in [120,60]:store.append(reading,-55,(datetime.now(timezone.utc)-timedelta(seconds=seconds)).isoformat())
`,project,join(scratch,'data')],{encoding:'utf8'});
  assert.equal(fixture.status,0,fixture.stderr);
  await evaluate(`refreshLive()`);
  await evaluate(`document.querySelector('#source-select').value='live';document.querySelector('#source-select').dispatchEvent(new Event('change'))`);
  await click('[data-page="overview"]');
  await waitFor(`document.querySelectorAll('.card').length===1&&document.querySelector('#cards').textContent.includes('20,1')`);
  assert.equal(await evaluate(`document.querySelector('#source-notice strong').textContent`),'Echte BT06-Empfänge');
  await click('[data-page="history"]');await waitFor(`document.querySelector('#chart-caption').textContent.includes('BLE-Empfänge')`);
  const exported=await evaluate(`fetch('api/export?'+state.query).then(r=>r.text())`);
  assert.ok(exported.includes('Host-Empfang')&&exported.includes('SYNTHETISCHER_TESTVEKTOR')&&!exported.includes('Simulation'));
  await evaluate(`state.chart.dispatchAction({type:'dataZoom',start:20,end:80})`);
  assert.equal(await evaluate(`state.follow`),false);
  await screenshot('history-live-fixture-mobile.png');
  await evaluate(`document.querySelector('#source-select').value='simulation';document.querySelector('#source-select').dispatchEvent(new Event('change'))`);
  await waitFor(`document.querySelectorAll('.card').length===3`);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  await evaluate(`setSource('device');go('history');loadHistory()`);
  await waitFor(`document.querySelector('#chart-caption').textContent.includes('3 Loggerwerte')`);
  assert.equal(await evaluate(`state.chartData.axis_basis`),'device_calendar');
  assert.equal(await evaluate(`state.chartData.clock_verified`),false);
  assert.equal(await evaluate(`document.querySelector('#source-notice').textContent.includes('ungeprüft')`),true);
  assert.equal(await evaluate(`document.querySelector('#run-title').textContent`),'Historienstand');
  assert.equal(await evaluate(`new Date(state.chartData.points[0][0]).toISOString().startsWith('2024-03-31')`),true);
  const deviceExport=await evaluate(`fetch('api/export?'+state.query).then(r=>r.text())`);
  assert.ok(deviceExport.includes('Geraetekalender')&&deviceExport.includes('ZEIT_UNGEPRUEFT'));
  await screenshot('device-history-mobile.png');
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await evaluate(`document.querySelector('#period').value='custom';document.querySelector('#period').dispatchEvent(new Event('change'));document.querySelector('#range-start').value='2024-03-31T00:30';document.querySelector('#range-end').value='2024-03-31T00:40';document.querySelector('#apply-range').click()`);
  await waitFor(`state.chartData.raw_count===2`);
  const extensionFixture=spawnSync('python3',['-c',`import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from history_fixture import capture
from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
from datetime import datetime,timezone
first=int(datetime(2024,3,31,0,30,tzinfo=timezone.utc).timestamp())
HistoryStore(Path(sys.argv[1])/'data/history').publish('12345678',**decode_capture(capture(seconds=[first+i*600 for i in range(4)])))
`,join(scratch,'data')],{cwd:project,encoding:'utf8'});
  assert.equal(extensionFixture.status,0,extensionFixture.stderr);
  await evaluate(`(async()=>{await refreshSnapshots();document.querySelector('#period').value='0';await loadHistory();})()`);
  await waitFor(`state.chartData.raw_count===4`);
  assert.equal(await evaluate(`state.series.length`),1);
  assert.equal(await evaluate(`state.snapshots.length`),2);
  assert.equal(await evaluate(`document.querySelectorAll('#run-select optgroup').length`),2);
  assert.equal(await evaluate(`document.querySelector('#snapshot-list').textContent.includes('2 übereinstimmende Historienstände')`),true);
  assert.equal(await evaluate(`document.querySelector('#sync-incremental').disabled`),true);
  await evaluate(`setSource('simulation');document.querySelector('#period').value='0';loadHistory()`);
  await waitFor(`document.querySelector('#chart-caption').textContent.includes('Testwerte')`);
  assert.equal(await evaluate(`document.querySelector('#run-title').textContent`),'Testlauf');
  const report={passed:true,checks:['empty state','generator','three cards','chart canvas','zoom preservation','save settings','load settings preview','load settings save','390px no overflow','BLE missing dependency state','live/simulation source switch with synthetic fixture','live CSV export','manual zoom pauses live follow','device calendar axis and warning','unverified original history CSV','device calendar custom range','switch back to simulation','prefix extension grouped without duplicate points','earlier snapshots accessible','incremental button availability','no JS exceptions','no external requests'],screenshots:7};
  await writeFile(join(artifacts,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{
  if(browser){try{await send('Browser.close',{},null);}catch{}if(browser.exitCode===null){browser.kill('SIGTERM');await new Promise(resolve=>{browser.once('exit',resolve);setTimeout(resolve,5000);});}}
  if(app){app.kill('SIGTERM');await new Promise(resolve=>{if(app.exitCode!==null)resolve();else{app.once('exit',resolve);setTimeout(resolve,5000);}});}
  for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('Browser closed'));}pending.clear();
  await rm(scratch,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
