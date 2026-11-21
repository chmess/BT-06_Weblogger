// Optional UI verification with installed Chromium and Node, no npm dependencies.
import {spawn} from 'node:child_process';
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
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  const report={passed:true,checks:['empty state','generator','three cards','chart canvas','zoom preservation','save settings','load settings preview','load settings save','390px no overflow','BLE missing dependency state','no JS exceptions','no external requests'],screenshots:6};
  await writeFile(join(artifacts,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{
  if(browser){try{await send('Browser.close',{},null);}catch{}browser.kill('SIGTERM');}
  if(app){app.kill('SIGTERM');await new Promise(resolve=>{if(app.exitCode!==null)resolve();else{app.once('exit',resolve);setTimeout(resolve,5000);}});}
  for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('Browser closed'));}pending.clear();
  await rm(scratch,{recursive:true,force:true});
}
