'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {settings: null, saved: null, csrf: '', runs: [], run: null, logger: null, chart: null, chartData: null, selection: {}, query: null, loading: 0, source:'simulation', live:null, liveLoggers:[], follow:true, snapshots:[], series:[], snapshot:null, sync:null, autoSync:null, timeAssignment:null};
const titles = {overview:'Übersicht', history:'Klimaverlauf', simulation:'Testdaten', logger:'Logger / Bluetooth', settings:'Einstellungen', diagnostics:'Diagnose'};
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
  if(page==='history') { if(!state.chart) initChart(); state.chart?.resize(); }
}
function chartDate(value) { return state.source==='device'?new Intl.DateTimeFormat('de-DE',{dateStyle:'short',timeStyle:'short',timeZone:'UTC'}).format(new Date(value)):date(value); }
function element(tag, text, className) { const node=document.createElement(tag); if(text!=null) node.textContent=text; if(className) node.className=className; return node; }
function downloadSettings(value) {
  const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'});
  const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='bt06-settings.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}
function formSettings() {
  const data=new FormData($('#settings-form'));
  return {schema_version:1,theme:data.get('theme'),timezone:data.get('timezone'),refresh_seconds:Number(data.get('refresh_seconds')),default_hours:Number(data.get('default_hours')),humidity_warning:Number(data.get('humidity_warning')),humidity_critical:Number(data.get('humidity_critical'))};
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
function dirty() { const changed=JSON.stringify(formSettings())!==JSON.stringify(state.saved); $('#dirty').textContent=changed?'Ungespeichert':'Gespeichert'; $('#dirty').classList.toggle('warning',changed); }
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
function chooseLogger() {
  const select=$('#logger-select'), previous=state.logger;select.replaceChildren();
  const loggers=state.source==='live'?state.liveLoggers:state.source==='device'?[...new Set(state.snapshots.map(s=>s.logger))].map(id=>({id,name:'BT06 '+id.replace('bt06-','')})):state.run?.loggers||[];
  for(const logger of loggers) addOption(select,logger.id,logger.name);
  state.logger=loggers.find(l=>l.id===previous)?.id||loggers[0]?.id||null;
  select.value=state.logger||'';
  if(state.source==='device') populateSnapshots();
  $('#chart-export').disabled=!state.logger;$('#overview-export').disabled=!state.logger;
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
    card.append(readings,element('p',`24 h: ${number(data.min_temperature)}–${number(data.max_temperature)} °C · ${number(data.min_humidity,0)}–${number(data.max_humidity,0)} % rF`,'hint'));
    card.append(element('time',data.latest?`Letzter Testwert: ${date(data.latest[0])}`:'Keine Werte im Zeitraum.'));
    const button=element('button','Verlauf ansehen','secondary');button.addEventListener('click',guard(async()=>{state.logger=logger.id;$('#logger-select').value=logger.id;go('history');await loadHistory();}));card.append(button);cards.append(card);
  });
}
function buildQuery() {
  if(!state.logger||state.source==='simulation'&&!state.run) return null;
  const query=new URLSearchParams({source:state.source,logger:state.logger});
  if(state.source==='simulation')query.set('run',state.run.id);
  if(state.source==='device'){if(!state.snapshot)return null;query.set('snapshot',state.snapshot.id);}
  const period=$('#period').value;
  if(period==='custom') {
    if(!$('#range-start').value||!$('#range-end').value) throw new Error('Beginn und Ende angeben. Freie Zeitangaben gelten in der Browser-Zeitzone.');
    const suffix=state.source==='device'?'Z':'';const start=new Date($('#range-start').value+suffix),end=new Date($('#range-end').value+suffix);
    if(start>end) throw new Error('Beginn liegt nach dem Ende.');
    query.set('start',start.toISOString());query.set('end',end.toISOString());
  } else if(Number(period)>0) {
    const end=state.source==='live'?new Date():state.source==='device'?new Date(state.snapshot.last_device_calendar+'Z'):new Date(state.run.options.end);query.set('end',end.toISOString());query.set('start',new Date(end.getTime()-Number(period)*3600000).toISOString());
  }
  return query;
}
function initChart() {
  if(!window.echarts) {notice('Lokale Diagrammbibliothek fehlt. Installation prüfen.',true);return;}
  state.chart=echarts.init($('#chart'),null,{renderer:'canvas'});
  state.chart.on('legendselectchanged',event=>{state.selection=event.selected;localStorage.setItem('bt06-curves',JSON.stringify(state.selection));});
  state.chart.on('datazoom',()=>{if(state.source==='live'){state.follow=false;$('#live-follow').checked=false;}});
  new ResizeObserver(()=>state.chart.resize()).observe($('#chart'));
  if(state.chartData)renderChart(state.chartData);
}
function renderChart(data, reset=false) {
  if(!state.chart) return;
  const css=getComputedStyle(document.documentElement), text=css.getPropertyValue('--muted').trim(), border=css.getPropertyValue('--border').trim();
  const savedZoom=reset?null:state.chart.getOption()?.dataZoom;
  const lines=[{name:'Warnlinie',yAxis:state.saved.humidity_warning,lineStyle:{color:'#c69e52'}},{name:'Kritische Linie',yAxis:state.saved.humidity_critical,lineStyle:{color:'#d47c7c'}}];
  state.chart.setOption({animation:false,color:['#f3a35c','#65aaff'],textStyle:{color:text},legend:{top:0,textStyle:{color:text},selected:state.selection},
    grid:{left:55,right:55,top:62,bottom:90},tooltip:{trigger:'axis',axisPointer:{type:'cross'},formatter:params=>{const valid=params.filter(p=>p.value[1]!=null);return valid.length?`${chartDate(valid[0].value[0])}<br>${valid.map(p=>`${p.marker}${p.seriesName}: ${number(p.value[1])} ${p.seriesIndex===0?'°C':'%'}`).join('<br>')}`:'Datenlücke';}},
    xAxis:{type:'time',axisLabel:{color:text,formatter:value=>new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:state.source==='device'?'UTC':state.saved.timezone}).format(value)},splitLine:{show:false}},
    yAxis:[{type:'value',name:'°C',scale:true,axisLabel:{color:text},splitLine:{lineStyle:{color:border}}},{type:'value',name:'% rF',min:0,max:100,axisLabel:{color:text},splitLine:{show:false}}],
    dataZoom:[{type:'inside',xAxisIndex:0,start:savedZoom?.[0]?.start??0,end:savedZoom?.[0]?.end??100},{type:'slider',xAxisIndex:0,bottom:12,height:25,start:savedZoom?.[1]?.start??0,end:savedZoom?.[1]?.end??100,textStyle:{color:text}}],
    series:[{name:'Temperatur',type:'line',showSymbol:false,connectNulls:false,data:data.points.map(p=>[p[0],p[1]])},{name:'Relative Feuchte',type:'line',showSymbol:false,connectNulls:false,yAxisIndex:1,data:data.points.map(p=>[p[0],p[2]]),markLine:{silent:true,symbol:'none',label:{show:false},data:lines}}]}, {notMerge:true});
}
async function loadHistory(refresh=false) {
  const query=buildQuery(); if(!query) {state.query=null;state.chartData=null;state.chart?.clear();$('#chart-caption').textContent='Keine Daten ausgewählt.';return;}
  const request=++state.loading; const data=await api(`history?${query}`);if(request!==state.loading)return;
  const assignment=query.get('source')==='device'?await api(`time-assignment?${new URLSearchParams({logger:query.get('logger'),snapshot:query.get('snapshot')})}`):null;if(request!==state.loading)return;state.timeAssignment=assignment;
  $('#chart-export-assigned').hidden=!assignment;$('#chart-export-assigned').disabled=!assignment?.timezone_confirmed;$('#timezone-panel').hidden=!assignment;
  if(assignment){$('#timezone-status').textContent=assignment.timezone_confirmed?`${assignment.timezone} bestätigt · ${assignment.assigned_count} Werte zugeordnet · ${assignment.unassigned_count} spätere/unbestätigte Werte · Datum weiterhin ungeprüft`:'Zeitzone dieses Historienstands noch nicht bestätigt.';if(assignment.timezone)$('#history-timezone').value=assignment.timezone;}
  const reset=!refresh&&state.query?.toString()!==query.toString();state.query=query;state.chartData=data;
  $('#chart-caption').textContent=`${data.raw_count.toLocaleString('de-DE')} ${state.source==='live'?'BLE-Empfänge':state.source==='device'?'Loggerwerte':'Testwerte'} · ${data.points.length.toLocaleString('de-DE')} Grafikpunkte · ${state.source==='device'?'Gerätezeit · Datum/Offset ungeprüft':state.saved.timezone}`;
  renderChart(data,reset);
}
function exportCSV() { if(!state.query) throw new Error('Zuerst einen Verlauf laden.');const link=document.createElement('a');link.href=`api/export?${state.query}`;link.click(); }
async function diagnostics() {
  const data=await api('status');$('#version').textContent=data.version;
  $('#template-note').textContent=data.local_profiles?'Lokale Zigbee-Klimavorlagen verfügbar. Erzeugte Werte bleiben synthetisch.':'Allgemeine synthetische Klimavorlagen. Zigbee-Vorlagen können lokal eingelesen werden.';
  const target=$('#diagnostics');target.replaceChildren();
  for(const [key,value] of [['Version',data.version],['Betrieb',data.mode==='advertising'?'BLE-Advertising-Empfang':'Offline'],['Laufzeit',`${data.uptime_seconds} Sekunden`],['Bluetooth',data.ble.status],['Freier Speicher',`${number(data.free_bytes/1073741824)} GiB`],['Einstellungen','JSON · Save / Load'],['Datenquellen','BLE-Empfänge / Simulation getrennt']])target.append(element('dt',key),element('dd',value));
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
  state.loading++;state.chartData=null;state.query=null;state.chart?.clear();$('#timezone-panel').hidden=true;$('#chart-export-assigned').hidden=true;
  state.source=source;localStorage.setItem('bt06-source',source);$('#source-select').value=source;
  const live=source==='live',device=source==='device';$('#run-label').hidden=live;$('#live-follow-label').hidden=!live;
  $('#run-title').textContent=device?'Historienstand':'Testlauf';
  $('#source-notice').classList.toggle('real-notice',live);
  $('#source-notice strong').textContent=live?'Echte BT06-Empfänge':device?'Loggerhistorie · Gerätezeit ungeprüft':'Synthetische Testdaten';
  $('#source-notice span').textContent=live?'BLE-Advertising · Zeitbasis: Host-Empfang · keine Loggerhistorie':device?'Originale Loggerwerte · Datum und UTC-Offset nicht bestätigt · keine automatische Zeitkorrektur':'Alle dargestellten Werte dieser Datenquelle sind simuliert.';
  $('#overview-note').textContent=live?'Aktuelle Aussendungen und lokal gespeicherte Empfänge. Veraltete Werte werden gekennzeichnet.':device?'Vollständig gelesene Historienstände. Keine aktuellen Livewerte.':'Letzter Testlauf · keine Livewerte und keine Schimmelbewertung.';
  $('#chart-time-note').textContent=device?'Zeitachse und freie Datumseingaben zeigen unveränderten Gerätekalender ohne bestätigten UTC-Offset. CSV enthält Original-Gerätesekunden und keine erfundenen UTC-Zeitstempel.':'Temperatur in °C · relative Feuchte in % · Lücken bleiben sichtbar. CSV enthält die Originalauflösung des gewählten Zeitraums, unabhängig vom Grafikzoom.';
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
  const labels={pausing_host:'Hostempfang wird pausiert',connecting:state.sync.trigger==='automatic'?'Automatischer Verbindungsversuch ohne Tastendruck':'Verbindung wartet auf kurzen Tastendruck',reading_metadata:'Metadaten lesen',selecting_range:'Nachladebereich wählen',full_fallback:'Vollauslesung erforderlich',receiving:'Historie empfangen',saving:'CSV dauerhaft speichern',finished:'Abgeschlossen'};
  $('#sync-start').disabled=busy||!state.live?.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;
  $('#sync-button-signal').hidden=!(busy&&state.sync.trigger!=='automatic'&&state.sync.phase==='connecting');
  const result=state.sync.result;
  $('#sync-status').textContent=[labels[state.sync.phase]||'Bereit zum manuellen Auslesen.',busy&&state.sync.expected?`${state.sync.received} / ${state.sync.expected} Werte`:'',result?(result.last_transfer_scope==='range'?`${result.new_count} neue Werte · ${result.received_count} Werte einschließlich Überlappung geprüft · ${result.count} Werte im Gesamtbestand · ${result.duplicate?'keine Änderung':'dauerhaft gespeichert'}`:`${result.count} Werte vollständig geprüft · ${result.duplicate?'bereits vorhanden, keine Kopie':'dauerhaft gespeichert'}`):'',state.sync.error||'',state.sync.resume_error||''].filter(Boolean).join(' · ');
  if(busy&&!syncPolling)syncPolling=setInterval(guard(refreshSync),1000);
  if(!busy&&syncPolling){clearInterval(syncPolling);syncPolling=null;}
  if(previous==='running'&&!busy){await refreshLive();await refreshSnapshots();await refreshBluetooth();await refreshAutoSync();await renderCards();}
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
  $('#capture-stop').disabled=!active||syncing;$('#capture-resume').hidden=!live.config.device||active;$('#capture-resume').disabled=syncing;$('#sync-start').disabled=syncing||!live.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;
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
  $('#sync-start').disabled=data.state==='running'||state.sync?.state==='running'||!state.live?.config.device;$('#sync-incremental').disabled=$('#sync-start').disabled;
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
  $('#logger-select').addEventListener('change',guard(async()=>{state.logger=$('#logger-select').value;await loadHistory();}));
  $('#period').addEventListener('change',guard(async()=>{$('#custom-period').hidden=$('#period').value!=='custom';if($('#period').value!=='custom')await loadHistory();}));
  $('#apply-range').addEventListener('click',guard(()=>loadHistory()));
  $('#chart-reset').addEventListener('click',()=>{if(state.chartData)renderChart(state.chartData,true);});
  $('#chart-fullscreen').addEventListener('click',guard(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('#chart').requestFullscreen();}));
  $('#chart-export').addEventListener('click',guard(exportCSV));
  $('#chart-export-assigned').addEventListener('click',guard(()=>{if(!state.query||!state.timeAssignment?.timezone_confirmed)throw new Error('Zuerst Historienstand mit bestätigter Zeitzone laden.');const query=new URLSearchParams(state.query);query.set('time_basis','assigned');const link=document.createElement('a');link.href=`api/export?${query}`;link.click();}));
  $('#timezone-form').addEventListener('submit',guard(async event=>{event.preventDefault();if(state.source!=='device'||!state.snapshot)throw new Error('Zuerst einen Historienstand auswählen.');await post('time-assignment',{logger:state.logger,snapshot:state.snapshot.id,timezone:$('#history-timezone').value,timezone_confirmed:$('#timezone-confirmed').checked});$('#timezone-confirmed').checked=false;await loadHistory(true);notice('Zeitzone für diesen Historienstand bestätigt. Datum bleibt ungeprüft; Originaldateien erhalten.');}));
  $('#autosync-form').addEventListener('submit',guard(async event=>{event.preventDefault();await post('autosync',{enabled:$('#autosync-enabled').checked,interval_minutes:Number($('#autosync-interval').value)});await refreshAutoSync(true);notice(state.autoSync.config.enabled?'Automatische Nachladeversuche gespeichert. Erster Versuch nach Ablauf des Intervalls.':'Automatische Nachladeversuche ausgeschaltet.');}));
  $('#sync-incremental').addEventListener('click',guard(async()=>{await post('sync',{mode:'incremental'});await refreshSync();await refreshLive();await refreshBluetooth();}));
  $('#sync-start').addEventListener('click',guard(async()=>{await post('sync',{});await refreshSync();await refreshLive();await refreshBluetooth();}));
  $('#ble-scan').addEventListener('click',guard(()=>startBluetooth('scan')));
  $('#capture-resume').addEventListener('click',guard(()=>startReceive()));
  $('#capture-stop').addEventListener('click',guard(async()=>{await post('live/stop',{});await refreshLive();await refreshBluetooth();await renderCards();notice('Empfang am DeskPi pausiert. Loggeraufzeichnung unverändert.');}));
  $('#source-select').addEventListener('change',guard(async()=>{setSource($('#source-select').value);await renderCards();await loadHistory();}));
  $('#live-follow').addEventListener('change',guard(async()=>{state.follow=$('#live-follow').checked;if(state.follow)await loadHistory();}));
  $('#overview-export').addEventListener('click',guard(async()=>{await loadHistory();exportCSV();}));
  $('#simulation-form').addEventListener('submit',guard(async event=>{
    event.preventDefault();const button=event.target.querySelector('button[type=submit]');button.disabled=true;button.textContent='Wird erzeugt …';
    try{const form=new FormData(event.target);const result=await post('simulation',{scenario:form.get('scenario'),days:Number(form.get('days')),interval_minutes:Number(form.get('interval_minutes')),seed:Number(form.get('seed'))});setSource('simulation');await refreshRuns(result.id);go('history');await loadHistory();notice('Testdaten gespeichert. Alle Werte sind synthetisch.');}finally{button.disabled=false;button.textContent='Testdaten erzeugen';}
  }));
  $('#settings-form').addEventListener('input',dirty);
  $('#settings-form').addEventListener('submit',guard(async event=>{event.preventDefault();const result=await post('settings',checkSettings(formSettings()));state.saved=result;fillSettings(result);applySettings();downloadSettings(result);notice('Einstellungen gespeichert und als JSON zum Download bereitgestellt.');}));
  $('#load-settings').addEventListener('click',()=>$('#settings-file').click());
  $('#settings-file').addEventListener('change',guard(async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>16384)throw new Error('Einstellungsdatei ist zu groß.');fillSettings(checkSettings(JSON.parse(await file.text())));notice('Einstellungen eingelesen. Mit Save Settings übernehmen.');}finally{event.target.value='';}}));
  await diagnostics();await refreshLive();await refreshSync();await refreshAutoSync(true);await refreshBluetooth();await refreshRuns();await refreshSnapshots();setSource(localStorage.getItem('bt06-source')||(state.liveLoggers.length?'live':'simulation'));await renderCards();go(location.hash.slice(1)||'overview');if(location.hash==='#history')await loadHistory();
  let lastUpdate=Date.now();setInterval(guard(async()=>{if(document.hidden||Date.now()-lastUpdate<state.saved.refresh_seconds*1000)return;lastUpdate=Date.now();await diagnostics();await refreshSync();await refreshLive();await refreshAutoSync();await refreshBluetooth();if(state.source==='live'){await renderCards();if(!$('#page-history').hidden&&state.follow)await loadHistory(true);}}),1000);
}
guard(main)();
