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
  await evaluate(`document.querySelector('#history-timezone').value='Europe/Berlin';document.querySelector('#timezone-confirmed').checked=true;document.querySelector('#timezone-form').requestSubmit()`);
  await waitFor(`state.timeAssignment?.timezone_confirmed===true&&!document.querySelector('#chart-export-assigned').disabled`);
  assert.equal(await evaluate(`state.timeAssignment.date_verified`),false);
  const assignedExport=await evaluate(`fetch('api/export?'+state.query+'&time_basis=assigned').then(r=>r.text())`);
  assert.ok(assignedExport.includes('ZugeordneteZeit')&&assignedExport.includes('+01:00')&&assignedExport.includes('DATUM_UNGEPRUEFT'));
  await evaluate(`document.querySelector('#autosync-interval').value='45';document.querySelector('#autosync-form').requestSubmit()`);
  await waitFor(`state.autoSync?.config.interval_minutes===45`);
  assert.equal(await evaluate(`state.autoSync.config.enabled`),false);
  const automaticSignal=await evaluate(`(async()=>{const originalApi=api;try{api=async(path,...args)=>path==='sync'?{state:'running',phase:'connecting',trigger:'automatic',expected:null,received:0,result:null,error:null,resume_error:null}:originalApi(path,...args);await refreshSync();return {signalHidden:document.querySelector('#sync-button-signal').hidden,status:document.querySelector('#sync-status').textContent};}finally{api=originalApi;await refreshSync();}})()`);
  assert.equal(automaticSignal.signalHidden,true);
  assert.ok(automaticSignal.status.includes('ohne Tastendruck'));

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
  assert.equal(await evaluate(`state.timeAssignment.assigned_count`),3);
  assert.equal(await evaluate(`state.timeAssignment.unassigned_count`),1);
  assert.equal(await evaluate(`document.querySelectorAll('#run-select optgroup').length`),2);
  assert.equal(await evaluate(`document.querySelector('#snapshot-list').textContent.includes('2 übereinstimmende Historienstände')`),true);
  assert.equal(await evaluate(`document.querySelector('#sync-incremental').disabled`),true);
  await evaluate(`setSource('simulation');document.querySelector('#period').value='0';loadHistory()`);
  await waitFor(`document.querySelector('#chart-caption').textContent.includes('Testwerte')`);
  assert.equal(await evaluate(`document.querySelector('#run-title').textContent`),'Testlauf');
  const settingsFixture=spawnSync('python3',['-c',`import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from settings_fixture import observation
from backend.common.device_settings import DeviceSettingsStore
from backend.common.settings_preview import settings_preview
from test_history_jobs import config
saved=DeviceSettingsStore(Path(sys.argv[1])/'data/device-settings').save('12345678',observation())
preview=settings_preview(config(),saved,{'base_capture':saved['capture'],'changes':{'broadcast_interval_seconds':1}})
record_preview=settings_preview(config(),saved,{'base_capture':saved['capture'],'changes':{'record_interval_seconds':1500}})
print(json.dumps({'settings':saved,'preview':preview,'record_preview':record_preview}))
`,join(scratch,'data')],{cwd:project,encoding:'utf8'});
  assert.equal(settingsFixture.status,0,settingsFixture.stderr);
  const settingsFixtureData=JSON.parse(settingsFixture.stdout),observed=settingsFixtureData.settings;
  await evaluate(`(async()=>{const originalApi=api;try{api=async(path,...args)=>path==='device-settings'?{settings:${JSON.stringify(observed)},memory_estimate:{capacity_records:32000,nominal_days:${observed.values.record_interval_seconds*32000/86400}},selected:true,read_only:true}:originalApi(path,...args);await refreshDeviceSettings();}finally{api=originalApi;}})()`);
  await click('[data-page="logger"]');
  const settingsText=await evaluate(`document.querySelector('#device-settings-values').textContent`);
  assert.ok(settingsText.includes('Demo BT06')&&settingsText.includes('1230 s')&&settingsText.includes('12,5 s'));
  assert.ok(settingsText.includes('Bedeutung noch nicht bestätigt'));
  assert.ok((await evaluate(`document.querySelector('#device-memory-estimate').textContent`)).includes('455,6 Tage'));
  assert.equal(await evaluate(`document.querySelector('#device-settings-read').disabled`),true);
  const settingsJobs=await evaluate(`(async()=>{const originalApi=api;const results=[];try{for(const job of [{state:'running',phase:'connecting'},{state:'error',phase:'finished',error:'Bluetooth-Zeitlimit erreicht.'},{state:'done',phase:'finished',result:${JSON.stringify(observed)}}]){state.sync=null;api=async(path,...args)=>path==='sync'?{mode:'settings',trigger:'manual',received:0,expected:null,error:null,result:null,...job}:path==='device-settings'?{settings:${JSON.stringify(observed)},memory_estimate:{capacity_records:32000,nominal_days:${observed.values.record_interval_seconds*32000/86400}},selected:true}:originalApi(path,...args);await refreshSync();await refreshDeviceSettings();results.push({text:document.querySelector('#device-settings-job').textContent,signalHidden:document.querySelector('#device-settings-button-signal').hidden,stand:document.querySelector('#device-settings-status').textContent});}return results;}finally{api=originalApi;state.sync=null;await refreshSync();}})()`);
  assert.equal(settingsJobs[0].signalHidden,false);
  assert.ok(settingsJobs[0].text.includes('Tastendruck'));
  assert.equal(settingsJobs[1].signalHidden,true);
  assert.ok(settingsJobs[1].text.includes('Kein neuer Einstellungsstand gespeichert'));
  assert.ok(settingsJobs[1].text.includes('Bluetooth-Zeitlimit'));
  assert.ok(settingsJobs.every(job=>job.stand.includes('Stand')));
  assert.ok(settingsJobs[2].text.includes('Geräteeinstellungen gelesen'));
  const draftFlow=await evaluate(`(async()=>{const originalApi=api;try{
    const saved=${JSON.stringify(observed)};updateDeviceDraft(saved,true);
    document.querySelector('#device-settings-draft').closest('details').open=true;
    const input=document.querySelector('#device-draft-interval');input.value='1';input.dispatchEvent(new Event('input',{bubbles:true}));
    let request;
    api=async(path,options)=>{if(path!=='device-settings/preview')throw new Error('Unexpected draft request '+path);request=JSON.parse(options.body);return ${JSON.stringify(settingsFixtureData.preview)};};
    await previewDeviceDraft(new Event('submit'));
    const text=document.querySelector('#device-draft-result').textContent,status=document.querySelector('#device-draft-status').textContent;
    input.value='2';input.dispatchEvent(new Event('input',{bubbles:true}));
    const invalidated=document.querySelector('#device-draft-result').textContent==='';
    updateDeviceDraft({...saved,capture:'f'.repeat(32)+'.csv'});
    const stale={value:input.value,blocked:document.querySelector('#device-draft-preview').disabled,status:document.querySelector('#device-draft-status').textContent};
    document.querySelector('#device-draft-reset').click();
    const reset={value:input.value,blocked:document.querySelector('#device-draft-preview').disabled};
    let release;api=()=>new Promise(resolve=>{release=resolve;});
    const inFlight=previewDeviceDraft(new Event('submit'));
    input.value='3';input.dispatchEvent(new Event('input',{bubbles:true}));
    release(${JSON.stringify(settingsFixtureData.preview)});await inFlight;
    const lateResponseIgnored=document.querySelector('#device-draft-result').textContent==='';
    updateDeviceDraft(null);const noDeviceBlocked=document.querySelector('#device-draft-preview').disabled;
    updateDeviceDraft(saved,true);
    return {request,text,status,invalidated,stale,reset,lateResponseIgnored,noDeviceBlocked};
  }finally{api=originalApi;}})()`);
  assert.equal(draftFlow.request.base_capture,observed.capture);
  assert.equal(draftFlow.request.changes.broadcast_interval_seconds,1);
  assert.equal(draftFlow.request.changes.transmit_power_dbm,0);
  assert.ok(draftFlow.text.includes('12.5 → 1 s')&&draftFlow.text.includes('0 dBm'));
  assert.ok(draftFlow.status.includes('Gerätehistorie löschen'));
  assert.equal(draftFlow.invalidated,true);
  assert.equal(draftFlow.stale.value,'2');assert.equal(draftFlow.stale.blocked,true);
  assert.ok(draftFlow.stale.status.includes('Entwurf bleibt sichtbar'));
  assert.equal(draftFlow.reset.value,'12.5');assert.equal(draftFlow.reset.blocked,false);
  assert.equal(draftFlow.lateResponseIgnored,true);
  assert.equal(draftFlow.noDeviceBlocked,true);
  const configurationFlow=await evaluate(`(async()=>{const originalApi=api;try{
    const saved=${JSON.stringify(observed)},plan=${JSON.stringify(settingsFixtureData.record_preview)};
    updateDeviceDraft(saved,true);
    const input=document.querySelector('#device-draft-record');input.value='25';input.dispatchEvent(new Event('input',{bubbles:true}));
    const prepared={kind:'configuration-prepared',token:'synthetic-once',preview:plan,values_before:saved.values,history:{count:3,scope:'full'},expires_in_seconds:600,will_stop:true,will_restart:false,notice:'Speichern kann Historie löschen. Aufzeichnung bleibt gestoppt.'};
    const calls=[];let action='preview';
    api=async(path,options)=>{
      if(path==='device-settings/preview')return plan;
      if(path==='device-settings/prepare'){calls.push({path,body:JSON.parse(options.body)});action='prepare';return {state:'running'};}
      if(path==='device-settings/apply'){calls.push({path,body:JSON.parse(options.body)});action='apply';return {state:'running'};}
      if(path==='sync')return {state:action==='apply'?'error':'done',phase:'finished',mode:action==='apply'?'configuration_write':'configuration_prepare',trigger:'manual',received:3,expected:3,result:action==='apply'?null:prepared,error:action==='apply'?'Gerätezustand unklar; nicht automatisch wiederholen.':null};
      if(path==='device-settings/configuration')return {prepared:action==='apply'?null:prepared,last_change:action==='apply'?{status:'uncertain',notice:'Zustand neu lesen.'}:null};
      throw new Error('Unexpected configuration UI request '+path);
    };
    await previewDeviceDraft(new Event('submit'));
    const prepareEnabled=!document.querySelector('#device-config-prepare').disabled;
    document.querySelector('#device-config-prepare').click();await new Promise(r=>setTimeout(r,0));
    const visible=!document.querySelector('#device-config-confirmation').hidden,summary=document.querySelector('#device-config-changes').textContent;
    const applyButton=document.querySelector('#device-config-apply'),loss=document.querySelector('#device-config-loss'),stop=document.querySelector('#device-config-stop');
    const initiallyBlocked=applyButton.disabled;
    loss.checked=true;loss.dispatchEvent(new Event('change'));const oneBlocked=applyButton.disabled;
    stop.checked=true;stop.dispatchEvent(new Event('change'));const bothEnabled=!applyButton.disabled;
    input.value='26';input.dispatchEvent(new Event('input',{bubbles:true}));const editedBlocked=applyButton.disabled&&!loss.checked&&!stop.checked;
    input.value='25';input.dispatchEvent(new Event('input',{bubbles:true}));
    loss.checked=true;stop.checked=true;stop.dispatchEvent(new Event('change'));
    applyButton.click();await new Promise(r=>setTimeout(r,0));
    return {prepareEnabled,visible,summary,initiallyBlocked,oneBlocked,bothEnabled,editedBlocked,calls,status:document.querySelector('#device-config-status').textContent,job:document.querySelector('#device-settings-job').textContent};
  }finally{api=originalApi;state.sync=null;await refreshSync();await refreshConfiguration();updateDeviceDraft(${JSON.stringify(observed)},true);}})()`);
  assert.ok(configurationFlow.prepareEnabled&&configurationFlow.visible);
  assert.ok(configurationFlow.summary.includes('25,0 min'));
  assert.ok(configurationFlow.initiallyBlocked&&configurationFlow.oneBlocked&&configurationFlow.bothEnabled&&configurationFlow.editedBlocked);
  assert.equal(configurationFlow.calls.length,2);
  assert.equal(configurationFlow.calls[0].body.changes.record_interval_seconds,1500);
  assert.deepEqual(configurationFlow.calls[1].body,{token:'synthetic-once',confirm_history_loss:true,confirm_stop:true});
  assert.ok(configurationFlow.status.includes('nicht abschließend bestätigt'));
  assert.ok(configurationFlow.job.includes('nicht automatisch wiederholen'));
  const parameterOnly=await evaluate(`(async()=>{const originalApi=api;try{api=async(path)=>path==='device-settings/configuration'?{prepared:null,last_change:{status:'parameters_verified',may_have_changed:true,recording_state_verified:false,notice:'Parameter bestätigt. Status ohne Aufzeichnungsdetails; kein automatischer Start.'}}:path==='sync'?{state:'done',phase:'finished',mode:'configuration_verify',result:{kind:'configuration-parameters-verified'},received:8,expected:8}:originalApi(path);await refreshSync();await refreshConfiguration();return {status:document.querySelector('#device-config-status').textContent,job:document.querySelector('#device-settings-job').textContent,verifyEnabled:!document.querySelector('#device-config-verify').disabled};}finally{api=originalApi;state.sync=null;await refreshSync();await refreshConfiguration();}})()`);
  assert.ok(parameterOnly.status.includes('Parameter zurückgelesen'));
  assert.ok(parameterOnly.job.includes('ohne Aufzeichnungsdetails'));
  assert.ok(!parameterOnly.job.includes('bleibt gestoppt'));
  assert.equal(parameterOnly.verifyEnabled,true);
  const recordingUi=await evaluate(`(async()=>{const originalApi=api;try{api=async(path)=>path==='recording'?{prepared:{token:'synthetic-start',interval_seconds:1500,protection:{count:0},expires_in_seconds:600,notice:'Geräteuhr ungeprüft.'},last_start:null}:originalApi(path);await refreshRecording();const button=document.querySelector('#recording-start');const initial=button.disabled;document.querySelector('#recording-loss').checked=true;recordingControls();const one=button.disabled;document.querySelector('#recording-consent').checked=true;recordingControls();return {initial,one,both:!button.disabled,text:document.querySelector('#recording-plan').textContent};}finally{api=originalApi;await refreshRecording();}})()`);
  assert.ok(recordingUi.initial&&recordingUi.one&&recordingUi.both);
  assert.ok(recordingUi.text.includes('25,0 min')&&recordingUi.text.includes('leerer Speicher nachgewiesen'));
  const manualUi=await evaluate(`(async()=>{const originalApi=api;try{api=async()=>({prepared:{token:'manual',allow_unread_history_loss:true,interval_seconds:1500,protection:{count:null},expires_in_seconds:600,notice:'Ungesicherte Daten dürfen verloren gehen.'},last_start:null});await refreshRecording();document.querySelector('#recording-loss').checked=true;document.querySelector('#recording-consent').checked=true;recordingControls();const blocked=document.querySelector('#recording-start').disabled;document.querySelector('#recording-unread-confirm').checked=true;recordingControls();return {blocked,enabled:!document.querySelector('#recording-start').disabled,text:document.querySelector('#recording-plan').textContent};}finally{api=originalApi;await refreshRecording();}})()`);
  assert.ok(manualUi.blocked&&manualUi.enabled&&manualUi.text.includes('Gerätebestand unbekannt'));
  assert.ok(!manualUi.text.includes('leerer Speicher'));

  await screenshot('device-settings-mobile.png');
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(external.length,0,JSON.stringify(external));
  const report={passed:true,checks:['empty state','generator','three cards','chart canvas','zoom preservation','save settings','load settings preview','load settings save','390px no overflow','BLE missing dependency state','live/simulation source switch with synthetic fixture','live CSV export','manual zoom pauses live follow','device calendar axis and warning','unverified original history CSV','device calendar custom range','switch back to simulation','prefix extension grouped without duplicate points','earlier snapshots accessible','incremental button availability','explicit timezone assignment and derived export','later data stays unconfirmed','auto sync remains off after saving interval','automatic attempt never requests button press','read-only settings values and unknown radio meaning','settings read unavailable without selection','settings job progress, button signal, timeout preserves prior stand, and success shown locally','draft diff preserves broadcast counterpart, warns of data loss, invalidates on edit, blocks stale base, and resets explicitly','25 minute recording draft, full preparation summary, two explicit confirmations, edit invalidation and uncertain write display','parameter verification never guesses recording state from zero summary','no JS exceptions','no external requests'],screenshots:8};
  await writeFile(join(artifacts,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{
  if(browser){try{await send('Browser.close',{},null);}catch{}if(browser.exitCode===null){browser.kill('SIGTERM');await new Promise(resolve=>{browser.once('exit',resolve);setTimeout(resolve,5000);});}}
  if(app){app.kill('SIGTERM');await new Promise(resolve=>{if(app.exitCode!==null)resolve();else{app.once('exit',resolve);setTimeout(resolve,5000);}});}
  for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('Browser closed'));}pending.clear();
  await rm(scratch,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
