'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {settings: null, saved: null, csrf: '', runs: [], run: null, logger: null, chart: null, chartData: null, selection: {}, query: null, loading: 0};
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
    const button=element('button','Ansehen','secondary'); button.addEventListener('click',guard(async()=>{await refreshRuns(run.id);go('history');await loadHistory();}));
    row.append(details,button);list.append(row);
  }
  await renderCards();
}
function chooseLogger() {
  const select=$('#logger-select'), previous=state.logger;select.replaceChildren();
  for(const logger of state.run?.loggers||[]) addOption(select,logger.id,logger.name);
  state.logger=state.run?.loggers.find(l=>l.id===previous)?.id||state.run?.loggers[0]?.id||null;
  select.value=state.logger||'';
  $('#chart-export').disabled=!state.logger;$('#overview-export').disabled=!state.logger;
}
async function renderCards() {
  const cards=$('#cards'); if(!state.run) return;
  const run=state.run;
  const values=await Promise.all(run.loggers.map(logger=>api(`history?${new URLSearchParams({run:run.id,logger:logger.id,end:run.options.end,start:new Date(new Date(run.options.end).getTime()-86400000).toISOString()})}`)));
  if(state.run?.id!==run.id) return;
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
  if(!state.run||!state.logger) return null;
  const query=new URLSearchParams({run:state.run.id,logger:state.logger});
  const period=$('#period').value;
  if(period==='custom') {
    if(!$('#range-start').value||!$('#range-end').value) throw new Error('Beginn und Ende angeben. Freie Zeitangaben gelten in der Browser-Zeitzone.');
    const start=new Date($('#range-start').value),end=new Date($('#range-end').value);
    if(start>end) throw new Error('Beginn liegt nach dem Ende.');
    query.set('start',start.toISOString());query.set('end',end.toISOString());
  } else if(Number(period)>0) {
    const end=new Date(state.run.options.end);query.set('end',end.toISOString());query.set('start',new Date(end.getTime()-Number(period)*3600000).toISOString());
  }
  return query;
}
function initChart() {
  if(!window.echarts) {notice('Lokale Diagrammbibliothek fehlt. Installation prüfen.',true);return;}
  state.chart=echarts.init($('#chart'),null,{renderer:'canvas'});
  state.chart.on('legendselectchanged',event=>{state.selection=event.selected;localStorage.setItem('bt06-curves',JSON.stringify(state.selection));});
  new ResizeObserver(()=>state.chart.resize()).observe($('#chart'));
  if(state.chartData)renderChart(state.chartData);
}
function renderChart(data, reset=false) {
  if(!state.chart) return;
  const css=getComputedStyle(document.documentElement), text=css.getPropertyValue('--muted').trim(), border=css.getPropertyValue('--border').trim();
  const savedZoom=reset?null:state.chart.getOption()?.dataZoom;
  const lines=[{name:'Warnlinie',yAxis:state.saved.humidity_warning,lineStyle:{color:'#c69e52'}},{name:'Kritische Linie',yAxis:state.saved.humidity_critical,lineStyle:{color:'#d47c7c'}}];
  state.chart.setOption({animation:false,color:['#f3a35c','#65aaff'],textStyle:{color:text},legend:{top:0,textStyle:{color:text},selected:state.selection},
    grid:{left:55,right:55,top:62,bottom:90},tooltip:{trigger:'axis',axisPointer:{type:'cross'},formatter:params=>{const valid=params.filter(p=>p.value[1]!=null);return valid.length?`${date(valid[0].value[0])}<br>${valid.map(p=>`${p.marker}${p.seriesName}: ${number(p.value[1])} ${p.seriesIndex===0?'°C':'%'}`).join('<br>')}`:'Datenlücke';}},
    xAxis:{type:'time',axisLabel:{color:text,formatter:value=>new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:state.saved.timezone}).format(value)},splitLine:{show:false}},
    yAxis:[{type:'value',name:'°C',scale:true,axisLabel:{color:text},splitLine:{lineStyle:{color:border}}},{type:'value',name:'% rF',min:0,max:100,axisLabel:{color:text},splitLine:{show:false}}],
    dataZoom:[{type:'inside',xAxisIndex:0,start:savedZoom?.[0]?.start??0,end:savedZoom?.[0]?.end??100},{type:'slider',xAxisIndex:0,bottom:12,height:25,start:savedZoom?.[1]?.start??0,end:savedZoom?.[1]?.end??100,textStyle:{color:text}}],
    series:[{name:'Temperatur',type:'line',showSymbol:false,connectNulls:false,data:data.points.map(p=>[p[0],p[1]])},{name:'Relative Feuchte',type:'line',showSymbol:false,connectNulls:false,yAxisIndex:1,data:data.points.map(p=>[p[0],p[2]]),markLine:{silent:true,symbol:'none',label:{show:false},data:lines}}]}, {notMerge:true});
}
async function loadHistory() {
  const query=buildQuery(); if(!query) return;
  const request=++state.loading; const data=await api(`history?${query}`);if(request!==state.loading)return;
  const reset=state.query?.toString()!==query.toString();state.query=query;state.chartData=data;
  $('#chart-caption').textContent=`${data.raw_count.toLocaleString('de-DE')} Testwerte · ${data.points.length.toLocaleString('de-DE')} Grafikpunkte · ${state.saved.timezone}`;
  renderChart(data,reset);
}
function exportCSV() { if(!state.query) throw new Error('Zuerst einen Verlauf laden.');const link=document.createElement('a');link.href=`api/export?${state.query}`;link.click(); }
async function diagnostics() {
  const data=await api('status');$('#version').textContent=data.version;
  $('#template-note').textContent=data.local_profiles?'Lokale Zigbee-Klimavorlagen verfügbar. Erzeugte Werte bleiben synthetisch.':'Allgemeine synthetische Klimavorlagen. Zigbee-Vorlagen können lokal eingelesen werden.';
  const target=$('#diagnostics');target.replaceChildren();
  for(const [key,value] of [['Version',data.version],['Betrieb','Offline / Simulation'],['Laufzeit',`${data.uptime_seconds} Sekunden`],['Bluetooth',data.ble.status],['Freier Speicher',`${number(data.free_bytes/1073741824)} GiB`],['Einstellungen','JSON · Save / Load'],['Originaldaten','Keine BT06-Daten erfasst']])target.append(element('dt',key),element('dd',value));
}
let blePolling=null;
async function refreshBluetooth() {
  const data=await api('ble');
  $('#ble-status').textContent=!data.available?'Optionale Bluetooth-Unterstützung fehlt. Mit ./install.sh --ble lokal installieren und das Programm neu starten.':data.state==='running'?'Bluetooth-Auftrag läuft …':data.error||`Bereit. Sichtbare Adapter: ${data.adapters.join(', ')||'keine erkannt'}.`;
  $('#ble-scan').disabled=!data.available||data.state==='running';
  for(const button of document.querySelectorAll('[data-ble-action]'))button.disabled=data.state==='running';
  if(data.state==='running') { if(!blePolling)blePolling=setInterval(guard(refreshBluetooth),1000);return; }
  if(blePolling){clearInterval(blePolling);blePolling=null;}
  if(data.command==='scan'&&data.result) {
    const target=$('#ble-devices');target.replaceChildren();
    if(!data.result.devices.length)target.append(element('p','Keine BLE-Geräte gefunden. Reichweite und Betriebszustand prüfen.','muted'));
    for(const device of data.result.devices) {
      const row=element('div',null,'run-item'),details=element('div');details.append(element('strong',device.name||'Unbenanntes BLE-Gerät'),element('p',`${device.address} · ${device.rssi} dBm · Modell unbestätigt`));
      const actions=element('div',null,'button-row');
      for(const [label,pair] of [['Verbinden & prüfen',false],['Koppeln & prüfen',true]]) {
        const button=element('button',label,'secondary');button.dataset.bleAction='true';button.addEventListener('click',guard(()=>startBluetooth('gatt',device.address,pair)));actions.append(button);
      }
      row.append(details,actions);target.append(row);
    }
  }
  if(data.command==='gatt'&&data.result){$('#ble-result').hidden=false;$('#ble-result').textContent=JSON.stringify(data.result,null,2);$('#ble-status').textContent='GATT-Inventar gelesen. Diagnoseverbindung geschlossen; keine Liveaufzeichnung.';}
}
async function startBluetooth(command, device, pair=false) {
  const adapter=$('#ble-adapter').value;if(!/^hci[0-9]{1,3}$/.test(adapter))throw new Error('Adapter als hci0, hci1, … angeben.');
  const value={command,adapter,seconds:10};if(device){value.device=device;value.pair=pair;}
  await post('ble',value);await refreshBluetooth();
}
async function main() {
  state.csrf=(await api('session')).csrf_token;state.saved=await api('settings');fillSettings(state.saved);applySettings();
  const hours=String(state.saved.default_hours);if(![...$('#period').options].some(o=>o.value===hours))addOption($('#period'),hours,`${hours} Stunden`);$('#period').value=hours;
  try{state.selection=JSON.parse(localStorage.getItem('bt06-curves')||'{}');}catch{state.selection={};}
  for(const button of document.querySelectorAll('[data-page]'))button.addEventListener('click',guard(async()=>{go(button.dataset.page);if(button.dataset.page==='history')await loadHistory();}));
  for(const button of document.querySelectorAll('[data-go]'))button.addEventListener('click',()=>go(button.dataset.go));
  window.addEventListener('hashchange',guard(async()=>{go(location.hash.slice(1));if(location.hash==='#history')await loadHistory();}));
  $('#run-select').addEventListener('change',guard(async()=>{state.run=state.runs.find(r=>r.id===$('#run-select').value);chooseLogger();await loadHistory();}));
  $('#logger-select').addEventListener('change',guard(async()=>{state.logger=$('#logger-select').value;await loadHistory();}));
  $('#period').addEventListener('change',guard(async()=>{$('#custom-period').hidden=$('#period').value!=='custom';if($('#period').value!=='custom')await loadHistory();}));
  $('#apply-range').addEventListener('click',guard(loadHistory));
  $('#chart-reset').addEventListener('click',()=>{if(state.chartData)renderChart(state.chartData,true);});
  $('#chart-fullscreen').addEventListener('click',guard(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('#chart').requestFullscreen();}));
  $('#chart-export').addEventListener('click',guard(exportCSV));
  $('#ble-scan').addEventListener('click',guard(()=>startBluetooth('scan')));
  $('#overview-export').addEventListener('click',guard(async()=>{await loadHistory();exportCSV();}));
  $('#simulation-form').addEventListener('submit',guard(async event=>{
    event.preventDefault();const button=event.target.querySelector('button[type=submit]');button.disabled=true;button.textContent='Wird erzeugt …';
    try{const form=new FormData(event.target);const result=await post('simulation',{scenario:form.get('scenario'),days:Number(form.get('days')),interval_minutes:Number(form.get('interval_minutes')),seed:Number(form.get('seed'))});await refreshRuns(result.id);go('history');await loadHistory();notice('Testdaten gespeichert. Alle Werte sind synthetisch.');}finally{button.disabled=false;button.textContent='Testdaten erzeugen';}
  }));
  $('#settings-form').addEventListener('input',dirty);
  $('#settings-form').addEventListener('submit',guard(async event=>{event.preventDefault();const result=await post('settings',checkSettings(formSettings()));state.saved=result;fillSettings(result);applySettings();downloadSettings(result);notice('Einstellungen gespeichert und als JSON zum Download bereitgestellt.');}));
  $('#load-settings').addEventListener('click',()=>$('#settings-file').click());
  $('#settings-file').addEventListener('change',guard(async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>16384)throw new Error('Einstellungsdatei ist zu groß.');fillSettings(checkSettings(JSON.parse(await file.text())));notice('Einstellungen eingelesen. Mit Save Settings übernehmen.');}finally{event.target.value='';}}));
  await diagnostics();await refreshBluetooth();await refreshRuns();go(location.hash.slice(1)||'overview');if(location.hash==='#history')await loadHistory();
  let lastUpdate=Date.now();setInterval(guard(async()=>{if(document.hidden||Date.now()-lastUpdate<state.saved.refresh_seconds*1000)return;lastUpdate=Date.now();await diagnostics();}),1000);
}
guard(main)();
