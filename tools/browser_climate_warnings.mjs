// Display-state checks only; receiver persistence and warning transitions use Python tests.
import assert from 'node:assert/strict';

export async function runClimateWarnings({evaluate,waitFor,click,screenshot,send}){
  await waitFor(`state.live?.warnings&&state.liveLoggers.length===2`);
  await evaluate(`setSource('live');go('overview')`);
  assert.equal(await evaluate(`document.querySelector('#live-warnings').hidden`),false);
  assert.ok(await evaluate(`document.querySelector('#live-warnings-status').textContent.includes('Noch keine zugeordneten')`));
  const untouched=await evaluate(`api('live').then(data=>data.warnings.entries.length)`);assert.equal(untouched,0);
  await evaluate(`window.originalWarningStatus=state.live.warnings;window.warningFixture={started_at:new Date().toISOString(),error:null,active_count:0,entries:[{logger:'bt06-12345678',site_id:'site-'+'a'.repeat(32),site_name:'Synthetischer Anzeigezustand',criteria:{air_threshold:70,surface_threshold:80,hysteresis:2,minimum_minutes:60,surface_mode:'fixed',surface_value:15},last_stored_at:new Date().toISOString(),reason:null,channels:{air:{state:'pending',value_pct:75,phase_seconds:1800,event_saved:null},surface:{state:'below_threshold',value_pct:60,phase_seconds:0,event_saved:null}}}]};state.live.warnings=warningFixture;renderWarnings()`);
  assert.ok(await evaluate(`document.querySelector('#live-warnings-values').textContent.includes('Mindestdauer noch nicht erreicht')`));
  assert.ok(await evaluate(`document.querySelector('#live-warnings-values').textContent.includes('15,0 °C konstant')`));
  await evaluate(`warningFixture.active_count=1;warningFixture.entries[0].channels.air={state:'warning',value_pct:75,phase_seconds:3600,event_saved:false};renderWarnings()`);
  assert.ok(await evaluate(`document.querySelector('#live-warnings-status').textContent.includes('1 aktive')`));
  assert.ok(await evaluate(`document.querySelector('#live-warnings-values').textContent.includes('Warnung aktiv')&&document.querySelector('#live-warnings-values').textContent.includes('Ereignisspeicherung nicht bestätigt')`));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=window.innerWidth`),true);
  await screenshot('climate-warnings-mobile.png');
  await evaluate(`warningFixture.active_count=0;warningFixture.entries[0].reason='sample_gap';warningFixture.entries[0].channels.air.state='unknown';renderWarnings()`);
  assert.ok(await evaluate(`document.querySelector('#live-warnings-values').textContent.includes('Unbekannt / Beurteilung unterbrochen')&&document.querySelector('#live-warnings-values').textContent.includes('Lücke seit letztem')`));
  await evaluate(`warningFixture.error='Synthetischer Auswertungsfehler';renderWarnings()`);
  assert.equal(await evaluate(`document.querySelector('#live-warnings-status').textContent`),'Synthetischer Auswertungsfehler');
  await evaluate(`setSource('simulation')`);assert.equal(await evaluate(`document.querySelector('#live-warnings').hidden`),true);
  await evaluate(`setSource('device')`);assert.equal(await evaluate(`document.querySelector('#live-warnings').hidden`),true);
  await evaluate(`state.live.warnings=originalWarningStatus;renderWarnings();delete window.warningFixture;delete window.originalWarningStatus`);
  assert.equal(await evaluate(`api('live').then(data=>data.warnings.entries.length)`),0);
  return ['no retrospective warning from preexisting CSV','pending duration display','explicit surface assumption','active warning and unconfirmed event display','unknown gap state','evaluation error display','390px width','simulation/device separation','display fixtures never modify backend'];
}
