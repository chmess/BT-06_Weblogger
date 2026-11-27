import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

export async function runHistoryDiagnostics({evaluate,waitFor,click,screenshot,send,scratch}){
  await waitFor(`state.snapshots.length===1`);
  await click('[data-page="diagnostics"]');
  assert.equal(await evaluate(`document.querySelector('#history-check-select').options.length`),1);
  const identity=await evaluate(`({logger:state.snapshots[0].logger,id:state.snapshots[0].id})`);
  await click('#history-check');await waitFor(`!historyCheckBusy&&document.querySelector('#history-check-status').textContent.includes('Prüfung ohne Befund')`);
  assert.ok(await evaluate(`document.querySelector('#history-check-summary').textContent.includes('Werte im geprüften Gesamtstand3')`));
  assert.ok(await evaluate(`document.querySelector('#history-check-summary').textContent.includes('Ungeprüft; keine Uhrkorrektur')`));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await screenshot('history-diagnostics-mobile.png');
  const path=join(scratch,'data','data','history',identity.logger,identity.id,'capture.csv');const original=await readFile(path);
  await writeFile(path,Buffer.concat([original,Buffer.from('synthetic corruption')]));
  try{
    await click('#history-check');await waitFor(`!historyCheckBusy&&document.querySelector('#history-check-status').textContent.includes('Fehler gefunden')`);
    assert.deepEqual(await readFile(path),Buffer.concat([original,Buffer.from('synthetic corruption')]));
  }finally{await writeFile(path,original);}
  await click('#history-check');await waitFor(`!historyCheckBusy&&document.querySelector('#history-check-status').textContent.includes('Prüfung ohne Befund')`);
  await evaluate(`state.snapshots=[];historyCheckOptions()`);
  assert.equal(await evaluate(`document.querySelector('#history-check').disabled`),true);
  return ['explicit selected archive verification','checked counts and unverified clock','390px width','damaged capture reported without repair','restored original verifies again','no archive disables action'];
}
