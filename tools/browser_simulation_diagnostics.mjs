import assert from 'node:assert/strict';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {join} from 'node:path';

export async function runSimulationDiagnostics({evaluate,waitFor,click,screenshot,send,scratch}){
  await waitFor(`state.snapshots.length===1`);
  await click('[data-page="diagnostics"]');assert.equal(await evaluate(`document.querySelector('#simulation-check').disabled`),true);
  await click('[data-page="simulation"]');
  await evaluate(`document.querySelector('#simulation-form [name=days]').value='1';document.querySelector('#simulation-form [name=interval_minutes]').value='60';document.querySelector('#simulation-form [name=scenario]').value='gaps';document.querySelector('#simulation-form').requestSubmit()`);
  await waitFor(`state.runs.length===1&&document.querySelector('#chart-caption').textContent.includes('Testwerte')`);
  const run=await evaluate(`state.runs[0]`);
  await click('[data-page="diagnostics"]');assert.equal(await evaluate(`document.querySelector('#simulation-check-select').options.length`),1);
  await click('#simulation-check');await waitFor(`!simulationCheckBusy&&document.querySelector('#simulation-check-status').textContent.includes('Strukturprüfung ohne Befund')`);
  assert.ok(await evaluate(`document.querySelector('#simulation-check-summary').textContent.includes('Vollständig geprüfte Testmessstellen3')`));
  assert.ok(await evaluate(`document.querySelector('#simulation-check-status').textContent.includes('Keine Referenz-Prüfsummen')`));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await screenshot('simulation-diagnostics-mobile.png');
  const folder=join(scratch,'data','simulation',run.id,run.loggers[0].id),year=(await readdir(folder)).sort()[0],month=(await readdir(join(folder,year))).sort()[0];
  const path=join(folder,year,month),original=await readFile(path);await writeFile(path,Buffer.concat([original,Buffer.from('synthetic damage')]));
  try{
    await click('#simulation-check');await waitFor(`!simulationCheckBusy&&document.querySelector('#simulation-check-status').textContent.includes('Fehler gefunden')`);
    assert.deepEqual(await readFile(path),Buffer.concat([original,Buffer.from('synthetic damage')]));
  }finally{await writeFile(path,original);}
  await click('#simulation-check');await waitFor(`!simulationCheckBusy&&document.querySelector('#simulation-check-status').textContent.includes('Strukturprüfung ohne Befund')`);
  return ['no run disables action','generated gapped run verifies','counts and checksum limitation visible','390px width','damage reported without repair','restored test original verifies'];
}
