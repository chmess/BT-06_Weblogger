'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {settings: null, saved: null, csrf: '', runs: [], run: null, logger: null, chart: null, chartData: null, selection: {}, query: null, loading: 0, source:'simulation', live:null, liveLoggers:[], follow:true, snapshots:[], series:[], snapshot:null, sync:null, autoSync:null, timeAssignment:null};
const titles = {overview:'Übersicht', history:'Klimaverlauf', simulation:'Testdaten', climate:'Taupunkt / Feuchte', statistics:'Statistik', events:'Ereignisse', export:'Export', sites:'Messstellen', logger:'Logger / Bluetooth', settings:'Einstellungen', diagnostics:'Diagnose'};
const scenarios = {daily:'Tagesgang',humidity:'Feuchtespitzen',ventilation:'Lüftung',gaps:'Datenlücken'};
const number = (value, digits=1) => value == null ? '–' : new Intl.NumberFormat('de-DE', {maximumFractionDigits:digits,minimumFractionDigits:digits}).format(value);
function notice(message, error=false) { const box=$('#notice'); box.textContent=message; box.hidden=false; box.classList.toggle('error', error); }
async function api(path, options={}) {
  const response=await fetch(`api/${path}`, options);
  if(!response.ok) { const error=await response.json().catch(()=>({error:`HTTP ${response.status}`})); throw new Error(error.error); }
  return response.json();
}
function post(path, value) { return api(path,{method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(value)}); }
function guard(task) { return async (...args)=>{try { await task(...args); } catch(error) { notice(error.message,true); }}; }
function date(value) { return new Intl.DateTimeFormat('de-DE',{dateStyle:'short',timeStyle:'short',timeZone:state.saved?.timezone||'Europe/Berlin'}).format(new Date(value)); }
function go(page) {
  if(!titles[page]) page='overview';
  for(const section of document.querySelectorAll('.page')) section.hidden=section.id!==`page-${page}`;
  for(const button of document.querySelectorAll('[data-page]')) { if(button.dataset.page===page) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current'); }
  $('#page-title').textContent=titles[page];
  if(location.hash!==`#${page}`) history.replaceState(null,'',`#${page}`);
  $('.source-strip').hidden=['events','sites'].includes(page);$('#source-notice').hidden=['events','sites'].includes(page);
  if(page==='sites')loadSites().catch(error=>notice(error.message,true));
  if(page==='events')loadEvents().catch(error=>notice(error.message,true));
  if(page==='history') { if(!state.chart) initChart(); state.chart?.resize(); }
}
function chartDate(value) { return state.source==='device'?new Intl.DateTimeFormat('de-DE',{dateStyle:'short',timeStyle:'short',timeZone:'UTC'}).format(new Date(value)):date(value); }
function element(tag, text, className) { const node=document.createElement(tag); if(text!=null) node.textContent=text; if(className) node.className=className; return node; }
function downloadSettings(value) {
  const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'});
  const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='bt06-settings.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}
function formSettings() {
  const input=name=>$('#settings-form').elements.namedItem(name).value;
  return {schema_version:1,theme:input('theme'),timezone:input('timezone'),refresh_seconds:Number(input('refresh_seconds')),default_hours:Number(input('default_hours')),humidity_warning:Number(input('humidity_warning')),humidity_critical:Number(input('humidity_critical'))};
}
function checkSettings(value) {
  const fields=['schema_version','theme','timezone','refresh_seconds','default_hours','humidity_warning','humidity_critical'].sort();
  if(!value || typeof value!=='object' || JSON.stringify(Object.keys(value).sort())!==JSON.stringify(fields) || value.schema_version!==1 || !['dark','light'].includes(value.theme)) throw new Error('Unbekanntes Einstellungsformat.');
  try {new Intl.DateTimeFormat('de-DE',{timeZone:value.timezone}).format();}catch{throw new Error('Ungültige Zeitzone.');}
  for(const [field,low,high] of [['refresh_seconds',5,300],['default_hours',1,2160],['humidity_warning',1,99],['humidity_critical',2,100]]) if(typeof value[field]!=='number' || !Number.isFinite(value[field]) || value[field]<low || value[field]>high) throw new Error(`Ungültiger Wert: ${field}`);
  if(value.humidity_warning>=value.humidity_critical) throw new Error('Warnschwelle muss unter der kritischen Schwelle liegen.');
  return value;
}
function fillSettings(value) {
  for(const [key,val] of Object.entries(value)) {const input=$('#settings-form').elements.namedItem(key); if(input) input.value=val;}
  dirty();
}
function dirty() { const changed=!!state.settingsImport||JSON.stringify(formSettings())!==JSON.stringify(state.saved); $('#dirty').textContent=changed?'Ungespeichert':'Gespeichert'; $('#dirty').classList.toggle('warning',changed); }
let settingsBusy=false,settingsFileRevision=0;
function settingsControls(){for(const input of document.querySelectorAll('#settings-form input,#settings-form select,#settings-form button,#settings-import input,#settings-import button'))input.disabled=settingsBusy;$('#settings-include-sites').disabled=settingsBusy||!!state.settingsImport?.legacy;$('#settings-save').disabled=settingsBusy||!!state.settingsImport&&!state.settingsImport.token;}
function invalidateSettingsPreview(){if(state.settingsImport){state.settingsImport.token=null;$('#settings-import-status').textContent='Entwurf geändert; Vorschau vor Save Settings aktualisieren.';$('#settings-import-preview').replaceChildren();}dirty();settingsControls();}
function clearSettingsImport(){state.settingsImport=null;$('#settings-import').hidden=true;$('#settings-import-preview').replaceChildren();dirty();settingsControls();}
async function previewSettingsImport(){
  const staged=state.settingsImport;if(!staged)throw new Error('Zuerst eine Datei wählen.');const settings=checkSettings(formSettings());staged.token=null;settingsBusy=true;settingsControls();$('#settings-import-status').textContent='Datei und lokale Historie werden geprüft …';
  try{
    const plan=await post('settings/preview',{document:staged.document,include_sites:$('#settings-include-sites').checked,settings});
    if(state.settingsImport!==staged)return;staged.token=plan.token;const target=$('#settings-import-preview');target.replaceChildren();
    const changes=element('dl');for(const item of plan.settings_changes)changes.append(element('dt',item.field),element('dd',`${item.before} → ${item.after}`));target.append(changes);
    target.append(element('p',`${plan.added_sites} neue / ${plan.updated_sites} geänderte Messstellen · ${plan.added_intervals} zusätzliche historische Intervalle · ${plan.preserved_active_loggers} vorhandene aktive Loggerbelegungen bleiben erhalten.`));
    for(const change of plan.site_changes){const details=element('details'),list=element('dl');details.append(element('summary',(change.before?'Ändern: ':'Neu: ')+change.after.name+' · '+change.id.slice(-6)));for(const [key,label] of [['name','Name'],['room','Raum'],['description','Beschreibung']])list.append(element('dt',label),element('dd',`${change.before?.[key]||'–'} → ${change.after[key]||'–'}`));for(const key of Object.keys(change.after.criteria))list.append(element('dt',key),element('dd',`${change.before?.criteria[key]??'–'} → ${change.after.criteria[key]??'–'}`));details.append(list);target.append(details);}
    $('#settings-import-status').textContent=(plan.legacy?'Ältere Programmeinstellungsdatei; Messstellen bleiben erhalten. ':'Gemeinsame Einstellungsdatei geprüft. ')+`Vorschau gilt ${Math.floor(plan.expires_in_seconds/60)} Minuten. Noch nichts übernommen.`;
  }catch(error){$('#settings-import-status').textContent='Vorschau fehlgeschlagen. Gegebenenfalls Messstellen abwählen und neu prüfen.';throw error;}finally{settingsBusy=false;settingsControls();}
}
async function saveAllSettings(event){
  event.preventDefault();const settings=checkSettings(formSettings());settingsBusy=true;settingsControls();
  try{
    let document;
    if(state.settingsImport){if(!state.settingsImport.token)throw new Error('Importvorschau zuerst prüfen.');document=await post('settings/apply',{token:state.settingsImport.token});}
    else{await post('settings',settings);document=await api('settings/download');}
    state.saved=document.settings;clearSettingsImport();fillSettings(state.saved);applySettings();if(sitesData)await loadSites();downloadSettings(document);notice('Einstellungen gespeichert; gemeinsame JSON-Datei zum Download bereitgestellt.');
  }catch(error){if(state.settingsImport)state.settingsImport.token=null;throw error;}finally{settingsBusy=false;settingsControls();}
}
async function loadSettingsFile(event){
  const file=event.target.files[0];if(!file)return;const revision=++settingsFileRevision;
  try{
    if(file.size>8*1024*1024)throw new Error('Einstellungsdatei ist größer als 8 MiB.');const document=JSON.parse(await file.text());if(revision!==settingsFileRevision)return;const bundle=document.format==='BT06_SETTINGS';
    const settings=checkSettings(bundle?document.settings:document);state.settingsImport={document,legacy:!bundle,token:null};fillSettings(settings);$('#settings-import').hidden=false;$('#settings-include-sites').checked=bundle;await previewSettingsImport();notice('Datei nur geprüft. Vorschau lesen und mit Save Settings übernehmen.');
  }finally{event.target.value='';}
}
function applySettings() {
  document.documentElement.dataset.theme=state.saved.theme;
  if(state.chartData) renderChart(state.chartData);
}
function addOption(select, value, text) { const option=element('option',text); option.value=value; select.append(option); }
async function refreshRuns(preferRun) {
  state.runs=(await api('runs')).runs;
  state.run=state.runs.find(r=>r.id===(preferRun||state.run?.id))||state.runs[0]||null;
  const select=$('#run-select'); select.replaceChildren();
  for(const run of state.runs) addOption(select,run.id,`${date(run.created_at)} · ${run.options.days} Tage · ${scenarios[run.options.scenario]||run.options.scenario}`);
  select.value=state.run?.id||'';
  chooseLogger();
  const list=$('#run-list'); list.replaceChildren();
  if(!state.runs.length) list.append(element('p','Noch keine Testläufe.','muted'));
  for(const run of state.runs) {
    const row=element('div',null,'run-item'), details=element('div');
    details.append(element('strong',`${date(run.created_at)} · ${run.options.days} Tage`),element('p',`${scenarios[run.options.scenario]||run.options.scenario} · ${run.options.interval_minutes} min · Seed ${run.options.seed} · ${run.loggers.reduce((sum,l)=>sum+l.count,0).toLocaleString('de-DE')} Werte`));
    const button=element('button','Ansehen','secondary'); button.addEventListener('click',guard(async()=>{setSource('simulation');await refreshRuns(run.id);go('history');await loadHistory();}));
    row.append(details,button);list.append(row);
  }
  await renderCards();
}
let historySites=[];
function updateHistorySites(data=null){
  if(data)historySites=data.sites;
  const select=$('#history-site'),previous=select.value;select.replaceChildren();addOption(select,'','Alle gespeicherten Empfänge');
  for(const site of historySites)addOption(select,site.id,site.name+(site.room?' · '+site.room:'')+' · '+site.id.slice(-6));
  select.value=historySites.some(site=>site.id===previous)?previous:'';
  $('#history-site-label').hidden=state.source!=='live';$('#history-site-note').hidden=state.source!=='live'||!select.value;
}
function selectedSite(){return state.source==='live'?$('#history-site').value:'';}
function siteReportLabel(result){const item=result.site_selection;return item?` · Messstelle ${item.site_id} (aktueller Name: ${item.current_name}) · Logger ${item.logger}`:'';}
function chooseLogger() {
  const select=$('#logger-select'), previous=state.logger;select.replaceChildren();
  const loggers=state.source==='live'?state.liveLoggers:state.source==='device'?[...new Set(state.snapshots.map(s=>s.logger))].map(id=>({id,name:'BT06 '+id.replace('bt06-','')})):state.run?.loggers||[];
  for(const logger of loggers) addOption(select,logger.id,logger.name);
  state.logger=loggers.find(l=>l.id===previous)?.id||loggers[0]?.id||null;
  select.value=state.logger||'';updateHistorySites();
  if(state.source==='device') populateSnapshots();
  $('#chart-export').disabled=!state.logger;$('#overview-export').disabled=!state.logger;
}
function climateSummary(value){
  if(!value||value.absolute_humidity_g_m3==null)return element('p','Berechnete Feuchtewerte nicht verfügbar (fehlende Eingaben oder außerhalb des Modells).','hint');
  return element('p',`Berechnet: Taupunkt ${number(value.dew_point_c)} °C · absolute Feuchte ${number(value.absolute_humidity_g_m3)} g/m³${value.dew_point_c==null?' · Taupunkt nicht im Modellbereich':''}`,'hint');
}
let climateRevision=0;
async function calculateClimate(event){
  event.preventDefault();const value={temperature_c:Number($('#climate-temperature').value),humidity_pct:Number($('#climate-humidity').value),surface_temperature_c:$('#climate-surface').value===''?null:Number($('#climate-surface').value)};
  if($('#climate-temperature').value===''||$('#climate-humidity').value==='')throw new Error('Lufttemperatur und Feuchte angeben.');
  const revision=++climateRevision,target=$('#climate-results');target.replaceChildren();$('#climate-status').textContent='Berechnung läuft …';
  let result;try{result=await post('climate/calculate',value);}catch(error){if(revision===climateRevision)$('#climate-status').textContent='Berechnung fehlgeschlagen.';throw error;}
  if(revision!==climateRevision)return;
  const pairs=[['Taupunkt',result.dew_point_c,'°C'],['Absolute Feuchte',result.absolute_humidity_g_m3,'g/m³'],['Sättigungsdampfdruck',result.saturation_pressure_hpa,'hPa'],['Wasserdampf-Partialdruck',result.vapor_pressure_hpa,'hPa'],['Oberflächentemperatur bei 70 % rF',result.critical_surface_70_c,'°C'],['Oberflächentemperatur bei 80 % rF',result.critical_surface_80_c,'°C'],['Oberfläche: Abstand zum Taupunkt',result.surface_dew_point_margin_c,'K']];
  for(const [label,reading,unit] of pairs)target.append(element('dt',label),element('dd',reading==null?'Nicht verfügbar':`${number(reading,2)} ${unit}`));
  target.append(element('dt','Rechnerische Oberflächenfeuchte'),element('dd',result.surface_relative_humidity_pct==null?'Keine Oberflächentemperatur angegeben':result.surface_relative_humidity_pct>=100?'≥ 100 % rF · Kondensationsbedingung':`${number(result.surface_relative_humidity_pct,1)} % rF`));
  $('#climate-status').textContent=(result.condensation_possible===true?'An der angenommenen Oberfläche ist die Kondensationsbedingung erreicht. ':result.condensation_possible===false?'An der angenommenen Oberfläche ist die Kondensationsbedingung rechnerisch nicht erreicht. ':'Keine Oberflächenbewertung ohne Annahme. ')+(result.status==='ok'?'Momentaufnahme; keine zeitabhängige Schimmelbewertung.':'Taupunkt nicht verfügbar: keine Feuchte oder außerhalb des Modellbereichs.');
}
async function copyClimateReading(){
  const revision=++climateRevision,key=rangeIdentity(),loaded=await loadHistory();if(!loaded||revision!==climateRevision||key!==rangeIdentity())return;const point=state.chartData?.latest;
  if(!point||point[1]==null||point[2]==null)throw new Error('Kein vollständiger Wert im ausgewählten Zeitraum.');
  $('#climate-temperature').value=point[1];$('#climate-humidity').value=point[2];
  $('#climate-input-source').textContent=`Übernommen aus ${state.source==='device'?'Loggerhistorie · Gerätezeit ungeprüft':state.source==='live'?'gespeicherten BLE-Empfängen':'synthetischen Testdaten'}: ${chartDate(point[0])}. Die Oberflächentemperatur bleibt eine manuelle Annahme.`;
  $('#climate-results').replaceChildren();$('#climate-status').textContent='Wert übernommen; zum Auswerten „Berechnen“ wählen.';
}
let riskRevision=0;
function updateRiskControls(){const mode=$('#risk-mode').value,input=$('#risk-value');input.disabled=mode==='none';input.required=mode!=='none';input.min=mode==='fixed'?-45:0;input.max=mode==='fixed'?60:50;$('#risk-surface-label').textContent=mode==='fixed'?'Angenommene Oberfläche (°C)':mode==='delta'?'Angenommene Differenz unter Lufttemperatur (K)':'Oberflächenwert (nicht verwendet)';}
function clearRisk(){riskRevision++;state.riskReport=null;$('#risk-results').replaceChildren();$('#risk-range').textContent='';$('#risk-status').textContent='Kriterien geändert; erneut auswerten.';}
function markRiskStale(){riskRevision++;if(state.riskReport)$('#risk-status').textContent='Ansicht oder Quelle geändert. Der Bericht gehört weiterhin zum unten genannten Zeitraum; für die neue Auswahl erneut auswerten.';}
function selectionSignature(){return JSON.stringify([rangeIdentity(),$('#period').value,$('#range-start').value,$('#range-end').value]);}
function renderRisk(result){
  const target=$('#risk-results');target.replaceChildren();
  for(const [key,title] of [['air','Luftfeuchte'],['surface','Oberfläche · Annahme'],['condensation','Kondensationsbedingung · Annahme']]){
    const metric=result[key],card=element('article',null,'panel');card.append(element('h3',title));
    if(!metric){card.append(element('p','Ohne Oberflächenannahme nicht ausgewertet.'));target.append(card);continue;}
    card.append(element('p',metric.status==='insufficient_data'?'Keine ausreichenden benachbarten Messpaare.':`${metric.qualified_phase_count} Phasen erreichen die gewählte Mindestdauer.`,metric.qualified_phase_count?'tag warning':'hint'));
    const list=element('dl');
    for(const [label,value] of [['Schwelle / Rücksetzgrenze',`${number(metric.threshold_pct)} / ${number(metric.release_pct)} %`],['Auswertbare Messpaarzeit',`${number(metric.observed_seconds/60)} min`],['Unbekannte Zeit',`${number(metric.unknown_seconds/60)} min`],['Zeit ab Schwelle',`${number(metric.above_threshold_seconds/60)} min`],['Längste Phase inkl. Hysterese',`${number(metric.longest_phase_seconds/60)} min`],['Mindestphasendauer',`${number(metric.minimum_seconds/60)} min`]])list.append(element('dt',label),element('dd',value));
    card.append(list);
    if(metric.status!=='evaluated')card.append(element('p','Datenabdeckung unvollständig; unbekannte Zeit ist keine unkritische Zeit.','hint'));
    if(metric.phases.length){const details=element('details'),items=element('ol');details.append(element('summary',`Phasen anzeigen (${metric.phases.length}${metric.omitted_phases?' von '+metric.phase_count:''})`));for(const phase of metric.phases)items.append(element('li',`${chartDate(phase.start_ms)} bis ${chartDate(phase.end_ms)} · ${number(phase.duration_seconds/60)} min · Spitze ${number(phase.peak_pct)} % · ${phase.qualified?'Mindestdauer erreicht':'kurze Phase'}${phase.left_censored||phase.right_censored?' · Rand oder Lücke begrenzt die Beobachtung':''}`));details.append(items);card.append(details);}
    target.append(card);
  }
  $('#risk-range').textContent=`${result.source}${siteReportLabel(result)}: ${result.range.start_ms==null?'kein Anfang':chartDate(result.range.start_ms)} bis ${result.range.end_ms==null?'kein Ende':chartDate(result.range.end_ms)}${result.clock_verified?'':' · Gerätekalender und UTC-Zuordnung ungeprüft'}. Oberflächenmodell: ${result.criteria.surface_mode==='none'?'keine Annahme':result.criteria.surface_mode==='fixed'?number(result.criteria.surface_value)+' °C konstant':number(result.criteria.surface_value)+' K unter Lufttemperatur'}.`;
  $('#risk-status').textContent='Auswertung aus Originalwerten abgeschlossen. Konfigurierbare Feuchteindikatoren; keine Schimmelwahrscheinlichkeit.';
}
function analysisQuery(visible=false){
  if(visible&&(!state.query||state.chartContext!==rangeIdentity()))throw new Error('Zuerst den Klimaverlauf für die aktuelle Auswahl laden.');
  const base=visible?new URLSearchParams(state.query):buildQuery();if(!base)throw new Error('Zuerst eine Datenquelle und einen Logger wählen.');
  const query=new URLSearchParams(base);
  if(visible){const range=chartRange(true);if(!range)throw new Error('Kein sichtbarer Zeitraum.');query.set('start',new Date(range.start).toISOString());query.set('end',new Date(range.end).toISOString());}
  return query;
}
async function analyzeRisk(visible=false){
  const signature=selectionSignature(),revision=++riskRevision,query=analysisQuery(visible);
  for(const [key,id] of [['air_threshold','#risk-air'],['surface_threshold','#risk-surface'],['hysteresis','#risk-hysteresis'],['minimum_minutes','#risk-minimum']]){if($(id).value==='')throw new Error('Alle Auswertekriterien angeben.');query.set(key,$(id).value);}
  query.set('surface_mode',$('#risk-mode').value);query.set('surface_value',$('#risk-mode').value==='none'?'':$('#risk-value').value);
  $('#risk-status').textContent='Originalwerte werden ausgewertet …';
  let result;try{result=await api('risk?'+query);}catch(error){if(revision===riskRevision)$('#risk-status').textContent='Auswertung fehlgeschlagen.';throw error;}
  if(revision!==riskRevision)return;if(signature!==selectionSignature()){$('#risk-status').textContent='Auswahl geändert; erneut auswerten.';return;}
  state.riskReport=result;renderRisk(result);
}
let statisticsRevision=0;
function markStatisticsStale(){statisticsRevision++;if(state.statisticsReport)$('#statistics-status').textContent='Auswahl geändert. Tabelle und CSV gehören weiterhin zum unten genannten Berichtszeitraum; für die neue Auswahl erneut auswerten.';else if(state.statisticsPending)$('#statistics-status').textContent='Auswahl geändert; erneut auswerten.';state.statisticsPending=false;}
function renderStatistics(result){
  const target=$('#statistics-values');target.replaceChildren();
  for(const [key,label,unit] of [['temperature_c','Temperatur','°C'],['humidity_pct','Relative Feuchte','% rF'],['dew_point_c','Taupunkt · berechnet','°C'],['absolute_humidity_g_m3','Absolute Feuchte · berechnet','g/m³']]){
    const metric=result.metrics[key],row=element('tr');row.append(element('th',`${label} (${unit})`));row.firstChild.scope='row';
    row.append(element('td',`${metric.valid_samples.toLocaleString('de-DE')} / ${metric.missing_samples.toLocaleString('de-DE')}`));
    for(const bound of ['minimum','maximum']){const cell=element('td',number(metric[bound]?.value,2));if(metric[bound])cell.title=chartDate(metric[bound].time_ms);row.append(cell);}
    for(const value of [metric.sample_mean,metric.time_weighted_mean])row.append(element('td',number(value,2)));
    row.append(element('td',`${number(metric.observed_seconds/60)} min`),element('td',`${number(metric.unknown_seconds/60)} min`));target.append(row);
  }
  $('#statistics-table').hidden=false;
  $('#statistics-range').textContent=`${result.source}${siteReportLabel(result)}: ${result.range.start_ms==null?'kein Anfang':chartDate(result.range.start_ms)} bis ${result.range.end_ms==null?'kein Ende':chartDate(result.range.end_ms)}${result.clock_verified?'':' · Gerätekalender und UTC-Zuordnung ungeprüft'}. ${result.raw_count.toLocaleString('de-DE')} Originalzeilen · ${result.gap_count} Zeitlücken/Zuordnungsgrenzen · erwartetes Messintervall ${number(result.interval_minutes)} min.`;
  $('#statistics-status').textContent='Statistik berechnet. Fehlende oder nicht abgedeckte Zeit bleibt je Größe unbekannt.';
}
async function analyzeStatistics(visible=false){
  const signature=selectionSignature(),revision=++statisticsRevision,query=analysisQuery(visible);
  state.statisticsReport=null;state.statisticsQuery=null;state.statisticsPending=true;$('#statistics-table').hidden=true;$('#statistics-export').disabled=true;$('#statistics-range').textContent='';$('#statistics-status').textContent='Originalwerte werden statistisch ausgewertet …';
  let result;try{result=await api('statistics?'+query);}catch(error){if(revision===statisticsRevision){state.statisticsPending=false;$('#statistics-status').textContent='Statistik fehlgeschlagen.';}throw error;}
  if(revision!==statisticsRevision)return;state.statisticsPending=false;
  if(signature!==selectionSignature()){$('#statistics-status').textContent='Auswahl geändert; erneut auswerten.';return;}
  state.statisticsReport=result;state.statisticsQuery=query;renderStatistics(result);$('#statistics-export').disabled=false;
}
function exportStatistics(){if(!state.statisticsQuery)throw new Error('Zuerst Statistik berechnen.');const link=document.createElement('a');link.href='api/export?'+state.statisticsQuery;link.click();}
let eventsRevision=0;
function invalidateEvents(){eventsRevision++;state.eventsQuery=null;$('#events-export').disabled=true;$('#events-table').hidden=true;$('#events-status').textContent='Filter geändert; erneut laden.';}
function eventsQuery(){
  const query=new URLSearchParams({limit:$('#events-limit').value});
  for(const field of ['logger','level','type'])if($(`#events-${field}`).value)query.set(field,$(`#events-${field}`).value);
  for(const field of ['start','end']){const raw=$(`#events-${field}`).value;if(raw){const dateValue=new Date(raw);if(!Number.isFinite(dateValue.getTime()))throw new Error('Ungültiger Ereigniszeitraum.');query.set(field,dateValue.toISOString());}}
  return query;
}
async function loadEvents(){
  const query=eventsQuery(),revision=++eventsRevision;$('#events-status').textContent='Ereignisse werden geladen …';$('#events-export').disabled=true;
  let result;try{result=await api('events?'+query);}catch(error){if(revision===eventsRevision){$('#events-status').textContent='Ereignisprotokoll konnte nicht gelesen werden; Originaldateien erhalten.';$('#events-table').hidden=true;}throw error;}
  if(revision!==eventsRevision)return;
  const chosen=$('#events-type').value;$('#events-type').replaceChildren();addOption($('#events-type'),'','Alle');for(const [key,label] of Object.entries(result.event_types))addOption($('#events-type'),key,label);$('#events-type').value=chosen;
  const target=$('#events-values');target.replaceChildren();const levels={info:'Information',warning:'Warnung',error:'Fehler'};
  for(const item of result.events){const row=element('tr');for(const value of [date(item.Zeitstempel),levels[item.Stufe],result.event_types[item.Typ],item.Logger||'–',item.Nachricht])row.append(element('td',value));target.append(row);}
  $('#events-table').hidden=false;state.eventsQuery=query;$('#events-export').disabled=false;
  $('#events-status').textContent=`${result.events.length} Ereignisse geladen${result.truncated?' · weitere Treffer vorhanden; CSV enthält alle passenden Einträge':''}.${result.log_status.failed_this_session?' '+result.log_status.failed_this_session+' Ereignisse in dieser Sitzung nicht dauerhaft bestätigt.':''}${result.log_status.error?' '+result.log_status.error:''}`;
}
function exportEvents(){if(!state.eventsQuery)throw new Error('Zuerst Ereignisse laden.');const query=new URLSearchParams(state.eventsQuery);query.delete('limit');const link=document.createElement('a');link.href='api/events/export?'+query;link.click();}
let exportRevision=0;
function exportSignature(){return selectionSignature()+'|'+$('#export-scope').value+'|'+($('#export-scope').value==='statistics'?state.statisticsQuery?.toString():'');}
function invalidateExport(){exportRevision++;state.exportBase=null;state.exportOptions=null;$('#export-choices').hidden=true;$('#export-download').disabled=true;$('#export-context').textContent='';$('#export-status').textContent='Auswahl geändert; Spaltenauswahl erneut vorbereiten.';}
function exportControls(){
  const climate=$('#export-climate').checked;$('#export-calculated-group').hidden=!climate;
  $('#export-download').disabled=!state.exportBase||exportSignature()!==state.exportSignature||(climate&&!$('#export-calculated-fields input:checked'));
  const options=state.exportOptions;if(options)$('#export-required').textContent='Automatisch erhalten: '+[...options.required_fields,...options.export_metadata,...(climate?options.calculated_metadata:[])].join(', ')+'.';
}
async function prepareExport(){
  const signature=exportSignature(),revision=++exportRevision,scope=$('#export-scope').value;
  let query;
  if(scope==='statistics'){
    if(!state.statisticsQuery)throw new Error('Zuerst einen Statistikbericht berechnen.');
    query=new URLSearchParams(state.statisticsQuery);
    const source=query.get('source')||'simulation',identity=[source,query.get('logger'),source==='simulation'?query.get('run'):null,source==='device'?query.get('snapshot'):null];if(query.get('site'))identity.push(query.get('site'));const key=JSON.stringify(identity);
    if(key!==rangeIdentity())throw new Error('Der Statistikbericht gehört zu einer anderen Datenquelle oder Loggerauswahl. Passende Auswahl im Klimaverlauf wählen.');
  }else query=analysisQuery(scope==='visible');
  $('#export-download').disabled=true;$('#export-status').textContent='Exportspalten werden vorbereitet …';
  let options;try{options=await api('export/options?'+query);}catch(error){if(revision===exportRevision)$('#export-status').textContent='Vorbereitung fehlgeschlagen.';throw error;}
  if(revision!==exportRevision)return;if(signature!==exportSignature()){$('#export-status').textContent='Auswahl geändert; erneut vorbereiten.';return;}
  state.exportBase=query;state.exportOptions=options;state.exportSignature=signature;
  const original=$('#export-original-fields'),calculated=$('#export-calculated-fields');original.replaceChildren();calculated.replaceChildren();
  for(const [fields,target,kind] of [[options.original_fields,original,'original'],[options.calculated_fields,calculated,'calculated']])for(const field of fields){const label=element('label',null,'inline-check'),input=element('input');input.type='checkbox';input.value=field;input.checked=true;input.dataset.exportField=kind;input.disabled=kind==='original'&&options.required_fields.includes(field);label.append(input,document.createTextNode(options.labels[field]||field));target.append(label);}
  $('#export-climate').checked=false;$('#export-choices').hidden=false;
  $('#export-context').textContent=`${({simulation:'Synthetische Testdaten',live:'BLE-Empfänge',device:'Loggerhistorie'})[query.get('source')]} · ${query.get('logger')}${query.get('site')?' · Messstelle '+query.get('site'):''} · ${query.has('start')?chartDate(query.get('start')):'Anfang'} bis ${query.has('end')?chartDate(query.get('end')):'Ende'}${query.get('source')==='device'?' · ungeprüfter Gerätekalender':''}`;
  $('#export-status').textContent='Spaltenauswahl vorbereitet. Der angezeigte Zeitraum bleibt für diesen Export fest.';exportControls();
}
async function downloadPreparedExport(){
  if(!state.exportBase||exportSignature()!==state.exportSignature)throw new Error('Auswahl zuerst erneut vorbereiten.');
  const query=new URLSearchParams(state.exportBase),fields=[...document.querySelectorAll('#export-original-fields input:checked')].map(input=>input.value);
  if($('#export-climate').checked){const derived=[...document.querySelectorAll('#export-calculated-fields input:checked')].map(input=>input.value);if(!derived.length)throw new Error('Mindestens eine berechnete Größe auswählen.');fields.push(...derived);query.set('climate','1');}
  query.set('fields',fields.join(','));const revision=exportRevision,signature=state.exportSignature;$('#export-download').disabled=true;$('#export-status').textContent='CSV aus Originalwerten wird erstellt …';
  try{
    const response=await fetch('api/export?'+query);if(!response.ok){const error=await response.json();throw new Error(error.error||'Export fehlgeschlagen.');}
    const blob=await response.blob();if(revision!==exportRevision||signature!==exportSignature()){$('#export-status').textContent='Auswahl während des Exports geändert; Download nicht ausgelöst.';return;}
    const link=document.createElement('a'),match=/filename="([^"]+)"/.exec(response.headers.get('Content-Disposition')||'');link.href=URL.createObjectURL(blob);link.download=match?.[1]||'bt06-auswahl.csv';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
    $('#export-status').textContent='CSV erstellt und Download gestartet.';
  }catch(error){$('#export-status').textContent='Export fehlgeschlagen; keine erfolgreiche Datei bestätigt.';throw error;}finally{exportControls();}
}
let sitesData=null,siteEditing=null,siteDraftRevision=null,siteDraftDirty=false,siteBusy=false,sitesRequest=0;
function siteDefaults(){return {name:'',room:'',description:'',criteria:{air_threshold:70,surface_threshold:80,hysteresis:2,minimum_minutes:60,surface_mode:'none',surface_value:null}};}
function siteCriteria(){const criteria={surface_mode:$('#site-mode').value,surface_value:$('#site-mode').value==='none'?null:Number($('#site-value').value)};for(const [key,id] of [['air_threshold','#site-air'],['surface_threshold','#site-surface'],['hysteresis','#site-hysteresis'],['minimum_minutes','#site-minimum']]){if($(id).value==='')throw new Error('Alle Auswertekriterien angeben.');criteria[key]=Number($(id).value);}if(criteria.surface_mode!=='none'&&$('#site-value').value==='')throw new Error('Oberflächenannahme vollständig angeben.');return criteria;}
function siteControls(){
  for(const input of document.querySelectorAll('#page-sites input,#page-sites select,#page-sites textarea,#page-sites button'))input.disabled=siteBusy;
  const mode=$('#site-mode').value;$('#site-value').disabled=siteBusy||mode==='none';$('#site-value').required=mode!=='none';$('#site-value').min=mode==='fixed'?-45:0;$('#site-value').max=mode==='fixed'?60:50;
  $('#site-save').disabled=siteBusy||!sitesData||siteDraftRevision!==sitesData.revision;
  const logger=$('#assignment-logger').value,site=$('#assignment-site').value,active=sitesData?.active_assignments||[],current=active.find(item=>item.logger===logger),occupied=active.find(item=>item.site_id===site&&item.logger!==logger);
  $('#site-assign').disabled=siteBusy||!logger||!site||current?.site_id===site;$('#site-unassign').disabled=siteBusy||!current;
  $('#assignment-preview').textContent=!logger?'Bekannten Logger wählen.':`Aktuell: ${current?current.site_snapshot.name:'keine Messstelle'}. ${site?'Ziel: '+(sitesData.sites.find(item=>item.id===site)?.name||'unbekannt')+'.':'Zielmessstelle wählen.'}${occupied?' Die bisherige Zuordnung des Zielortes zu '+occupied.logger+' endet dabei.':''}`;
}
function editSite(id,internal=false){
  if(siteBusy&&!internal)return;const site=id?sitesData?.sites.find(item=>item.id===id):siteDefaults();if(!site)return;
  siteEditing=id;for(const field of ['name','room','description'])$(`#site-${field}`).value=site[field];
  for(const [key,id] of [['air_threshold','#site-air'],['surface_threshold','#site-surface'],['hysteresis','#site-hysteresis'],['minimum_minutes','#site-minimum'],['surface_mode','#site-mode'],['surface_value','#site-value']])$(id).value=site.criteria[key]??'';
  siteDraftRevision=sitesData?.revision??null;siteDraftDirty=false;$('#site-form-title').textContent=id?'Messstelle bearbeiten':'Neue Messstelle';$('#site-draft-status').textContent='Entwurf zum aktuellen Messstellenstand. Noch nicht gespeichert.';siteControls();
}
function useSiteCriteria(site){
  if(siteBusy)return;for(const [key,id] of [['air_threshold','#risk-air'],['surface_threshold','#risk-surface'],['hysteresis','#risk-hysteresis'],['minimum_minutes','#risk-minimum'],['surface_mode','#risk-mode'],['surface_value','#risk-value']])$(id).value=site.criteria[key]??'';
  updateRiskControls();clearRisk();go('climate');$('#risk-status').textContent='Kriterien von '+site.name+' übernommen. Datenquelle und Zeitraum vor dem Auswerten prüfen.';
}
async function loadSites(force=false){
  const request=++sitesRequest;const [data,history]=await Promise.all([api('sites'),api('sites/assignments?limit=100')]);if(request!==sitesRequest)return;
  sitesData=data;updateHistorySites(data);if(siteDraftRevision===null&&siteEditing===null)siteDraftRevision=data.revision;const target=$('#site-list');target.replaceChildren();
  if(!data.sites.length)target.append(element('p','Noch keine Messstelle angelegt. Name und Kriterien unten eingeben.','hint'));
  for(const site of data.sites){const panel=element('article',null,'panel'),active=data.active_assignments.find(item=>item.site_id===site.id);panel.append(element('h3',site.name),element('p',`Raum: ${site.room||'–'} · aktuell zugeordnet: ${active?.logger||'kein Logger'}`),element('p',site.description||'Keine Beschreibung.','hint'),element('p','Stabile ID: '+site.id,'hint'));const buttons=element('div',null,'button-row'),edit=element('button','Diesen Stand bearbeiten','secondary'),criteria=element('button','Auswertekriterien übernehmen','secondary');edit.addEventListener('click',()=>editSite(site.id));criteria.addEventListener('click',()=>useSiteCriteria(site));buttons.append(edit,criteria);panel.append(buttons);target.append(panel);}
  const logger=$('#assignment-logger').value,site=$('#assignment-site').value;$('#assignment-logger').replaceChildren();addOption($('#assignment-logger'),'','Logger wählen');for(const id of data.available_loggers)addOption($('#assignment-logger'),id,id);$('#assignment-logger').value=logger;
  $('#assignment-site').replaceChildren();addOption($('#assignment-site'),'','Messstelle wählen');for(const item of data.sites)addOption($('#assignment-site'),item.id,item.name+(item.room?' · '+item.room:'')+' · '+item.id.slice(-6));$('#assignment-site').value=site;
  const rows=$('#site-history');rows.replaceChildren();for(const item of history.assignments){const row=element('tr');for(const value of [item.logger,item.site_snapshot.name,item.site_snapshot.room||'–',date(item.start),item.end?date(item.end):'laufend'])row.append(element('td',value));rows.append(row);}
  $('#sites-status').textContent=`${data.sites.length} Messstellen · ${data.assignment_count} Zuordnungsintervalle${history.truncated?' · Historientabelle auf 100 begrenzt':''}.`;
  if(force||!siteDraftDirty)editSite(siteEditing,true);else if(siteDraftRevision!==data.revision)$('#site-draft-status').textContent='Messstellenstand ersetzt; Entwurf bleibt erhalten. Vor dem Speichern aktuellen Stand übernehmen.';
  siteControls();
}
async function saveSite(event){
  event.preventDefault();if(!sitesData||siteDraftRevision!==sitesData.revision)throw new Error('Aktuellen Messstellenstand zuerst übernehmen.');
  const values={name:$('#site-name').value.trim(),room:$('#site-room').value.trim(),description:$('#site-description').value.trim(),criteria:siteCriteria()};siteBusy=true;siteControls();
  try{const result=await post('sites/save',{revision:siteDraftRevision,id:siteEditing,values});siteEditing=result.site.id;siteDraftDirty=false;await loadSites(true);$('#site-draft-status').textContent='Messstelle lokal gespeichert.';}finally{siteBusy=false;siteControls();}
}
async function assignSite(end=false){
  if(!sitesData)throw new Error('Messstellen zuerst laden.');const logger=$('#assignment-logger').value,site_id=end?null:$('#assignment-site').value;if(!logger||!end&&!site_id)throw new Error('Logger und Messstelle wählen.');siteBusy=true;siteControls();
  try{await post('sites/assign',{revision:sitesData.revision,logger,site_id});await loadSites();$('#sites-status').textContent='Zuordnung ab Hostzeit gespeichert; historische Intervalle erhalten.';}finally{siteBusy=false;siteControls();}
}
async function renderCards() {
  if(state.source==='live')return renderLiveCards();
  if(state.source==='device')return renderDeviceCards();
  const cards=$('#cards'); if(!state.run) return;
  const run=state.run;
  const values=await Promise.all(run.loggers.map(logger=>api(`history?${new URLSearchParams({run:run.id,logger:logger.id,end:run.options.end,start:new Date(new Date(run.options.end).getTime()-86400000).toISOString()})}`)));
  if(state.source!=='simulation'||state.run?.id!==run.id) return;
  cards.replaceChildren();
  run.loggers.forEach((logger,index)=>{
    const data=values[index], card=element('article',null,'card');
    card.append(element('div','SIMULATION · KEIN LIVEWERT','source'),element('h3',logger.name));
    const readings=element('div',null,'readings');
    for(const [label,val,unit,cls] of [['Temperatur',data.latest?.[1],'°C','temperature'],['Relative Feuchte',data.latest?.[2],'%','humidity']]) {
      const reading=element('div',null,'reading');reading.append(element('strong',`${number(val)} ${unit}`,cls),element('span',label));readings.append(reading);
    }
    card.append(climateSummary(data.climate?.latest));
    card.append(readings,element('p',`24 h: ${number(data.min_temperature)}–${number(data.max_temperature)} °C · ${number(data.min_humidity,0)}–${number(data.max_humidity,0)} % rF`,'hint'));
    card.append(element('time',data.latest?`Letzter Testwert: ${date(data.latest[0])}`:'Keine Werte im Zeitraum.'));
    const button=element('button','Verlauf ansehen','secondary');button.addEventListener('click',guard(async()=>{state.logger=logger.id;$('#logger-select').value=logger.id;go('history');await loadHistory();}));card.append(button);cards.append(card);
  });
}
function rangeIdentity(){const identity=[state.source,state.logger,state.source==='simulation'?state.run?.id:null,state.source==='device'?state.snapshot?.id:null];if(selectedSite())identity.push(selectedSite());return JSON.stringify(identity);}
function buildQuery() {
  if(!state.logger||state.source==='simulation'&&!state.run) return null;
  const query=new URLSearchParams({source:state.source,logger:state.logger});if(selectedSite())query.set('site',selectedSite());
  if(state.source==='simulation')query.set('run',state.run.id);
  if(state.source==='device'){if(!state.snapshot)return null;query.set('snapshot',state.snapshot.id);}
  const period=$('#period').value;
  if(period==='custom') {
    if(!$('#range-start').value||!$('#range-end').value) throw new Error('Beginn und Ende angeben. Freie Zeitangaben gelten in der Browser-Zeitzone.');
    const suffix=state.source==='device'?'Z':'',shifted=state.shiftedRange;
    const exact=shifted&&shifted.identity===rangeIdentity()&&shifted.inputs[0]===$('#range-start').value&&shifted.inputs[1]===$('#range-end').value;
    const start=new Date(exact?shifted.start:$('#range-start').value+suffix),end=new Date(exact?shifted.end:$('#range-end').value+suffix);
    if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime()))throw new Error('Ungültige Zeitangabe.');
    if(start>end) throw new Error('Beginn liegt nach dem Ende.');
    query.set('start',start.toISOString());query.set('end',end.toISOString());
  } else if(Number(period)>0) {
    const end=state.source==='live'?new Date():state.source==='device'?new Date(state.snapshot.last_device_calendar+'Z'):new Date(state.run.options.end);query.set('end',end.toISOString());query.set('start',new Date(end.getTime()-Number(period)*3600000).toISOString());
  }
  return query;
}
const CHART_VIEW_KEY='bt06-chart-views-v1';
function defaultAxes(){return {temperature:{mode:'auto',min:0,max:40},humidity:{mode:'manual',min:0,max:100}};}
function validateAxes(value) {
  const result={};
  for(const axis of ['temperature','humidity']){
    const item=value?.[axis];
    if(!item||!['auto','manual'].includes(item.mode)||typeof item.min!=='number'||typeof item.max!=='number'||!Number.isFinite(item.min)||!Number.isFinite(item.max)||item.min>=item.max||item.min< (axis==='humidity'?0:-1000)||item.max>(axis==='humidity'?100:1000))throw new Error('Achsengrenzen prüfen: Untergrenze muss kleiner als Obergrenze sein; Feuchte 0–100 %, Temperatur −1000 bis 1000 °C.');
    result[axis]={mode:item.mode,min:item.min,max:item.max};
  }
  return result;
}
function updateAxisControls(){for(const axis of ['temperature','humidity'])for(const bound of ['min','max'])$(`#axis-${axis}-${bound}`).disabled=$(`#axis-${axis}-mode`).value==='auto';}
function updateAxisForm(){const axes=state.axes||defaultAxes();for(const axis of ['temperature','humidity'])for(const part of ['mode','min','max'])$(`#axis-${axis}-${part}`).value=axes[axis][part];updateAxisControls();}
function applyAxes(event){
  event.preventDefault();const axes=defaultAxes();
  for(const axis of ['temperature','humidity']){axes[axis].mode=$(`#axis-${axis}-mode`).value;if(axes[axis].mode==='manual')for(const bound of ['min','max']){const raw=$(`#axis-${axis}-${bound}`).value;if(raw==='')throw new Error('Beide Achsengrenzen angeben.');axes[axis][bound]=Number(raw);}}
  state.axes=validateAxes(axes);if(state.chartData)renderChart(state.chartData);$('#chart-view-status').textContent='Achsen angewendet. „Ansicht speichern“ sichert die Ansicht in diesem Browser.';
}
function readChartViews(){
  try{const value=JSON.parse(localStorage.getItem(CHART_VIEW_KEY)||'null');return value?.version===1&&Array.isArray(value.views)&&value.views.length<=20?value.views:[];}catch{return [];}
}
function validateChartView(value){
  if(!value||value.key!==rangeIdentity()||!Number.isFinite(value.range?.start)||!Number.isFinite(value.range?.end)||value.range.start>value.range.end||Math.abs(value.range.start)>8640000000000000||Math.abs(value.range.end)>8640000000000000||!Number.isFinite(value.zoom?.start)||!Number.isFinite(value.zoom?.end)||value.zoom.start<0||value.zoom.end>100||value.zoom.start>value.zoom.end)throw new Error('Gespeicherte Diagrammansicht ungültig.');
  const selection={};for(const name of ['Temperatur','Relative Feuchte','Taupunkt'])if(typeof value.selection?.[name]==='boolean')selection[name]=value.selection[name];
  return {key:value.key,range:{start:value.range.start,end:value.range.end},zoom:{start:value.zoom.start,end:value.zoom.end},axes:validateAxes(value.axes),selection};
}
function saveChartView(){
  const range=chartRange();if(!range)throw new Error('Zuerst einen Verlauf laden.');
  const zoom=state.chart?.getOption()?.dataZoom?.[0];
  const view=validateChartView({key:rangeIdentity(),range,zoom:{start:zoom?.start??0,end:zoom?.end??100},axes:state.axes||defaultAxes(),selection:state.selection});
  const views=readChartViews().filter(item=>item?.key!==view.key).slice(-19);views.push(view);localStorage.setItem(CHART_VIEW_KEY,JSON.stringify({version:1,views}));
  updateChartControls();$('#chart-view-status').textContent='Ansicht mit Zeitraum, Zoom, Achsen und Kurvenauswahl in diesem Browser gespeichert.';
}
async function loadChartView(){
  const view=validateChartView(readChartViews().find(item=>item?.key===rangeIdentity()));
  state.axes=view.axes;state.selection=view.selection;updateAxisForm();
  $('#range-start').value=rangeInput(view.range.start);$('#range-end').value=rangeInput(view.range.end);
  state.shiftedRange={...view.range,identity:view.key,inputs:[$('#range-start').value,$('#range-end').value]};
  $('#period').value='custom';$('#custom-period').hidden=false;
  if(state.source==='live'){state.follow=false;$('#live-follow').checked=false;}
  const loaded=await loadHistory();if(!loaded||rangeIdentity()!==view.key)return;
  state.chart?.dispatchAction({type:'dataZoom',start:view.zoom.start,end:view.zoom.end});
  $('#chart-view-status').textContent='Gespeicherte Ansicht geladen; der gespeicherte Zeitraum wird angezeigt.';
}
function initChart() {
  if(!window.echarts) {notice('Lokale Diagrammbibliothek fehlt. Installation prüfen.',true);return;}
  state.chart=echarts.init($('#chart'),null,{renderer:'canvas'});
  state.chart.on('legendselectchanged',event=>{state.selection=event.selected;localStorage.setItem('bt06-curves',JSON.stringify(state.selection));});
  state.chart.on('datazoom',()=>{if(state.source==='live'){state.follow=false;$('#live-follow').checked=false;}updateChartControls();});
  new ResizeObserver(()=>state.chart.resize()).observe($('#chart'));
  if(state.chartData)renderChart(state.chartData);
}
function renderChart(data, reset=false) {
  if(!state.chart) return;
  const css=getComputedStyle(document.documentElement), text=css.getPropertyValue('--muted').trim(), border=css.getPropertyValue('--border').trim();
  const savedZoom=reset?null:state.chart.getOption()?.dataZoom,domain=chartRange();
  const axes=state.axes||defaultAxes(),axisLimits=axis=>({min:axes[axis].mode==='manual'?axes[axis].min:null,max:axes[axis].mode==='manual'?axes[axis].max:null});
  const lines=[{name:'Warnlinie',yAxis:state.saved.humidity_warning,lineStyle:{color:'#c69e52'}},{name:'Kritische Linie',yAxis:state.saved.humidity_critical,lineStyle:{color:'#d47c7c'}}];
  state.chart.setOption({animation:false,color:['#f3a35c','#65aaff','#70c7a2'],textStyle:{color:text},legend:{top:0,textStyle:{color:text},selected:state.selection},
    grid:{left:55,right:55,top:62,bottom:90},tooltip:{trigger:'axis',axisPointer:{type:'cross'},formatter:params=>{const valid=params.filter(p=>p.value[1]!=null);return valid.length?`${chartDate(valid[0].value[0])}<br>${valid.map(p=>`${p.marker}${p.seriesName}: ${number(p.value[1])} ${p.seriesName==='Relative Feuchte'?'% rF':'°C'}`).join('<br>')}`:'Datenlücke';}},
    xAxis:{type:'time',min:domain?.start??null,max:domain?.end??null,boundaryGap:false,axisLabel:{color:text,formatter:value=>new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:state.source==='device'?'UTC':state.saved.timezone}).format(value)},splitLine:{show:false}},
    yAxis:[{type:'value',name:'°C',scale:true,...axisLimits('temperature'),axisLabel:{color:text},splitLine:{lineStyle:{color:border}}},{type:'value',name:'% rF',scale:true,...axisLimits('humidity'),axisLabel:{color:text},splitLine:{show:false}}],
    dataZoom:[{type:'inside',xAxisIndex:0,start:savedZoom?.[0]?.start??0,end:savedZoom?.[0]?.end??100},{type:'slider',xAxisIndex:0,bottom:12,height:25,start:savedZoom?.[1]?.start??0,end:savedZoom?.[1]?.end??100,textStyle:{color:text}}],
    series:[{name:'Temperatur',type:'line',showSymbol:false,connectNulls:false,data:data.points.map(p=>[p[0],p[1]])},{name:'Relative Feuchte',type:'line',showSymbol:false,connectNulls:false,yAxisIndex:1,data:data.points.map(p=>[p[0],p[2]]),markLine:{silent:true,symbol:'none',label:{show:false},data:lines}},{name:'Taupunkt',type:'line',showSymbol:false,connectNulls:false,lineStyle:{type:'dashed'},data:(data.climate?.points||data.points.map(p=>[p[0],null])).map(p=>[p[0],p[1]])}]}, {notMerge:true});
  updateChartControls();
}
async function loadHistory(refresh=false) {
  const query=buildQuery(); if(!query) {state.query=null;state.chartData=null;state.chart?.clear();$('#chart-caption').textContent='Keine Daten ausgewählt.';updateChartControls();return false;}
  const request=++state.loading; const data=await api(`history?${query}`);if(request!==state.loading)return false;
  const assignment=query.get('source')==='device'?await api(`time-assignment?${new URLSearchParams({logger:query.get('logger'),snapshot:query.get('snapshot')})}`):null;if(request!==state.loading)return false;state.timeAssignment=assignment;
  $('#chart-export-assigned').hidden=!assignment;$('#chart-export-assigned').disabled=!assignment?.timezone_confirmed;$('#timezone-panel').hidden=!assignment;
  if(assignment){$('#timezone-status').textContent=assignment.timezone_confirmed?`${assignment.timezone} bestätigt · ${assignment.assigned_count} Werte zugeordnet · ${assignment.unassigned_count} spätere/unbestätigte Werte · Datum weiterhin ungeprüft`:'Zeitzone dieses Historienstands noch nicht bestätigt.';if(assignment.timezone)$('#history-timezone').value=assignment.timezone;}
  if(state.exportBase&&exportSignature()!==state.exportSignature)invalidateExport();
  const changed=state.query?.toString()!==query.toString();if(changed&&state.riskReport)markRiskStale();if(changed&&state.statisticsReport)markStatisticsStale();
  const reset=!refresh&&changed;state.query=query;state.chartData=data;state.chartContext=rangeIdentity();
  $('#chart-caption').textContent=`${data.raw_count.toLocaleString('de-DE')} ${state.source==='live'?'BLE-Empfänge':state.source==='device'?'Loggerwerte':'Testwerte'} · ${data.points.length.toLocaleString('de-DE')} Grafikpunkte · ${state.source==='device'?'Gerätezeit · Datum/Offset ungeprüft':state.saved.timezone}${data.climate?' · Taupunkt berechnet (Magnus über Wasser)':''}${siteReportLabel(data)}`;
  renderChart(data,reset);return true;
}
function chartRange(visible=false) {
  if(!state.query||!state.chartData)return null;
  const points=state.chartData.points;
  let start=state.query.has('start')?Date.parse(state.query.get('start')):points.length?new Date(points[0][0]).getTime():NaN;
  let end=state.query.has('end')?Date.parse(state.query.get('end')):points.length?new Date(points[points.length-1][0]).getTime():NaN;
  if(!Number.isFinite(start)||!Number.isFinite(end)||start>end)return null;
  if(visible){const zoom=state.chart?.getOption()?.dataZoom?.[0],width=end-start;const low=Number(zoom?.start??0),high=Number(zoom?.end??100);if(!Number.isFinite(low)||!Number.isFinite(high)||low<0||high>100||low>high)return null;end=Math.round(start+width*high/100);start=Math.round(start+width*low/100);}
  return {start,end};
}
function updateChartControls() {
  const range=chartRange(true),movable=!!range&&range.end>range.start;
  $('#chart-view-save').disabled=!range;$('#chart-view-load').disabled=!state.query||!readChartViews().some(item=>item?.key===rangeIdentity());
  $('#chart-previous').disabled=!movable;$('#chart-next').disabled=!movable;$('#chart-export-visible').disabled=!range;
  $('#chart-visible-range').textContent=range?`Sichtbarer Ausschnitt: ${chartDate(range.start)} bis ${chartDate(range.end)}${state.source==='device'?' · ungeprüfter Gerätekalender':''}`:'';
}
function rangeInput(value) {
  const dateValue=new Date(value);
  return new Date(value-(state.source==='device'?0:dateValue.getTimezoneOffset()*60000)).toISOString().slice(0,-1);
}
async function shiftChart(direction) {
  const range=chartRange(true);if(!range||range.start===range.end)throw new Error('Zuerst einen Zeitraum mit Anfang und Ende laden.');
  const offset=(range.end-range.start)*direction;
  $('#range-start').value=rangeInput(range.start+offset);$('#range-end').value=rangeInput(range.end+offset);
  state.shiftedRange={start:range.start+offset,end:range.end+offset,identity:rangeIdentity(),inputs:[$('#range-start').value,$('#range-end').value]};
  $('#period').value='custom';$('#custom-period').hidden=false;
  if(state.source==='live'){state.follow=false;$('#live-follow').checked=false;}
  await loadHistory();
}
function exportCSV(visible=false) {
  if(!state.query)throw new Error('Zuerst einen Verlauf laden.');
  const query=new URLSearchParams(state.query);
  if(visible){const range=chartRange(true);if(!range)throw new Error('Kein sichtbarer Zeitraum verfügbar.');query.set('start',new Date(range.start).toISOString());query.set('end',new Date(range.end).toISOString());}
  const link=document.createElement('a');link.href=`api/export?${query}`;link.click();
}
async function diagnostics() {
  const data=await api('status');$('#version').textContent=data.version;
  $('#template-note').textContent=data.local_profiles?'Lokale Zigbee-Klimavorlagen verfügbar. Erzeugte Werte bleiben synthetisch.':'Allgemeine synthetische Klimavorlagen. Zigbee-Vorlagen können lokal eingelesen werden.';
  const target=$('#diagnostics');target.replaceChildren();
  for(const [key,value] of [['Version',data.version],['Betrieb',data.mode==='advertising'?'BLE-Advertising-Empfang':'Offline'],['Laufzeit',`${data.uptime_seconds} Sekunden`],['Bluetooth',data.ble.status],['Freier Speicher',`${number(data.free_bytes/1073741824)} GiB`],['Einstellungen','JSON · Save / Load'],['Datenquellen','BLE-Empfänge / Simulation getrennt'],['Konfigurationsablage',data.configuration?.error||`${data.configuration?.path||'unbekannt'} · ${data.configuration?.persisted?'gespeichert':'bisheriger Stand / Standardwerte'} · Revision ${data.configuration?.revision??'–'}`],['Ereignisablage',data.event_log?.error||`Kein aktueller Schreibfehler · ${data.event_log?.failed_this_session??0} Fehler seit Dienststart`]])target.append(element('dt',key),element('dd',value));
}
async function checkStorage(){
  const button=$('#storage-check');button.disabled=true;$('#storage-check-status').textContent='Empfangsdateien werden rein lesend geprüft …';$('#storage-check-summary').replaceChildren();$('#storage-check-details').replaceChildren();
  try{
    const data=await api('diagnostics/storage'),labels={ok:'Empfangsdateien innerhalb des Prüfumfangs ohne Befund.',empty:'Keine Empfangsdateien vorhanden; keine Messdaten geprüft.',partial:'Nur teilweise geprüft. Kein vollständiger Integritätsnachweis.',error:'Fehler gefunden. Originaldateien unverändert; keine Reparatur ausgeführt.'};
    $('#storage-check-status').textContent=labels[data.state]+' Stand: '+date(data.checked_at);
    for(const [key,value] of [['Vollständig geprüfte Dateien',data.files_checked],['Geprüfte Zeilen',data.rows_checked],['Berücksichtigte Dateigröße',number(data.bytes_checked/1048576)+' MiB'],['Prüfdauer',number(data.elapsed_seconds)+' s'],['Prüfumfang',data.complete?'Erfasster Bestand vollständig abgearbeitet':'Begrenzt / nicht vollständig abgearbeitet']])$('#storage-check-summary').append(element('dt',key),element('dd',String(value)));
    for(const item of [...data.errors,...data.skipped])$('#storage-check-details').append(element('li',item.file+': '+item.reason));
  }catch(error){$('#storage-check-status').textContent='Prüfung fehlgeschlagen; kein Integritätsnachweis.';throw error;}finally{button.disabled=false;}
}
function populateSnapshots() {
  const selected=state.snapshots.filter(s=>s.logger===state.logger),heads=state.series.filter(s=>s.logger===state.logger);
  state.snapshot=selected.find(s=>s.id===state.snapshot?.id)||heads[0]||selected[0]||null;
  const select=$('#run-select');select.replaceChildren();
  for(const [label,items] of [['Fortgesetzte Verläufe',heads],['Frühere Einzelstände',selected.filter(s=>!heads.some(h=>h.id===s.id))]]){
    if(!items.length)continue;
    const group=element('optgroup');group.label=label;
    for(const item of items)addOption(group,item.id,`${item.first_device_calendar.replace('T',' ')} – ${item.last_device_calendar.replace('T',' ')} · ${item.count} Werte`);
    select.append(group);
  }
  select.value=state.snapshot?.id||'';
}
function setSource(source) {
  if(!['live','device','simulation'].includes(source))source='simulation';
  markRiskStale();markStatisticsStale();invalidateExport();state.loading++;state.chartData=null;state.query=null;state.chartContext=null;state.chart?.clear();updateChartControls();$('#timezone-panel').hidden=true;$('#chart-export-assigned').hidden=true;
  state.source=source;localStorage.setItem('bt06-source',source);$('#source-select').value=source;
  const live=source==='live',device=source==='device';$('#run-label').hidden=live;$('#live-follow-label').hidden=!live;
  $('#run-title').textContent=device?'Historienstand':'Testlauf';
  $('#source-notice').classList.toggle('real-notice',live);
  $('#source-notice strong').textContent=live?'Echte BT06-Empfänge':device?'Loggerhistorie · Gerätezeit ungeprüft':'Synthetische Testdaten';
  $('#source-notice span').textContent=live?'BLE-Advertising · Zeitbasis: Host-Empfang · keine Loggerhistorie':device?'Originale Loggerwerte · Datum und UTC-Offset nicht bestätigt · keine automatische Zeitkorrektur':'Alle dargestellten Werte dieser Datenquelle sind simuliert.';
  $('#overview-note').textContent=live?'Aktuelle Aussendungen und lokal gespeicherte Empfänge. Veraltete Werte werden gekennzeichnet.':device?'Vollständig gelesene Historienstände. Keine aktuellen Livewerte.':'Letzter Testlauf · keine Livewerte und keine Schimmelbewertung.';
  $('#chart-time-note').textContent=device?'Zeitachse und freie Datumseingaben zeigen unveränderten Gerätekalender ohne bestätigten UTC-Offset. CSV enthält Original-Gerätesekunden und keine erfundenen UTC-Zeitstempel.':'Temperatur in °C · relative Feuchte in % · Lücken bleiben sichtbar. CSV enthält die Originalauflösung des gewählten Zeitraums, unabhängig vom Grafikzoom. „Sichtbaren Ausschnitt als CSV“ exportiert die Originalwerte im Zoomfenster.';
  if(source==='simulation'){const select=$('#run-select');select.replaceChildren();for(const run of state.runs)addOption(select,run.id,`${date(run.created_at)} · ${run.options.days} Tage`);select.value=state.run?.id||'';}
  chooseLogger();
}
async function refreshSnapshots() {
  const previousHead=state.series.find(s=>s.id===state.snapshot?.id&&s.logger===state.logger);
  const [snapshots,series]=await Promise.all([api('snapshots'),api('series')]);
  state.snapshots=snapshots.snapshots;state.series=series.series;
  if(previousHead){const successors=state.series.filter(s=>s.logger===previousHead.logger&&s.member_ids.includes(previousHead.id));if(successors.length===1)state.snapshot=successors[0];}
  const list=$('#snapshot-list');list.replaceChildren();
  if(!state.snapshots.length)list.append(element('p','Noch keine Loggerhistorie gespeichert.','muted'));
  function appendItem(item,target,archived=false){
    const row=element('div',null,'run-item'),details=element('div');
    details.append(element('strong',`BT06 ${item.logger.replace('bt06-','')} · ${item.count.toLocaleString('de-DE')} Werte`),element('p',`${item.first_device_calendar.replace('T',' ')} – ${item.last_device_calendar.replace('T',' ')} · Gerätezeit ungeprüft`));
    if(item.member_count>1)details.append(element('p',`${item.member_count} übereinstimmende Historienstände · vorhandene Werte einmal im Verlauf`));
    if(item.separate_series>1)details.append(element('p','Mehrere getrennte Reihen: keine eindeutige gemeinsame Fortsetzung.'));
    if(item.transfer_scope==='range')details.append(element('p',`Fortgesetzt aus geprüfter Basis und Nachladebereich · ${item.new_count} neue Werte`));
    const button=element('button',archived?'Einzelstand ansehen':'Verlauf ansehen','secondary');button.addEventListener('click',guard(async()=>{state.logger=item.logger;state.snapshot=item;setSource('device');go('history');await loadHistory();}));
    const exportButton=element('button','Original-CSV','secondary');exportButton.addEventListener('click',()=>{const link=document.createElement('a');link.href=`api/export?${new URLSearchParams({source:'device',logger:item.logger,snapshot:item.id})}`;link.click();});
    const actions=element('div',null,'button-row');actions.append(button,exportButton);row.append(details,actions);target.append(row);
  }
  for(const item of state.series)appendItem(item,list);
  const archived=state.snapshots.filter(s=>!state.series.some(h=>h.logger===s.logger&&h.id===s.id));
  if(archived.length){const details=element('details'),summary=element('summary',`${archived.length} frühere Einzelstände`);details.append(summary);for(const item of archived)appendItem(item,details,true);list.append(details);}
  if(state.source==='device')chooseLogger();
}
async function renderDeviceCards() {
  const cards=$('#cards');cards.replaceChildren();
  if(!state.snapshots.length){cards.append(element('p','Noch keine vollständig gelesene Loggerhistorie. Unter Logger / Bluetooth auslesen.','empty'));return;}
  const item=state.snapshot||state.series[0]||state.snapshots[0],card=element('article',null,'card');
  card.append(element('div','HISTORIE · GERÄTEZEIT UNGEPRÜFT','source'),element('h3','BT06 '+item.logger.replace('bt06-','')),element('p',`${item.count.toLocaleString('de-DE')} Originalwerte · ${item.interval_seconds} s Intervall`),element('p',`${item.first_device_calendar.replace('T',' ')} – ${item.last_device_calendar.replace('T',' ')}`,'hint'));
  const button=element('button','Verlauf ansehen','secondary');button.addEventListener('click',guard(async()=>{go('history');await loadHistory();}));card.append(button);cards.append(card);
}
let syncPolling=null;
async function refreshSync() {
  const previous=state.sync?.state;state.sync=await api('sync');
  const busy=state.sync.state==='running';
  const labels={finding_device:'Gewählten Logger erneut suchen',reading_settings:'Geräteeinstellungen lesen',pausing_host:'Hostempfang wird pausiert',connecting:state.sync.trigger==='automatic'?'Automatischer Verbindungsversuch ohne Tastendruck':'Verbindung wartet auf kurzen Tastendruck',reading_metadata:'Metadaten lesen',selecting_range:'Nachladebereich wählen',full_fallback:'Vollauslesung erforderlich',receiving:'Historie empfangen',reading_inventory:'Gesamten Historienumfang prüfen',starting_logger:'Aufzeichnung am Gerät starten',verifying_recording:'Aufnahmestart prüfen',securing_history:'Gesamte aktuelle Historie prüfen',stopping_logger:'Aufzeichnung am BT06 stoppen',writing_settings:'Geräteparameter schreiben',committing_settings:'Geräteeinstellungen speichern',verifying_settings:'Geräteeinstellungen zurücklesen',saving:'CSV dauerhaft speichern',finished:'Abgeschlossen'};
  $('#sync-start').disabled=busy||!state.live?.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;$('#device-settings-read').disabled=$('#sync-start').disabled;
  $('#sync-button-signal').hidden=!(busy&&state.sync.trigger!=='automatic'&&['finding_device','connecting'].includes(state.sync.phase));
  const result=state.sync.result;
  const resultText=result?.kind==='recording-prepared'?`Start vorbereitet · ${result.protection.count==null?'unbekannter Gerätebestand':result.protection.count+' vorhandene Werte geprüft'} · noch kein Start`:result?.kind==='recording-started'?'Aufzeichnung am Gerät bestätigt':result?.kind==='recording-start-pending'?'Start bestätigt; Aufzeichnung noch nicht nachgewiesen · nicht erneut starten':result?.kind==='configuration-parameters-verified'?'Geräteparameter zurückgelesen · Status ohne Aufzeichnungsdetails · kein automatischer Start':result?.kind==='configuration-prepared'?`Vorbereitung abgeschlossen · ${result.history.count} Werte vollständig geprüft · noch keine Geräteänderung`:result?.kind==='configuration-verified'?'Geräteänderung zurückgelesen · Aufzeichnung bleibt gestoppt':result?.kind==='device-settings'?`Geräteeinstellungen gelesen · Stand ${date(result.observed_at)} · ${Object.keys(result.read_errors).length+Object.keys(result.decode_errors).length} nicht verfügbare Abfragen`:(result?(result.last_transfer_scope==='range'?`${result.new_count} neue Werte · ${result.received_count} Werte einschließlich Überlappung geprüft · ${result.count} Werte im Gesamtbestand · ${result.duplicate?'keine Änderung':'dauerhaft gespeichert'}`:`${result.count} Werte vollständig geprüft · ${result.duplicate?'bereits vorhanden, keine Kopie':'dauerhaft gespeichert'}`):'');
  const jobText=[state.sync.state==='error'?(state.sync.mode==='configuration_write'?'Geräteänderung nicht bestätigt':'Lesen fehlgeschlagen'):labels[state.sync.phase]||'Bereit zum manuellen Auslesen.',busy&&state.sync.expected?`${state.sync.received} / ${state.sync.expected} ${state.sync.phase==='reading_settings'?'Abfragen':'Werte'}`:'',resultText,state.sync.error||'',state.sync.resume_error||''].filter(Boolean).join(' · ');
  $('#sync-status').textContent=jobText;
  $('#device-settings-job').textContent=['settings','configuration_prepare','configuration_write','configuration_verify','recording_prepare','recording_start','recording_verify'].includes(state.sync.mode)?jobText+(state.sync.state==='error'&&state.sync.mode==='settings'?' · Kein neuer Einstellungsstand gespeichert; bisheriger Stand bleibt erhalten.':''):'';
  $('#device-settings-button-signal').hidden=!['settings','configuration_prepare','configuration_write','configuration_verify','recording_prepare','recording_start','recording_verify'].includes(state.sync.mode)||$('#sync-button-signal').hidden;
  configurationControls();recordingControls();
  if(busy&&!syncPolling)syncPolling=setInterval(guard(refreshSync),1000);
  if(!busy&&syncPolling){clearInterval(syncPolling);syncPolling=null;}
  if(previous==='running'&&!busy){await refreshLive();await refreshSnapshots();await refreshBluetooth();await refreshAutoSync();await refreshDeviceSettings();await renderCards();}
}
async function refreshDeviceSettings() {
  const target=$('#device-settings-values');target.replaceChildren();let result;try{result=await api('device-settings');}catch(error){updateDeviceDraft(null);$('#device-settings-status').textContent=error.message;return;}const data=result.settings;
  const memory=result.memory_estimate;$('#device-memory-estimate').textContent=memory?`Rechnerische Speicherdauer: ca. ${number(memory.nominal_days,1)} Tage bei ${memory.capacity_records.toLocaleString('de-DE')} Werten (Herstellerangabe). Tatsächlich freie Restdauer unbekannt.`:'';
  updateDeviceDraft(data);await refreshConfiguration();await refreshRecording();
  if(!data){$('#device-settings-status').textContent=result.selected?'Für dieses Gerät noch keine gespeicherte Einstellungsabfrage.':'Zuerst einen verifizierten BT06 auswählen.';return;}
  const v=data.values;
  $('#device-settings-status').textContent=`Nur gelesen · Stand ${date(data.observed_at)} · Firmware ${data.firmware} · Gerätezeit ungeprüft`;
  const pairs=[['Gerätename',v.name],['Aufzeichnung',v.recording],['Aufzeichnungsintervall',v.record_interval_seconds==null?null:`${v.record_interval_seconds} s`],['Temperatureinheit',v.temperature_unit?`°${v.temperature_unit}`:null],['Sendeintervall',v.broadcast_interval_seconds==null?null:`${number(v.broadcast_interval_seconds,1)} s`],['Sendeleistung',v.transmit_power_dbm==null?null:`${v.transmit_power_dbm} dBm`],['Funkmoduscode',v.transmit_rate_code==null?null:`${v.transmit_rate_code} · Bedeutung noch nicht bestätigt`],['Gerätekalender',v.clock_calendar_2000?`${v.clock_calendar_2000.replace('T',' ')} · Jahresbasis 2000, ungeprüft`:null]];
  for(const [key,alarm,unit] of [['Temperaturalarm',v.temperature_alarm,v.temperature_unit?`°${v.temperature_unit}`:'Einheit unbekannt'],['Feuchtealarm',v.humidity_alarm,'% rF']]){
    if(alarm)pairs.push([key,`Untergrenze ${number(alarm.low.limit)} ${unit} (${alarm.low.enabled?'ein':'aus'}) · Obergrenze ${number(alarm.high.limit)} ${unit} (${alarm.high.enabled?'ein':'aus'})`]);
  }
  for(const [label,value] of pairs)if(value!=null)target.append(element('dt',label),element('dd',String(value)));
  const errors=Object.keys({...data.read_errors,...data.decode_errors});
  if(errors.length){const labels={device_info:'Gerätename',device_clock:'Gerätezeit',log_status:'Aufzeichnungsstatus',log_settings:'Aufzeichnungsparameter',broadcast_settings:'Funkparameter',transmit_rate:'Funkmodus',temperature_alarm:'Temperaturalarm',humidity_alarm:'Feuchtealarm'};target.append(element('dt','Nicht verfügbar'),element('dd',errors.map(key=>labels[key]||key).join(', ')));}
}
const deviceDraftFields={name:'#device-draft-name',broadcast_interval_seconds:'#device-draft-interval',transmit_power_dbm:'#device-draft-power',record_interval_seconds:'#device-draft-record',temperature_unit:'#device-draft-unit'};
for(const alarm of ['temperature','humidity'])for(const bound of ['low','high'])for(const part of ['limit','enabled'])deviceDraftFields[`${alarm}_alarm_${bound}_${part}`]=`#device-draft-${alarm}-${bound}-${part}`;
function editableDeviceValues(values) {
  const result={...values};
  for(const alarm of ['temperature','humidity'])for(const bound of ['low','high'])for(const part of ['limit','enabled'])if(part in (values[alarm+'_alarm']?.[bound]||{}))result[`${alarm}_alarm_${bound}_${part}`]=values[alarm+'_alarm'][bound][part];
  return result;
}
let deviceDraftBase=null,deviceDraftLatest=null,deviceDraftPending=false,deviceDraftRevision=0,deviceDraftReviewed=null,configurationState=null;
function deviceDraftValues() {
  const values={};
  for(const [key,selector] of Object.entries(deviceDraftFields))if(deviceDraftBase&&key in deviceDraftBase.values&&!(key.startsWith('temperature_alarm_')&&deviceDraftBase.values.temperature_unit!=='C'))values[key]=key.endsWith('_enabled')?$(selector).checked:['name','temperature_unit'].includes(key)?$(selector).value:Number($(selector).value)*(key==='record_interval_seconds'?60:1);
  return values;
}
function deviceDraftDirty() {
  return deviceDraftBase&&Object.entries(deviceDraftValues()).some(([key,value])=>value!==deviceDraftBase.values[key]);
}
function deviceDraftControls() {
  const current=deviceDraftBase&&deviceDraftLatest?.capture===deviceDraftBase.capture;
  for(const [key,selector] of Object.entries(deviceDraftFields))$(selector).disabled=!deviceDraftLatest||!deviceDraftBase||!(key in deviceDraftBase.values)||(key.startsWith('temperature_alarm_')&&deviceDraftBase.values.temperature_unit!=='C');
  $('#device-draft-preview').disabled=deviceDraftPending||!current||!Object.keys(deviceDraftValues()).length;
  $('#device-draft-reset').disabled=deviceDraftPending||!deviceDraftLatest;
  configurationControls();
}
function updateDeviceDraft(data,force=false) {
  if(data)data={...data,values:editableDeviceValues(data.values)};
  deviceDraftLatest=data;
  if(!data){deviceDraftReviewed=null;deviceDraftRevision++;$('#device-draft-result').replaceChildren();$('#device-draft-status').textContent='Zuerst für den ausgewählten Logger Geräteeinstellungen auslesen.';deviceDraftControls();return;}
  if(force||!deviceDraftBase||data.capture!==deviceDraftBase.capture){
    deviceDraftReviewed=null;deviceDraftRevision++;$('#device-draft-result').replaceChildren();
    if(!force&&deviceDraftDirty()){
      $('#device-draft-status').textContent='Ein anderer Einstellungsstand liegt vor. Entwurf bleibt sichtbar; vor einer neuen Prüfung „Aktuellen Stand übernehmen“ wählen.';
    }else{
      deviceDraftBase=data;
      for(const [key,selector] of Object.entries(deviceDraftFields))if(key.endsWith('_enabled'))$(selector).checked=data.values[key]===true;else $(selector).value=data.values[key]==null?'':key==='record_interval_seconds'?data.values[key]/60:data.values[key];
      $('#device-draft-status').textContent=`Entwurf zum Stand ${date(data.observed_at)}. Noch keine Änderungen geprüft oder am Gerät gespeichert.`;
    }
  }
  deviceDraftControls();
}
async function previewDeviceDraft(event) {
  event.preventDefault();
  if(!deviceDraftBase||deviceDraftBase.capture!==deviceDraftLatest?.capture)throw new Error('Aktuellen Einstellungsstand zuerst übernehmen.');
  deviceDraftReviewed=null;
  const revision=++deviceDraftRevision;
  deviceDraftPending=true;deviceDraftControls();$('#device-draft-result').replaceChildren();
  $('#device-draft-status').textContent='Änderungen werden lokal geprüft …';
  try{
    const result=await post('device-settings/preview',{base_capture:deviceDraftBase.capture,changes:deviceDraftValues()});
    if(revision!==deviceDraftRevision)return;
    deviceDraftReviewed=result;
    $('#device-draft-status').textContent=result.notice;
    const target=$('#device-draft-result'),values=element('dl');
    for(const item of result.changes)values.append(element('dt',item.label),element('dd',`${typeof item.before==='boolean'?(item.before?'an':'aus'):item.before} → ${typeof item.after==='boolean'?(item.after?'an':'aus'):item.after}${item.unit?' '+item.unit:''}`));
    target.append(values);
    if(result.broadcast_after)target.append(element('p',`Funkparameter danach: ${number(result.broadcast_after.broadcast_interval_seconds,1)} s · ${result.broadcast_after.transmit_power_dbm} dBm. Nicht bearbeitete Funkwerte bleiben erhalten.`,'hint'));
    if(result.required_steps.length){target.append(element('p','Vor einem späteren Schreiben erforderlich:'));const steps=element('ol');for(const text of result.required_steps)steps.append(element('li',text));target.append(steps);}
    target.append(element('p',result.write_block_reason,'hint'));
  }catch(error){if(revision===deviceDraftRevision)$('#device-draft-status').textContent=`Vorschau fehlgeschlagen: ${error.message}`;}
  finally{deviceDraftPending=false;deviceDraftControls();}
}
function configurationMatches() {
  const prepared=configurationState?.prepared;
  if(!prepared||deviceDraftLatest?.capture!==prepared.preview.base_capture)return false;
  const expected=editableDeviceValues(prepared.values_before);
  for(const item of prepared.preview.changes)expected[item.field]=item.after;
  return Object.entries(deviceDraftValues()).every(([key,value])=>expected[key]===value);
}
function configurationControls() {
  const busy=state.sync?.state==='running',prepared=configurationState?.prepared;
  $('#device-config-prepare').disabled=busy||deviceDraftPending||!deviceDraftReviewed?.changes.length||deviceDraftBase?.capture!==deviceDraftLatest?.capture;
  $('#device-config-apply').disabled=busy||!configurationMatches()||!$('#device-config-loss').checked||!$('#device-config-stop').checked;
  $('#device-config-cancel').disabled=busy||!prepared;
  const report=configurationState?.last_change;
  $('#device-config-verify').disabled=busy||!report?.may_have_changed||!['uncertain','writing','parameters_verified'].includes(report.status);
}
async function refreshConfiguration() {
  let result;
  try{result=await api('device-settings/configuration');}catch(error){configurationState=null;$('#device-config-status').textContent=error.message;$('#device-config-confirmation').hidden=true;configurationControls();return;}
  if(result.prepared?.token!==configurationState?.prepared?.token){$('#device-config-loss').checked=false;$('#device-config-stop').checked=false;}
  configurationState=result;
  const prepared=result.prepared,report=result.last_change;
  $('#device-config-confirmation').hidden=!prepared;
  $('#device-config-changes').replaceChildren();
  if(prepared){
    $('#device-config-status').textContent=`Vorbereitet · ${prepared.history.count} Werte vollständig gespeichert · gültig für ${Math.ceil(prepared.expires_in_seconds/60)} min. Vor dem Schreiben wird die aktuelle Historie erneut vollständig gelesen.`;
    for(const item of prepared.preview.changes){const recording=item.field==='record_interval_seconds',format=value=>recording?`${number(value/60,1)} min`:typeof value==='number'?`${number(value,Number.isInteger(value)?0:1)} ${item.unit}`:typeof value==='boolean'?(value?'an':'aus'):String(value);$('#device-config-changes').append(element('dt',item.label),element('dd',`${format(item.before)} → ${format(item.after)}`));}
    $('#device-config-consequences').textContent=prepared.notice;
  }else $('#device-config-status').textContent=report?`${report.status==='verified'?'Änderung zurückgelesen':report.status==='parameters_verified'?'Parameter zurückgelesen; Status ohne Aufzeichnungsdetails':report.status==='blocked'?'Änderung vor Gerätebefehlen blockiert':'Gerätezustand nicht abschließend bestätigt'} · ${report.notice||'Auftrag läuft.'}`:'Noch keine Geräteänderung vorbereitet.';
  configurationControls();
}
function recordingControls() {
  const busy=state.sync?.state==='running',prepared=state.recording?.prepared,report=state.recording?.last_start;
  $('#recording-prepare').disabled=busy||!state.live?.config.device;
  $('#recording-start').disabled=busy||!prepared||!$('#recording-loss').checked||!$('#recording-consent').checked||(prepared?.allow_unread_history_loss&&!$('#recording-unread-confirm').checked);
  $('#recording-cancel').disabled=busy||!prepared;
  $('#recording-verify').disabled=busy||!report?.may_have_changed;
}
async function refreshRecording() {
  try {
    const result=await api('recording');
    if(result.prepared?.token!==state.recording?.prepared?.token){$('#recording-loss').checked=false;$('#recording-consent').checked=false;$('#recording-unread-confirm').checked=false;}
    state.recording=result;const prepared=result.prepared;
    $('#recording-confirmation').hidden=!prepared;$('#recording-unread-label').hidden=!prepared?.allow_unread_history_loss;
    $('#recording-status').textContent=prepared?'Start vorbereitet; noch kein Startbefehl gesendet.':result.last_start?.notice||'Noch kein Aufzeichnungsstart vorbereitet.';
    if(prepared)$('#recording-plan').textContent=`Intervall ${number(prepared.interval_seconds/60,1)} min · ${prepared.protection.count==null?'Gerätebestand unbekannt':prepared.protection.count+' vorhandene Werte '+(prepared.protection.count?'vollständig gesichert':'(leerer Speicher nachgewiesen)')} · gültig für ${Math.ceil(prepared.expires_in_seconds/60)} min. ${prepared.notice}`;
  } catch(error){state.recording=null;$('#recording-status').textContent=error.message;$('#recording-confirmation').hidden=true;}
  recordingControls();
}
async function refreshAutoSync(fill=false) {
  const data=await api('autosync');state.autoSync=data;
  if(fill){$('#autosync-enabled').checked=data.config.enabled;$('#autosync-interval').value=data.config.interval_minutes;}
  $('#autosync-enabled').disabled=!state.live?.config.device;
  const next=data.next_in_seconds==null?'':`Nächster Versuch in ${Math.ceil(data.next_in_seconds/60)} min`;
  $('#autosync-status').textContent=[data.config.enabled?'Automatik eingeschaltet':'Automatik ausgeschaltet',data.active?'Nachladeversuch läuft':next,`Intervall ${data.config.interval_minutes} min`,data.failures?`${data.failures} aufeinanderfolgende Fehlversuche`:'',data.wait_reason||'',data.last_error||'',data.persistence_error||''].filter(Boolean).join(' · ');
}
async function refreshLive() {
  const [live,loggers]=await Promise.all([api('live'),api('loggers')]);state.live=live;state.liveLoggers=loggers.loggers;
  const syncing=state.sync?.state==='running';const active=['starting','receiving','retrying'].includes(live.state);
  $('#capture-stop').disabled=!active||syncing;$('#capture-resume').hidden=!live.config.device||active;$('#capture-resume').disabled=syncing;$('#sync-start').disabled=syncing||!live.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;$('#device-settings-read').disabled=$('#sync-start').disabled;
  const latest=live.latest;
  $('#capture-status').textContent=[`Empfang: ${live.state}`,live.config.device?`BT06 ${live.config.device.id} · Firmware ${live.config.device.firmware}`:'Noch kein Gerät ausgewählt.',latest?`Letzter Empfang: ${date(latest.received_at)} (${live.fresh?'aktuell':'veraltet'})`:'Noch kein Livepaket in dieser Sitzung.',`CSV-Abstand ${live.config.save_interval_seconds} s`,live.last_stored_at?`Zuletzt gespeichert: ${date(live.last_stored_at)}`:'Noch nichts gespeichert.',live.error||''].filter(Boolean).join(' · ');
  $('#ble-scan').disabled=active||$('#ble-scan').disabled;
}
async function renderLiveCards() {
  const cards=$('#cards');const loggers=state.liveLoggers;
  if(!loggers.length){cards.replaceChildren();const empty=element('div',null,'empty');empty.append(element('h3','Noch kein echter Logger ausgewählt'),element('p','Auf Logger / Bluetooth suchen und den Liveempfang bewusst starten.'));const button=element('button','Logger auswählen');button.addEventListener('click',()=>go('logger'));empty.append(button);cards.append(empty);return;}
  const end=new Date(),start=new Date(end.getTime()-86400000);
  const values=await Promise.all(loggers.map(logger=>api(`history?${new URLSearchParams({source:'live',logger:logger.id,start:start.toISOString(),end:end.toISOString()})}`)));
  if(state.source!=='live')return;
  cards.replaceChildren();
  loggers.forEach((logger,index)=>{
    const data=values[index],current=state.live?.latest,selected='bt06-'+current?.device_id===logger.id;
    const reading=selected?current:null,fresh=selected&&state.live.fresh;
    const card=element('article',null,'card');card.append(element('div',fresh?'BLE · AKTUELLER EMPFANG':'BLE · GESPEICHERT / VERALTET','source'),element('h3',logger.name));
    const readings=element('div',null,'readings');
    for(const [label,value,unit,cls] of [['Temperatur',reading?reading.temperature_c:data.latest?.[1],'°C','temperature'],['Relative Feuchte',reading?reading.humidity_pct:data.latest?.[2],'%','humidity']]){const block=element('div',null,'reading');block.append(element('strong',`${number(value)} ${unit}`,cls),element('span',label));readings.append(block);}
    card.append(climateSummary(reading?state.live.latest_climate:data.climate?.latest));
    card.append(readings,element('p',reading?`${number(reading.voltage_v,2)} V · ${reading.rssi} dBm · ${reading.recording} · Firmware ${reading.firmware}`:'Keine aktuelle Aussendung in dieser Sitzung.','hint'));
    card.append(element('time',reading?`Empfangen: ${date(reading.received_at)}`:data.latest?`Zuletzt gespeichert: ${date(data.latest[0])}`:'Noch kein gespeicherter Wert.'));
    if(state.live?.error)card.append(element('p',state.live.error,'hint'));
    const button=element('button','Verlauf ansehen','secondary');button.addEventListener('click',guard(async()=>{state.logger=logger.id;$('#logger-select').value=logger.id;go('history');await loadHistory();}));card.append(button);cards.append(card);
  });
}
async function startReceive(device) {
  const value=device?{device:device.address,adapter:$('#ble-adapter').value,save_interval_seconds:Number($('#capture-interval').value)}:{};
  await post('live/start',value);await refreshLive();setSource('live');await renderCards();await refreshBluetooth();go('overview');notice('BLE-Empfang aktiviert. Keine Verbindung oder Änderung am Logger.');
}
let blePolling=null;
async function refreshBluetooth() {
  const data=await api('ble');
  $('#ble-status').textContent=!data.available?'Optionale Bluetooth-Unterstützung fehlt. Mit ./install.sh --ble lokal installieren und das Programm neu starten.':data.state==='running'?'Bluetooth-Auftrag läuft …':data.error||`Bereit. Sichtbare Adapter: ${data.adapters.join(', ')||'keine erkannt'}.`;
  const busy=data.state==='running'||state.sync?.state==='running'||['starting','receiving','retrying'].includes(state.live?.state);
  $('#sync-start').disabled=!data.available||data.state==='running'||state.sync?.state==='running'||!state.live?.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;$('#device-settings-read').disabled=$('#sync-start').disabled;
  $('#ble-scan').disabled=!data.available||busy;
  for(const button of document.querySelectorAll('[data-ble-action]'))button.disabled=busy;
  if(data.state==='running') { if(!blePolling)blePolling=setInterval(guard(refreshBluetooth),1000);return; }
  if(blePolling){clearInterval(blePolling);blePolling=null;}
  if(data.command==='scan'&&data.result) {
    const target=$('#ble-devices');target.replaceChildren();
    if(!data.result.devices.length)target.append(element('p','Keine BLE-Geräte gefunden. Reichweite und Betriebszustand prüfen.','muted'));
    for(const device of data.result.devices) {
      const row=element('div',null,'run-item'),details=element('div');details.append(element('strong',device.name||'Unbenanntes BLE-Gerät'),element('p',`${device.address} · ${device.rssi} dBm · ${device.bt06?`BT06 ${device.bt06.device_id} · Format ${device.bt06.firmware}`:'Modell/Format unbestätigt'}`));
      const actions=element('div',null,'button-row');
      if(device.bt06){const receive=element('button','Liveempfang starten');receive.dataset.bleAction='true';receive.disabled=busy;receive.addEventListener('click',guard(()=>startReceive(device)));actions.append(receive);}
      for(const [label,pair] of [['Verbinden & prüfen',false],['Koppeln & prüfen',true]]) {
        const button=element('button',label,'secondary');button.dataset.bleAction='true';button.disabled=busy;button.addEventListener('click',guard(()=>startBluetooth('gatt',device.address,pair)));actions.append(button);
      }
      row.append(details,actions);target.append(row);
    }
  }
  if(data.command==='gatt'&&data.result){$('#ble-result').hidden=false;$('#ble-result').textContent=JSON.stringify(data.result,null,2);$('#ble-status').textContent='GATT-Inventar gelesen. Diagnoseverbindung geschlossen; keine Liveaufzeichnung.';}
}
async function startBluetooth(command, device, pair=false) {
  const adapter=$('#ble-adapter').value;if(!/^hci[0-9]{1,3}$/.test(adapter))throw new Error('Adapter als hci0, hci1, … angeben.');
  const value={command,adapter,seconds:30};if(device){value.device=device;value.pair=pair;}
  await post('ble',value);await refreshBluetooth();
}
async function main() {
  state.csrf=(await api('session')).csrf_token;state.saved=await api('settings');fillSettings(state.saved);applySettings();
  const hours=String(state.saved.default_hours);if(![...$('#period').options].some(o=>o.value===hours))addOption($('#period'),hours,`${hours} Stunden`);$('#period').value=hours;
  try{state.selection=JSON.parse(localStorage.getItem('bt06-curves')||'{}');}catch{state.selection={};}
  for(const button of document.querySelectorAll('[data-page]'))button.addEventListener('click',guard(async()=>{go(button.dataset.page);if(button.dataset.page==='history')await loadHistory();}));
  for(const button of document.querySelectorAll('[data-go]'))button.addEventListener('click',()=>go(button.dataset.go));
  window.addEventListener('hashchange',guard(async()=>{go(location.hash.slice(1));if(location.hash==='#history')await loadHistory();}));
  $('#run-select').addEventListener('change',guard(async()=>{if(state.source==='device')state.snapshot=state.snapshots.find(s=>s.id===$('#run-select').value);else state.run=state.runs.find(r=>r.id===$('#run-select').value);chooseLogger();await loadHistory();}));
  $('#storage-check').addEventListener('click',guard(checkStorage));
  $('#history-site').addEventListener('change',guard(async()=>{updateHistorySites();markRiskStale();markStatisticsStale();invalidateExport();await loadHistory();}));
  $('#logger-select').addEventListener('change',guard(async()=>{state.logger=$('#logger-select').value;await loadHistory();}));
  $('#period').addEventListener('change',guard(async()=>{$('#custom-period').hidden=$('#period').value!=='custom';if($('#period').value!=='custom')await loadHistory();}));
  $('#apply-range').addEventListener('click',guard(()=>loadHistory()));
  updateAxisForm();
  $('#chart-axes-form').addEventListener('submit',guard(applyAxes));
  for(const axis of ['temperature','humidity'])$(`#axis-${axis}-mode`).addEventListener('change',updateAxisControls);
  $('#chart-axes-reset').addEventListener('click',()=>{state.axes=defaultAxes();updateAxisForm();if(state.chartData)renderChart(state.chartData);$('#chart-view-status').textContent='Standardachsen wiederhergestellt.';});
  $('#chart-view-save').addEventListener('click',guard(saveChartView));
  $('#chart-view-load').addEventListener('click',guard(loadChartView));
  $('#chart-reset').addEventListener('click',()=>{if(state.chartData)renderChart(state.chartData,true);});
  $('#chart-fullscreen').addEventListener('click',guard(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('#chart-panel').requestFullscreen();}));
  $('#chart-export').addEventListener('click',guard(()=>exportCSV()));
  $('#chart-export-visible').addEventListener('click',guard(()=>exportCSV(true)));
  for(const id of ['#range-start','#range-end'])$(id).addEventListener('input',()=>{state.shiftedRange=null;});
  $('#chart-previous').addEventListener('click',guard(()=>shiftChart(-1)));
  $('#chart-next').addEventListener('click',guard(()=>shiftChart(1)));
  document.addEventListener('fullscreenchange',()=>{state.chart?.resize();$('#chart-fullscreen').textContent=document.fullscreenElement?'Vollbild verlassen':'Vollbild';});
  $('#chart-export-assigned').addEventListener('click',guard(()=>{if(!state.query||!state.timeAssignment?.timezone_confirmed)throw new Error('Zuerst Historienstand mit bestätigter Zeitzone laden.');const query=new URLSearchParams(state.query);query.set('time_basis','assigned');const link=document.createElement('a');link.href=`api/export?${query}`;link.click();}));
  $('#timezone-form').addEventListener('submit',guard(async event=>{event.preventDefault();if(state.source!=='device'||!state.snapshot)throw new Error('Zuerst einen Historienstand auswählen.');await post('time-assignment',{logger:state.logger,snapshot:state.snapshot.id,timezone:$('#history-timezone').value,timezone_confirmed:$('#timezone-confirmed').checked});$('#timezone-confirmed').checked=false;await loadHistory(true);notice('Zeitzone für diesen Historienstand bestätigt. Datum bleibt ungeprüft; Originaldateien erhalten.');}));
  $('#autosync-form').addEventListener('submit',guard(async event=>{event.preventDefault();await post('autosync',{enabled:$('#autosync-enabled').checked,interval_minutes:Number($('#autosync-interval').value)});await refreshAutoSync(true);notice(state.autoSync.config.enabled?'Automatische Nachladeversuche gespeichert. Erster Versuch nach Ablauf des Intervalls.':'Automatische Nachladeversuche ausgeschaltet.');}));
  $('#device-settings-read').addEventListener('click',guard(async()=>{await post('device-settings/read',{});await refreshSync();await refreshLive();await refreshBluetooth();}));
  $('#device-settings-draft').addEventListener('submit',guard(previewDeviceDraft));
  $('#device-settings-draft').addEventListener('input',()=>{deviceDraftReviewed=null;deviceDraftRevision++;$('#device-config-loss').checked=false;$('#device-config-stop').checked=false;configurationControls();$('#device-draft-result').replaceChildren();$('#device-draft-status').textContent=deviceDraftBase?.capture===deviceDraftLatest?.capture?'Entwurf geändert. Erneut prüfen; noch nichts am Gerät gespeichert.':'Einstellungsstand ersetzt. Zuerst aktuellen Stand übernehmen.';});
  $('#device-draft-reset').addEventListener('click',()=>updateDeviceDraft(deviceDraftLatest,true));
  $('#recording-prepare').addEventListener('click',guard(async()=>{await post('recording/prepare',$('#recording-unread-allow').checked?{allow_unread_history_loss:true}:{});await refreshSync();await refreshRecording();}));
  for(const selector of ['#recording-loss','#recording-consent','#recording-unread-confirm'])$(selector).addEventListener('change',recordingControls);
  $('#recording-start').addEventListener('click',guard(async()=>{await post('recording/start',{token:state.recording?.prepared?.token,confirm_history_loss:$('#recording-loss').checked,confirm_start:$('#recording-consent').checked,...(state.recording?.prepared?.allow_unread_history_loss?{confirm_unread_history_loss:$('#recording-unread-confirm').checked}:{})});$('#recording-loss').checked=false;$('#recording-consent').checked=false;$('#recording-unread-confirm').checked=false;await refreshSync();await refreshRecording();}));
  $('#recording-cancel').addEventListener('click',guard(async()=>{await post('recording/cancel',{});await refreshRecording();}));
  $('#recording-verify').addEventListener('click',guard(async()=>{await post('recording/verify',{});await refreshSync();await refreshRecording();}));
  $('#device-config-prepare').addEventListener('click',guard(async()=>{if(!deviceDraftReviewed?.changes.length)throw new Error('Änderungen zuerst prüfen.');await post('device-settings/prepare',{base_capture:deviceDraftBase.capture,changes:deviceDraftValues()});await refreshSync();await refreshConfiguration();}));
  for(const selector of ['#device-config-loss','#device-config-stop'])$(selector).addEventListener('change',configurationControls);
  $('#device-config-verify').addEventListener('click',guard(async()=>{await post('device-settings/verify',{});await refreshSync();await refreshConfiguration();}));
  $('#device-config-cancel').addEventListener('click',guard(async()=>{await post('device-settings/cancel',{});await refreshConfiguration();}));
  $('#device-config-apply').addEventListener('click',guard(async()=>{if(!configurationMatches())throw new Error('Entwurf passt nicht zur Vorbereitung. Erneut vorbereiten.');await post('device-settings/apply',{token:configurationState.prepared.token,confirm_history_loss:$('#device-config-loss').checked,confirm_stop:$('#device-config-stop').checked});$('#device-config-loss').checked=false;$('#device-config-stop').checked=false;await refreshSync();await refreshConfiguration();}));
  $('#sync-incremental').addEventListener('click',guard(async()=>{await post('sync',{mode:'incremental'});await refreshSync();await refreshLive();await refreshBluetooth();}));
  $('#sync-start').addEventListener('click',guard(async()=>{await post('sync',{});await refreshSync();await refreshLive();await refreshBluetooth();}));
  $('#ble-scan').addEventListener('click',guard(()=>startBluetooth('scan')));
  $('#capture-resume').addEventListener('click',guard(()=>startReceive()));
  $('#capture-stop').addEventListener('click',guard(async()=>{await post('live/stop',{});await refreshLive();await refreshBluetooth();await renderCards();notice('Empfang am DeskPi pausiert. Loggeraufzeichnung unverändert.');}));
  $('#source-select').addEventListener('change',guard(async()=>{setSource($('#source-select').value);await renderCards();await loadHistory();}));
  $('#live-follow').addEventListener('change',guard(async()=>{state.follow=$('#live-follow').checked;if(state.follow)await loadHistory();}));
  $('#overview-export').addEventListener('click',guard(async()=>{await loadHistory();exportCSV();}));
  $('#sites-reload').addEventListener('click',guard(()=>loadSites()));
  $('#site-form').addEventListener('submit',guard(saveSite));
  $('#site-form').addEventListener('input',()=>{siteDraftDirty=true;$('#site-draft-status').textContent='Ungespeicherter Entwurf.';siteControls();});
  $('#site-mode').addEventListener('change',siteControls);
  $('#site-new').addEventListener('click',()=>editSite(null));
  $('#site-reset').addEventListener('click',()=>editSite(siteEditing));
  for(const id of ['#assignment-logger','#assignment-site'])$(id).addEventListener('change',siteControls);
  $('#site-assign').addEventListener('click',guard(()=>assignSite()));
  $('#site-unassign').addEventListener('click',guard(()=>assignSite(true)));
  $('#export-prepare').addEventListener('click',guard(prepareExport));
  $('#export-scope').addEventListener('change',invalidateExport);
  $('#export-choices').addEventListener('input',exportControls);
  $('#export-download').addEventListener('click',guard(downloadPreparedExport));
  $('#events-form').addEventListener('submit',guard(async event=>{event.preventDefault();await loadEvents();}));
  $('#events-form').addEventListener('input',invalidateEvents);
  $('#events-export').addEventListener('click',guard(exportEvents));
  $('#events-selected').addEventListener('click',()=>{$('#events-logger').value=state.logger||'';invalidateEvents();});
  $('#statistics-range-button').addEventListener('click',guard(()=>analyzeStatistics()));
  $('#statistics-visible').addEventListener('click',guard(()=>analyzeStatistics(true)));
  $('#statistics-export').addEventListener('click',guard(exportStatistics));
  updateRiskControls();
  $('#risk-form').addEventListener('submit',guard(async event=>{event.preventDefault();await analyzeRisk();}));
  $('#risk-form').addEventListener('input',()=>{updateRiskControls();clearRisk();});
  $('#risk-mode').addEventListener('change',()=>{updateRiskControls();clearRisk();});
  $('#risk-visible').addEventListener('click',guard(()=>analyzeRisk(true)));
  $('#climate-form').addEventListener('submit',guard(calculateClimate));
  $('#climate-form').addEventListener('input',()=>{climateRevision++;$('#climate-results').replaceChildren();$('#climate-status').textContent='Eingaben geändert; erneut berechnen.';$('#climate-input-source').textContent='Manuelle Eingaben; Oberflächentemperatur als Annahme.';});
  $('#climate-copy').addEventListener('click',guard(copyClimateReading));
  $('#simulation-form').addEventListener('submit',guard(async event=>{
    event.preventDefault();const button=event.target.querySelector('button[type=submit]');button.disabled=true;button.textContent='Wird erzeugt …';
    try{const form=new FormData(event.target);const result=await post('simulation',{scenario:form.get('scenario'),days:Number(form.get('days')),interval_minutes:Number(form.get('interval_minutes')),seed:Number(form.get('seed'))});setSource('simulation');await refreshRuns(result.id);go('history');await loadHistory();notice('Testdaten gespeichert. Alle Werte sind synthetisch.');}finally{button.disabled=false;button.textContent='Testdaten erzeugen';}
  }));
  $('#settings-form').addEventListener('input',invalidateSettingsPreview);
  $('#settings-form').addEventListener('submit',guard(saveAllSettings));
  $('#load-settings').addEventListener('click',()=>$('#settings-file').click());
  $('#settings-file').addEventListener('change',guard(loadSettingsFile));
  $('#settings-preview').addEventListener('click',guard(previewSettingsImport));
  $('#settings-include-sites').addEventListener('change',invalidateSettingsPreview);
  $('#settings-cancel-import').addEventListener('click',()=>{clearSettingsImport();fillSettings(state.saved);notice('Dateivorschau verworfen.');});
  await diagnostics();await refreshLive();await refreshSync();await refreshAutoSync(true);await refreshDeviceSettings();await refreshBluetooth();await refreshRuns();await refreshSnapshots();updateHistorySites(await api('sites'));setSource(localStorage.getItem('bt06-source')||(state.liveLoggers.length?'live':'simulation'));await renderCards();go(location.hash.slice(1)||'overview');if(location.hash==='#history')await loadHistory();
  let lastUpdate=Date.now();setInterval(guard(async()=>{if(document.hidden||Date.now()-lastUpdate<state.saved.refresh_seconds*1000)return;lastUpdate=Date.now();await diagnostics();await refreshSync();await refreshLive();await refreshAutoSync();await refreshDeviceSettings();await refreshBluetooth();if(state.source==='live'){await renderCards();if(!$('#page-history').hidden&&state.follow)await loadHistory(true);}}),1000);
}
guard(main)();
