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
let screenshotCount=0;
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
async function screenshot(name) {const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(artifacts,name),Buffer.from(result.data,'base64'));screenshotCount++;}
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
  assert.ok(await evaluate(`state.chart.getOption().series.some(series=>series.name==='Taupunkt'&&series.data.some(p=>p[1]!=null))`));
  await click('[data-page="climate"]');await click('#climate-copy');await waitFor(`document.querySelector('#climate-input-source').textContent.includes('synthetischen Testdaten')`);
  await evaluate(`document.querySelector('#climate-temperature').value='20';document.querySelector('#climate-humidity').value='50';document.querySelector('#climate-surface').value='10';document.querySelector('#climate-form').requestSubmit()`);
  await waitFor(`document.querySelector('#climate-results').textContent.includes('9,26 °C')`);
  assert.ok(await evaluate(`document.querySelector('#climate-results').textContent.includes('8,62 g/m³')&&document.querySelector('#climate-results').textContent.includes('95,1 % rF')`));
  await evaluate(`document.querySelector('#climate-surface').value='5';document.querySelector('#climate-form').requestSubmit()`);
  await waitFor(`document.querySelector('#climate-results').textContent.includes('Kondensationsbedingung')`);
  const climateStale=await evaluate(`(async()=>{const originalApi=api;let release;try{api=async()=>new Promise(resolve=>{release=resolve;});const pending=calculateClimate(new Event('submit'));document.querySelector('#climate-temperature').dispatchEvent(new Event('input',{bubbles:true}));release({});await pending;return document.querySelector('#climate-results').children.length===0&&document.querySelector('#climate-status').textContent.includes('Eingaben geändert');}finally{api=originalApi;}})()`);
  assert.equal(climateStale,true);
  await evaluate(`document.querySelector('#risk-form').requestSubmit()`);await waitFor(`document.querySelector('#risk-status').textContent.includes('abgeschlossen')`);
  assert.equal(await evaluate(`state.riskReport.surface===null&&state.riskReport.air.observed_seconds>0&&document.querySelector('#risk-results').textContent.includes('Ohne Oberflächenannahme')`),true);
  await evaluate(`document.querySelector('#risk-mode').value='fixed';document.querySelector('#risk-mode').dispatchEvent(new Event('change'));document.querySelector('#risk-value').value='5';document.querySelector('#risk-air').value='40';document.querySelector('#risk-minimum').value='0';document.querySelector('#risk-form').requestSubmit()`);
  await waitFor(`document.querySelector('#risk-status').textContent.includes('abgeschlossen')`);
  assert.equal(await evaluate(`state.riskReport.condensation.above_threshold_samples>0&&state.riskReport.surface!==null&&document.querySelector('#risk-range').textContent.includes('5,0 °C konstant')`),true);
  const riskStale=await evaluate(`(async()=>{const originalApi=api,result=state.riskReport;let release;try{api=async()=>new Promise(resolve=>{release=resolve;});const pending=analyzeRisk();document.querySelector('#risk-air').dispatchEvent(new Event('input',{bubbles:true}));release(result);await pending;return document.querySelector('#risk-results').children.length===0&&state.riskReport===null;}finally{api=originalApi;}})()`);assert.equal(riskStale,true);
  await evaluate(`document.querySelector('#risk-mode').value='none';document.querySelector('#risk-mode').dispatchEvent(new Event('change'));document.querySelector('#risk-air').value='70';document.querySelector('#risk-minimum').value='60'`);
  await click('[data-page="statistics"]');await click('#statistics-range-button');await waitFor(`document.querySelector('#statistics-table').hidden===false`);
  const stats=await evaluate(`({rows:document.querySelector('#statistics-values').children.length,raw:state.statisticsReport.raw_count,chartRaw:state.chartData.raw_count,metric:state.statisticsReport.metrics.temperature_c})`);
  assert.equal(stats.rows,4);assert.equal(stats.raw,stats.chartRaw);assert.ok(stats.metric.sample_mean>=stats.metric.minimum.value&&stats.metric.sample_mean<=stats.metric.maximum.value);
  const statsExport=await evaluate(`(async()=>{const click=HTMLAnchorElement.prototype.click;let href;try{HTMLAnchorElement.prototype.click=function(){href=this.href;};document.querySelector('#statistics-export').click();await new Promise(r=>setTimeout(r,0));}finally{HTMLAnchorElement.prototype.click=click;}const csv=await fetch(href).then(r=>r.text());return {sameQuery:new URL(href).searchParams.toString()===state.statisticsQuery.toString(),rows:csv.trim().split('\\n').length-1};})()`);
  assert.equal(statsExport.sameQuery,true);assert.equal(statsExport.rows,stats.raw);
  const statsStale=await evaluate(`(async()=>{const originalApi=api,result=state.statisticsReport,period=document.querySelector('#period').value;let release;try{api=async()=>new Promise(resolve=>{release=resolve;});const pending=analyzeStatistics();document.querySelector('#period').value='6';release(result);await pending;return state.statisticsReport===null&&document.querySelector('#statistics-export').disabled&&document.querySelector('#statistics-status').textContent.includes('Auswahl geändert');}finally{api=originalApi;document.querySelector('#period').value=period;}})()`);assert.equal(statsStale,true);
  await click('[data-page="export"]');await click('#export-prepare');await waitFor(`document.querySelector('#export-status').textContent.includes('Spaltenauswahl vorbereitet.')`);
  assert.equal(await evaluate(`document.querySelector('#export-original-fields input[value="Zeitstempel"]').disabled`),true);
  await evaluate(`document.querySelector('#export-climate').checked=true;document.querySelector('#export-climate').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#export-original-fields input[value="Feuchte"]').checked=false`);
  const customExport=await evaluate(`(async()=>{const click=HTMLAnchorElement.prototype.click,create=URL.createObjectURL;let blob,href,name;try{URL.createObjectURL=function(value){blob=value;return create.call(URL,value);};HTMLAnchorElement.prototype.click=function(){href=this.href;name=this.download;};await downloadPreparedExport();const text=await blob.text();return {name,header:text.trim().split('\\n')[0].split(';'),rows:text.trim().split('\\n').length-1};}finally{HTMLAnchorElement.prototype.click=click;URL.createObjectURL=create;}})()`);
  assert.ok(customExport.name.endsWith('_klima.csv'));assert.ok(customExport.header.includes('Taupunkt_C')&&customExport.header.includes('Berechnungsstatus')&&customExport.header.includes('Exporttyp'));assert.equal(customExport.header.includes('Feuchte'),false);assert.equal(customExport.rows,stats.raw);
  const exportGuards=await evaluate(`(()=>{for(const input of document.querySelectorAll('#export-calculated-fields input'))input.checked=false;exportControls();const noneBlocked=document.querySelector('#export-download').disabled;document.querySelector('#export-scope').value='visible';document.querySelector('#export-scope').dispatchEvent(new Event('change'));return {noneBlocked,changedBlocked:document.querySelector('#export-download').disabled};})()`);assert.equal(exportGuards.noneBlocked,true);assert.equal(exportGuards.changedBlocked,true);
  const preparedStale=await evaluate(`(async()=>{const originalApi=api;let release;try{api=async()=>new Promise(resolve=>{release=resolve;});const pending=prepareExport();document.querySelector('#export-scope').value='selected';document.querySelector('#export-scope').dispatchEvent(new Event('change'));release({});await pending;return !state.exportBase&&document.querySelector('#export-choices').hidden;}finally{api=originalApi;}})()`);assert.equal(preparedStale,true);
  await evaluate(`analyzeStatistics()`);await evaluate(`document.querySelector('#export-scope').value='statistics';document.querySelector('#export-scope').dispatchEvent(new Event('change'));prepareExport()`);await waitFor(`document.querySelector('#export-status').textContent.includes('Spaltenauswahl vorbereitet.')`);
  assert.equal(await evaluate(`state.exportBase.toString()===state.statisticsQuery.toString()`),true);
  await evaluate(`document.querySelector('#export-scope').value='selected';document.querySelector('#export-scope').dispatchEvent(new Event('change'))`);
  await click('[data-page="history"]');
  await evaluate(`state.chart.dispatchAction({type:'dataZoom',start:25,end:75})`);
  const visibleRisk=await evaluate(`(async()=>{const range=chartRange(true);await analyzeRisk(true);const matches=state.riskReport.range.start_ms===range.start&&state.riskReport.range.end_ms===range.end;clearRisk();return matches;})()`);assert.equal(visibleRisk,true);
  const visibleStats=await evaluate(`(async()=>{const range=chartRange(true);await analyzeStatistics(true);return state.statisticsReport.range.start_ms===range.start&&state.statisticsReport.range.end_ms===range.end;})()`);assert.equal(visibleStats,true);
  const visibleExport=await evaluate(`(async()=>{const range=chartRange(true);document.querySelector('#export-scope').value='visible';await prepareExport();const exact=Date.parse(state.exportBase.get('start'))===range.start&&Date.parse(state.exportBase.get('end'))===range.end;document.querySelector('#export-scope').value='selected';invalidateExport();return exact;})()`);assert.equal(visibleExport,true);
  const zoom=await evaluate(`state.chart.getOption().dataZoom[0].start`);
  await evaluate(`state.chart.resize();renderChart(state.chartData)`);
  assert.equal(await evaluate(`state.chart.getOption().dataZoom[0].start`),zoom);
  const chartNavigation=await evaluate(`(async()=>{
    const base=chartRange(),visible=chartRange(true),query=state.query.toString();
    const anchorClick=HTMLAnchorElement.prototype.click;let href;
    try{HTMLAnchorElement.prototype.click=function(){href=this.href;};document.querySelector('#chart-export-visible').click();await new Promise(r=>setTimeout(r,0));}finally{HTMLAnchorElement.prototype.click=anchorClick;}
    const exported=new URL(href),csv=await fetch(exported).then(r=>r.text()),raw=await fetch('api/export?'+query).then(r=>r.text());
    const lines=csv.trim().split('\\n'),timestampIndex=lines[0].split(';').indexOf('Zeitstempel'),rows=lines.slice(1),times=rows.map(line=>new Date(line.split(';')[timestampIndex]).getTime());
    const queryUnchanged=state.query.toString()===query;
    await shiftChart(-1);const previous=chartRange();await shiftChart(1);const next=chartRange();
    document.querySelector('#period').value='24';document.querySelector('#custom-period').hidden=true;await loadHistory();
    return {base,visible,previous,next,queryUnchanged,start:Date.parse(exported.searchParams.get('start')),end:Date.parse(exported.searchParams.get('end')),count:rows.length,rawCount:raw.trim().split('\\n').length-1,inside:times.every(t=>t>=visible.start&&t<=visible.end),presets:[...document.querySelector('#period').options].map(o=>o.value)};
  })()`);
  assert.equal(chartNavigation.visible.end-chartNavigation.visible.start,(chartNavigation.base.end-chartNavigation.base.start)/2);
  assert.equal(chartNavigation.start,chartNavigation.visible.start);assert.equal(chartNavigation.end,chartNavigation.visible.end);
  assert.ok(chartNavigation.count>0&&chartNavigation.count<chartNavigation.rawCount);assert.equal(chartNavigation.inside,true);assert.equal(chartNavigation.queryUnchanged,true);
  assert.equal(chartNavigation.previous.end,chartNavigation.visible.start);assert.deepEqual(chartNavigation.next,chartNavigation.visible);
  for(const period of ['1','6','12','24','48','168','336','720','2160','4320','8760','0'])assert.ok(chartNavigation.presets.includes(period));
  const originalZone=await evaluate(`Intl.DateTimeFormat().resolvedOptions().timeZone`);
  await send('Emulation.setTimezoneOverride',{timezoneId:'Europe/Berlin'});
  const dstNavigation=await evaluate(`(async()=>{
    const saved={query:state.query,data:state.chartData,shifted:state.shiftedRange,source:state.source,period:document.querySelector('#period').value,start:document.querySelector('#range-start').value,end:document.querySelector('#range-end').value},originalLoad=loadHistory;
    try{
      state.source='simulation';state.query=new URLSearchParams({start:'2026-10-25T01:30:00.000Z',end:'2026-10-25T02:30:00.000Z'});state.chartData={points:[]};
      loadHistory=async()=>{state.query=buildQuery();};await shiftChart(-1);const result={start:state.query.get('start'),end:state.query.get('end'),sameLocalInput:document.querySelector('#range-start').value===document.querySelector('#range-end').value};
      document.querySelector('#range-start').dispatchEvent(new Event('input'));result.cleared=state.shiftedRange===null;return result;
    }finally{loadHistory=originalLoad;state.query=saved.query;state.chartData=saved.data;state.shiftedRange=saved.shifted;state.source=saved.source;document.querySelector('#period').value=saved.period;document.querySelector('#custom-period').hidden=saved.period!=='custom';document.querySelector('#range-start').value=saved.start;document.querySelector('#range-end').value=saved.end;updateChartControls();}
  })()`);
  assert.equal(dstNavigation.start,'2026-10-25T00:30:00.000Z');assert.equal(dstNavigation.end,'2026-10-25T01:30:00.000Z');assert.equal(dstNavigation.sameLocalInput,true);assert.equal(dstNavigation.cleared,true);
  await send('Emulation.setTimezoneOverride',{timezoneId:originalZone});
  await send('Runtime.evaluate',{expression:"document.querySelector('#chart-fullscreen').click()",userGesture:true});
  await waitFor(`document.fullscreenElement?.id==='chart-panel'`);
  assert.equal(await evaluate(`document.fullscreenElement.contains(document.querySelector('#chart-export-visible'))`),true);
  await evaluate(`document.exitFullscreen()`);await waitFor(`!document.fullscreenElement`);
  const axesAndView=await evaluate(`(async()=>{
    document.querySelector('#chart-axes-form').closest('details').open=true;
    for(const [axis,min,max] of [['temperature',10.5,32.5],['humidity',25,90]]){document.querySelector('#axis-'+axis+'-mode').value='manual';document.querySelector('#axis-'+axis+'-mode').dispatchEvent(new Event('change'));document.querySelector('#axis-'+axis+'-min').value=min;document.querySelector('#axis-'+axis+'-max').value=max;}
    document.querySelector('#chart-axes-form').requestSubmit();await new Promise(r=>setTimeout(r,0));
    state.chart.dispatchAction({type:'dataZoom',start:30,end:60});state.chart.dispatchAction({type:'legendToggleSelect',name:'Relative Feuchte'});
    document.querySelector('#chart-view-save').click();const stored=readChartViews().find(v=>v.key===rangeIdentity());
    const before=state.chart.getOption().yAxis.map(a=>[a.min,a.max]);document.querySelector('#axis-temperature-min').value='40';let rejected=false;try{applyAxes(new Event('submit'));}catch{rejected=true;}updateAxisForm();
    const unchanged=JSON.stringify(before)===JSON.stringify(state.chart.getOption().yAxis.map(a=>[a.min,a.max]));
    document.querySelector('#chart-axes-reset').click();document.querySelector('#period').value='6';await loadHistory();await loadChartView();
    const restored={axes:state.chart.getOption().yAxis.map(a=>[a.min,a.max]),zoom:state.chart.getOption().dataZoom[0].start,selection:state.chart.getOption().legend[0].selected['Relative Feuchte'],range:chartRange()};
    let invalidView=false;try{validateChartView({...stored,zoom:{start:-1,end:60}});}catch{invalidView=true;}
    return {stored,before,rejected,unchanged,restored,invalidView};
  })()`);
  assert.deepEqual(axesAndView.before,[[10.5,32.5],[25,90]]);assert.equal(axesAndView.rejected,true);assert.equal(axesAndView.unchanged,true);assert.equal(axesAndView.invalidView,true);
  assert.deepEqual(axesAndView.restored.axes,axesAndView.before);assert.equal(axesAndView.restored.zoom,30);assert.equal(axesAndView.restored.selection,false);assert.deepEqual(axesAndView.restored.range,axesAndView.stored.range);
  await send('Page.reload');
  await waitFor(`typeof state!=='undefined'&&state.chartData&&state.query&&document.querySelector('#chart-view-load').disabled===false`);
  await click('#chart-view-load');await waitFor(`document.querySelector('#chart-view-status').textContent.includes('Ansicht geladen')`);
  assert.equal(await evaluate(`state.chart.getOption().yAxis[0].min`),10.5);assert.equal(await evaluate(`state.chart.getOption().dataZoom[0].start`),30);assert.equal(await evaluate(`state.chart.getOption().legend[0].selected['Relative Feuchte']`),false);
  await evaluate(`document.querySelector('#chart-axes-reset').click();document.querySelector('#chart-reset').click();state.chart.dispatchAction({type:'legendToggleSelect',name:'Relative Feuchte'});localStorage.removeItem(CHART_VIEW_KEY);updateChartControls();document.querySelector('#period').value='24';document.querySelector('#custom-period').hidden=true;loadHistory()`);
  await waitFor(`state.query&&!state.query.has('snapshot')&&document.querySelector('#period').value==='24'&&state.chart.getOption().dataZoom[0].start===0`);
  await click('[data-page="sites"]');await waitFor(`sitesData!==null`);
  assert.equal(await evaluate(`document.querySelector('.source-strip').hidden`),true);
  await evaluate(`document.querySelector('#site-name').value='Synthetische Fensternische';document.querySelector('#site-room').value='Testraum';document.querySelector('#site-name').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#site-form').requestSubmit()`);
  await waitFor(`document.querySelector('#site-draft-status').textContent==='Messstelle lokal gespeichert.'`);
  const siteId=await evaluate(`siteEditing`);assert.ok(siteId.startsWith('site-'));
  await evaluate(`document.querySelector('#assignment-logger').value='bt06-12345678';document.querySelector('#assignment-site').value=${JSON.stringify(siteId)};document.querySelector('#assignment-site').dispatchEvent(new Event('change'));document.querySelector('#site-assign').click()`);
  await waitFor(`sitesData.active_assignments.length===1&&!siteBusy`);
  await evaluate(`document.querySelector('#site-name').value='Umbenannte Testmessstelle';document.querySelector('#site-air').value='66';document.querySelector('#site-name').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#site-form').requestSubmit()`);
  await waitFor(`sitesData.assignment_count===2&&!siteBusy`);
  const siteHistory=await evaluate(`api('sites/assignments?logger=bt06-12345678')`);
  assert.equal(siteHistory.assignments[0].site_snapshot.name,'Umbenannte Testmessstelle');assert.equal(siteHistory.assignments[1].site_snapshot.name,'Synthetische Fensternische');assert.equal(siteHistory.assignments[0].site_id,siteId);
  const staleSiteDraft=await evaluate(`(async()=>{document.querySelector('#site-name').value='Ungespeicherter Entwurf';document.querySelector('#site-name').dispatchEvent(new Event('input',{bubbles:true}));const values=siteDefaults();values.name='Zweiter Testort';await post('sites/save',{revision:sitesData.revision,id:null,values});await loadSites();return {name:document.querySelector('#site-name').value,blocked:document.querySelector('#site-save').disabled};})()`);
  assert.equal(staleSiteDraft.name,'Ungespeicherter Entwurf');assert.equal(staleSiteDraft.blocked,true);
  await click('#site-reset');await evaluate(`document.querySelector('#site-list .button-row button:last-child').click()`);
  assert.equal(await evaluate(`document.querySelector('#risk-air').value`),'66');assert.ok(await evaluate(`document.querySelector('#risk-status').textContent.includes('Kriterien von Umbenannte')`));
  await click('[data-page="sites"]');await waitFor(`!siteBusy&&document.querySelector('#site-unassign').disabled===false`);await click('#site-unassign');await waitFor(`sitesData.active_assignments.length===0&&!siteBusy`);
  await click('[data-page="events"]');await waitFor(`document.querySelector('#events-status').textContent.includes('Ereignisse geladen')`);
  assert.equal(await evaluate(`document.querySelector('.source-strip').hidden&&document.querySelector('#source-notice').hidden`),true);
  assert.ok(await evaluate(`document.querySelector('#events-values').textContent.includes('Anwendung gestartet')`));
  await evaluate(`document.querySelector('#events-type').value='application.started';document.querySelector('#events-type').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#events-form').requestSubmit()`);
  await waitFor(`document.querySelector('#events-status').textContent.includes('Ereignisse geladen')`);
  const eventExport=await evaluate(`(async()=>{const click=HTMLAnchorElement.prototype.click;let href;try{HTMLAnchorElement.prototype.click=function(){href=this.href;};document.querySelector('#events-export').click();await new Promise(r=>setTimeout(r,0));}finally{HTMLAnchorElement.prototype.click=click;}const url=new URL(href),csv=await fetch(url).then(r=>r.text());return {limited:url.searchParams.has('limit'),type:url.searchParams.get('type'),hasStart:csv.includes('application.started')};})()`);
  assert.equal(eventExport.limited,false);assert.equal(eventExport.type,'application.started');assert.equal(eventExport.hasStart,true);
  const eventStale=await evaluate(`(async()=>{const originalApi=api;let release;try{api=async()=>new Promise(resolve=>{release=resolve;});const pending=loadEvents();document.querySelector('#events-level').value='error';document.querySelector('#events-level').dispatchEvent(new Event('input',{bubbles:true}));release({});await pending;return document.querySelector('#events-table').hidden&&document.querySelector('#events-export').disabled;}finally{api=originalApi;document.querySelector('#events-level').value='';}})()`);assert.equal(eventStale,true);
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
  await click('[data-page="sites"]');await waitFor(`sitesData.sites.length===2`);await screenshot('sites-mobile.png');assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="export"]');await click('#export-prepare');await waitFor(`document.querySelector('#export-status').textContent.includes('Spaltenauswahl vorbereitet.')`);await screenshot('export-mobile.png');assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="events"]');await waitFor(`document.querySelector('#events-status').textContent.includes('Ereignisse geladen')`);await screenshot('events-mobile.png');assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="statistics"]');await click('#statistics-range-button');await waitFor(`document.querySelector('#statistics-table').hidden===false`);await screenshot('statistics-mobile.png');assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await click('[data-page="climate"]');await screenshot('climate-mobile.png');assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
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
  const unitDraft=await evaluate(`(()=>{const saved=${JSON.stringify(observed)};updateDeviceDraft(saved,true);const input=document.querySelector('#device-draft-unit');const before=input.value;input.value='F';input.dispatchEvent(new Event('input',{bubbles:true}));const values=deviceDraftValues();updateDeviceDraft(saved,true);return {before,values,reset:input.value};})()`);
  assert.equal(unitDraft.before,'C');assert.equal(unitDraft.values.temperature_unit,'F');assert.equal(unitDraft.reset,'C');
  assert.equal(unitDraft.values.record_interval_seconds,observed.values.record_interval_seconds);
  const alarmDraft=await evaluate(`(()=>{const saved=${JSON.stringify(observed)};updateDeviceDraft(saved,true);const enabled=document.querySelector('#device-draft-humidity-low-enabled'),limit=document.querySelector('#device-draft-humidity-high-limit');enabled.checked=true;limit.value='72.5';const values=deviceDraftValues();updateDeviceDraft(saved,true);const reset=enabled.checked;const f=JSON.parse(JSON.stringify(saved));f.values.temperature_unit='F';updateDeviceDraft(f,true);const blocked=document.querySelector('#device-draft-temperature-high-limit').disabled;const omitted=!('temperature_alarm_high_limit' in deviceDraftValues());updateDeviceDraft(saved,true);return {values,reset,blocked,omitted};})()`);
  assert.equal(alarmDraft.values.humidity_alarm_low_enabled,true);assert.equal(alarmDraft.values.humidity_alarm_high_limit,72.5);assert.equal(alarmDraft.reset,false);assert.equal(alarmDraft.blocked,true);assert.equal(alarmDraft.omitted,true);
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
  const report={passed:true,checks:['empty state','generator','three cards','chart canvas','dew point curve and climate calculator with stale response guard','original-row humidity phases, explicit surface assumption and visible-range analysis','original-row statistics, visible range, exact CSV and stale reply guard','persistent event table, filters, full filtered CSV and source separation','selection climate CSV, mandatory provenance and exact export scopes','measuring sites, assignment history and stale draft protection','zoom preservation','period presets, previous/next and original-resolution visible CSV','DST fold navigation and fullscreen controls','manual axes, invalid range guard and saved view restored after reload','save settings','load settings preview','load settings save','390px no overflow','BLE missing dependency state','live/simulation source switch with synthetic fixture','live CSV export','manual zoom pauses live follow','device calendar axis and warning','unverified original history CSV','device calendar custom range','switch back to simulation','prefix extension grouped without duplicate points','earlier snapshots accessible','incremental button availability','explicit timezone assignment and derived export','later data stays unconfirmed','auto sync remains off after saving interval','automatic attempt never requests button press','read-only settings values and unknown radio meaning','settings read unavailable without selection','settings job progress, button signal, timeout preserves prior stand, and success shown locally','draft diff preserves broadcast counterpart, warns of data loss, invalidates on edit, blocks stale base, and resets explicitly','25 minute recording draft, full preparation summary, two explicit confirmations, edit invalidation and uncertain write display','parameter verification never guesses recording state from zero summary','alarm limit and activation draft, reset and Fahrenheit guard','no JS exceptions','no external requests'],screenshots:screenshotCount};
  await writeFile(join(artifacts,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{
  if(browser){try{await send('Browser.close',{},null);}catch{}if(browser.exitCode===null){browser.kill('SIGTERM');await new Promise(resolve=>{browser.once('exit',resolve);setTimeout(resolve,5000);});}}
  if(app){app.kill('SIGTERM');await new Promise(resolve=>{if(app.exitCode!==null)resolve();else{app.once('exit',resolve);setTimeout(resolve,5000);}});}
  for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('Browser closed'));}pending.clear();
  await rm(scratch,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
