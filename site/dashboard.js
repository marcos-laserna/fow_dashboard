(function () {
  'use strict';

  const INE_ID = 'ine_retail_sales_madrid';
  const INE_NEEDLE = 'Madrid, Comunidad de. Cifra de negocio a precios constantes. Comercio al por menor, excepto de vehículos de motor y motocicletas. General. Índice';
  const AUTOMATION_TABLES = [
    {id:'60288',series:'ine_iass_raw',label:'IASS · Original (60288)',family:'iass',aliases:['indice general','total servicios','sector servicios de mercado']},
    {id:'60289',series:'ine_iass_wda',label:'IASS · Ajustado calendario (60289)',family:'iass',aliases:['indice general','total servicios','sector servicios de mercado']},
    {id:'60290',series:'ine_iass_cvec',label:'IASS · Ajustado calendario y estacionalidad (60290)',family:'iass',aliases:['indice general','total servicios','sector servicios de mercado']},
    {id:'60272',series:'ine_ipi_raw',label:'IPI · Original (60272)',family:'ipi',aliases:['total industria','indice general','general']},
    {id:'60276',series:'ine_ipi_wda',label:'IPI · Ajustado calendario (60276)',family:'ipi',aliases:['total industria','indice general','general']},
    {id:'60280',series:'ine_ipi_cvec',label:'IPI · Ajustado calendario y estacionalidad (60280)',family:'ipi',aliases:['total industria','indice general','general']}
  ];
  const CSV_FIELDS = ['series_id','series_name','source','period','value','unit','frequency','retrieved_at'];
  let currentRows = [];
  const seriesSelectionByMode = {};
  const sourceSelection = new Set();
  const knownSources = new Set();
  let activeSeriesMode = null;
  const fmt = value => new Intl.NumberFormat('es-ES',{maximumFractionDigits:1}).format(value);

  function parseCsv(text) {
    const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/);
    const parseLine=line=>{const out=[];let cell='',quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'&&quoted&&line[i+1]==='"'){cell+='"';i++;}else if(c==='"'){quoted=!quoted;}else if(c===','&&!quoted){out.push(cell);cell='';}else{cell+=c;}}out.push(cell);return out;};
    const headers=parseLine(lines.shift());
    return lines.filter(Boolean).map(line=>Object.fromEntries(parseLine(line).map((value,index)=>[headers[index],value])));
  }

  function dateNumber(period) {
    const month=period.match(/^(\d{4})-(\d{2})$/);
    if(month)return Date.UTC(Number(month[1]),Number(month[2])-1,1);
    const quarter=period.match(/^(\d{4})-T([1-4])$/);
    if(quarter)return Date.UTC(Number(quarter[1]),(Number(quarter[2])-1)*3,1);
    return Date.parse(period);
  }

  function displayDate(period) {
    const date=new Date(dateNumber(period));
    return Number.isNaN(date.getTime())?period:date.toISOString().slice(0,7);
  }

  function escapeHtml(value) {
    const entities={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(value).replace(/[&<>"']/g,char=>entities[char]);
  }

  function latestOf(rows) {
    return rows.slice().sort((a,b)=>dateNumber(a.period)-dateNumber(b.period)).at(-1);
  }

  function updateCards() {
    const ine=currentRows.filter(row=>row.source==='INE'&&row.series_id===INE_ID);
    const manual=currentRows.filter(row=>row.source.startsWith('Excel:'));
    const last=latestOf(ine),manualLast=latestOf(manual);
    if(last){document.getElementById('latest-value').textContent=fmt(Number(last.value));document.getElementById('latest-period').textContent=displayDate(last.period);}
    document.getElementById('period-count').textContent=String(ine.length);
    document.getElementById('manual-status').textContent=manualLast?fmt(Number(manualLast.value)):'Pendiente';
    document.getElementById('manual-detail').textContent=manualLast?manualLast.series_name+' · '+displayDate(manualLast.period):'Añade un Excel a data/manual/';
  }

  function buildGroups(mode) {
    const ine=currentRows.filter(r=>r.source==='INE'&&r.series_id===INE_ID);
    const manual=currentRows.filter(r=>r.source.startsWith('Excel:'));
    const colors={ine_iass_raw:'#2463eb',ine_iass_wda:'#0c9488',ine_iass_cvec:'#d97706',ine_ipi_raw:'#2463eb',ine_ipi_wda:'#0c9488',ine_ipi_cvec:'#d97706'};
    let groups=[];
    if(mode==='retail')groups=[{key:INE_ID,name:'INE · Madrid',rows:ine,color:'#2463eb'}];
    else if(mode==='ipc'||mode==='icm'){
      const subset=currentRows.filter(row=>row.source==='INE'&&row.series_id.startsWith(mode.toUpperCase()));
      const bySeries=new Map();subset.forEach(row=>{if(!bySeries.has(row.series_id))bySeries.set(row.series_id,[]);bySeries.get(row.series_id).push(row);});
      const palette=['#2463eb','#0c9488','#d97706','#7c3aed','#db2777','#0284c7'];
      groups=Array.from(bySeries.entries()).map(([key,rows],i)=>({key,name:rows[0].series_name,rows,color:palette[i%palette.length]}));
    }
    else groups=AUTOMATION_TABLES.filter(spec=>spec.family===mode).map(spec=>({key:spec.series,name:spec.label,rows:currentRows.filter(row=>row.series_id===spec.series),color:colors[spec.series]}));
    const manualGroups=new Map();
    manual.forEach(row=>{const key=row.series_name||'Serie Excel';if(!manualGroups.has(key))manualGroups.set(key,[]);manualGroups.get(key).push(row);});
    if(mode==='retail')Array.from(manualGroups.entries()).forEach((entry,index)=>groups.push({key:'manual_series|'+entry[0],name:entry[0],rows:entry[1],color:index===0?'#0c9488':'#d97706'}));
    if(mode==='other'){
      const otherGroups=new Map(),palette=['#0c9488','#d97706','#7c3aed','#db2777','#0284c7'];
      currentRows.filter(row=>row.source!=='INE').forEach(row=>{const key=row.source+'|'+row.series_id+'|'+row.series_name;if(!otherGroups.has(key))otherGroups.set(key,[]);otherGroups.get(key).push(row);});
      Array.from(otherGroups.entries()).forEach((entry,index)=>groups.push({key:entry[0],name:sourceLabel(entry[1][0].source)+' · '+entry[1][0].series_name,rows:entry[1],color:palette[index%palette.length]}));
    }
    return groups;
  }

  function shortSeriesName(fullName) {
    const parts=String(fullName||'').split('.').map(part=>part.trim()).filter(Boolean);
    let territory=parts.shift()||'Espa\u00f1a';
    if(['Total Nacional','Nacional','Espa\u00f1a'].includes(territory))territory='Espa\u00f1a';
    let measure='';
    const source=parts.join(' ').toLocaleLowerCase('es');
    if(source.includes('precios constantes'))measure='Ventas reales';
    else if(source.includes('precios corrientes'))measure='Ventas nominales';
    else if(source.includes('ocupaci'))measure='Ocupaci\u00f3n';
    else if(source.includes('cifra de negocio'))measure='Ventas';
    let dimension=parts.find(part=>/^(general|alimentos|bebidas|vestido|vivienda|muebles|sanidad|transporte|comunicaciones|ocio|ense\u00f1anza|restaurantes|hoteles|otros bienes|alimentaci\u00f3n|resto|equipo personal|equipamiento del hogar)/i.test(part));
    const statistic=parts.find(part=>/\u00edndice|variaci\u00f3n/i.test(part))||'';
    const shortStatistic=statistic.toLocaleLowerCase('es').includes('variaci\u00f3n mensual')?'Cambio mensual':statistic.toLocaleLowerCase('es').includes('variaci\u00f3n anual')?'Cambio anual':statistic.toLocaleLowerCase('es').includes('media en lo que va')?'Acumulado anual':statistic.toLocaleLowerCase('es').includes('variaci\u00f3n')?'Variaci\u00f3n':'\u00cdndice';
    const detail=[territory,measure,dimension&&dimension!=='General'?dimension:null,shortStatistic].filter(Boolean);
    return detail.join(' \u00b7 ');
  }

  function statisticName(fullName) {
    const text=String(fullName||'').toLocaleLowerCase('es');
    if(text.includes('variaci\u00f3n mensual'))return 'Variaci\u00f3n mensual';
    if(text.includes('variaci\u00f3n anual'))return 'Variaci\u00f3n anual';
    if(text.includes('media en lo que va')||text.includes('lo que va de a\u00f1o'))return 'Variaci\u00f3n acumulada anual';
    if(text.includes('variaci\u00f3n'))return 'Variaci?n';
    if(text.includes('\u00edndice'))return '\u00cdndice';
    return 'Valor';
  }

  function renderSeriesOptions(mode) {
    const series=buildGroups(mode),previous=seriesSelectionByMode[mode],known=seriesSelectionByMode[mode+'_known']||new Set();
    const isCatalog=mode==='ipc'||mode==='icm';
    const catalogGroups=new Map();
    series.forEach(item=>{
      const parts=item.name.split('.').map(part=>part.trim()).filter(Boolean);
      const base=isCatalog?parts.slice(0,-1).join('. '):item.name;
      if(!catalogGroups.has(base))catalogGroups.set(base,[]);
      catalogGroups.get(base).push(item);
    });
    const entries=Array.from(catalogGroups.entries());
    const query=(document.getElementById('series-search')?.value||'').trim().toLocaleLowerCase('es');
    const visible=entries.filter(([base,items])=>!query||(base+' '+items.map(item=>item.name+' '+shortSeriesName(item.name)).join(' ')).toLocaleLowerCase('es').includes(query));
    const defaultKeys=new Set(entries.slice(0,2).flatMap(([,items])=>[items[0]?.key]).filter(Boolean));
    let shown=[];
    const renderOption=item=>{
      const checked=previous?previous.has(item.key):(!known.has(item.key)&&defaultKeys.has(item.key));
      shown.push(item.key);
      const label=isCatalog?statisticName(item.name):shortSeriesName(item.name);
      return '<label class="check-option" title="'+escapeHtml(item.name)+'"><input class="series-option" type="checkbox" value="'+escapeHtml(item.key)+'"'+(checked?' checked':'')+'> <span>'+escapeHtml(label)+'</span></label>';
    };
    document.getElementById('series-options').innerHTML=visible.map(([base,items])=>isCatalog
      ?'<details class="series-group"><summary>'+escapeHtml(shortSeriesName(base))+' <span>'+items.length+' c\u00e1lculos</span></summary><div class="series-children">'+items.map(renderOption).join('')+'</div></details>'
      :items.map(renderOption).join('')).join('');
    const selected=Array.from(document.querySelectorAll('#series-options input:checked')).length;
    document.getElementById('series-count').textContent=(query?visible.length+' grupos de '+entries.length:entries.length+' grupos')+' \u00b7 '+series.length+' series \u00b7 '+selected+' seleccionadas';
    seriesSelectionByMode[mode+'_known']=new Set(series.map(item=>item.key));
    activeSeriesMode=mode;
  }

  function renderSourceOptions() {
    const sources=Array.from(new Set(currentRows.map(row=>row.source))).sort((a,b)=>a.localeCompare(b));
    sources.forEach(source=>{if(!knownSources.has(source))sourceSelection.add(source);});
    Array.from(sourceSelection).forEach(source=>{if(!sources.includes(source))sourceSelection.delete(source);});
    sources.forEach(source=>knownSources.add(source));
    document.getElementById('source-options').innerHTML=sources.map(source=>'<label class="check-option"><input class="source-option" type="checkbox" value="'+escapeHtml(source)+'"'+(sourceSelection.has(source)?' checked':'')+'> '+escapeHtml(sourceLabel(source))+'</label>').join('');
  }

  function sourceLabel(source) { return source==='INE'?'INE':source.startsWith('Excel:')?'Excel · '+source.slice(6):source; }

  function selectedGroups() {
    const selected=new Set(Array.from(document.querySelectorAll('#series-options input:checked')).map(input=>input.value));
    return buildGroups(document.getElementById('indicator').value).filter(group=>selected.has(group.key));
  }

  function dateBounds(rows) {
    const times=rows.map(row=>dateNumber(row.period)).filter(Number.isFinite);
    let min=-Infinity,max=Infinity;
    const from=document.getElementById('date-from').value,to=document.getElementById('date-to').value;
    if(from)min=Date.UTC(Number(from.slice(0,4)),Number(from.slice(5,7))-1,1);
    if(to)max=Date.UTC(Number(to.slice(0,4)),Number(to.slice(5,7)),1)-1;
    const choice=document.getElementById('range').value;
    if(choice!=='all'&&times.length){const relative=new Date(Math.max(...times));relative.setUTCMonth(relative.getUTCMonth()-Number(choice));min=Math.max(min,relative.getTime());}
    return {min,max};
  }

  function niceStep(span, targetTicks) {
    const rough=span/targetTicks, magnitude=Math.pow(10,Math.floor(Math.log10(rough))), fraction=rough/magnitude;
    return (fraction<=1?1:fraction<=2?2:fraction<=5?5:10)*magnitude;
  }

  function draw() {
    const svg=document.getElementById('chart'),w=1000,h=360,p={l:72,r:22,t:18,b:45};
    const mode=document.getElementById('indicator').value;
    const groups=selectedGroups();
    const titles={ipc:['IPC \u00b7 precios y grupos de consumo','Cat\u00e1logo nacional del IPC: \u00edndices y variaciones.'],icm:['ICM \u00b7 comercio minorista','Cat\u00e1logo nacional del comercio minorista: \u00edndices y tasas.'],retail:['Ventas minoristas \u2014 Madrid','INE \u00b7 Madrid. Marca una serie manual para compararla si quieres.'],iass:['Indicador de actividad del sector servicios (IASS)','Tres versiones del \u00edndice general: original, ajustado de calendario y CVEC'],ipi:['\u00cdndice de producci\u00f3n industrial (IPI)','Tres versiones del \u00edndice general: original, ajustado de calendario y CVEC'],other:['Excel y otras fuentes','Series cargadas manualmente y bases adicionales.']};
    document.getElementById('chart-title').textContent=titles[mode][0];document.getElementById('chart-description').textContent=titles[mode][1];
    const all=groups.flatMap(group=>group.rows.map(row=>({row,time:dateNumber(row.period),value:Number(row.value)}))).filter(item=>Number.isFinite(item.time)&&Number.isFinite(item.value));
    if(!all.length){svg.innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">No hay observaciones para mostrar.</text>';return;}
    const bounds=dateBounds(all.map(item=>item.row));
    const filteredGroups=groups.map(group=>({...group,rows:group.rows.filter(row=>{const t=dateNumber(row.period);return t>=bounds.min&&t<=bounds.max;}).sort((a,b)=>dateNumber(a.period)-dateNumber(b.period))}));
    const available=filteredGroups.flatMap(group=>group.rows.map(row=>({row,time:dateNumber(row.period),value:Number(row.value),group}))).filter(item=>Number.isFinite(item.time)&&Number.isFinite(item.value));
    if(!available.length){svg.innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">No hay observaciones en este intervalo.</text>';return;}
    const unitNames=new Set(available.map(item=>item.row.unit).filter(Boolean)),normalized=unitNames.size>1||available.some(item=>!item.row.unit);
    const baselineTime=normalized?Math.max(...filteredGroups.filter(group=>group.rows.length).map(group=>Math.min(...group.rows.map(row=>dateNumber(row.period))))):null;
    const baselines=new Map();
    if(normalized){filteredGroups.forEach(group=>{const base=group.rows.find(row=>dateNumber(row.period)>=baselineTime&&Number(row.value)!==0);if(base)baselines.set(group.name,Number(base.value));});available.forEach(item=>{const base=baselines.get(item.group.name);item.plotValue=base?item.value/base*100:item.value;});}
    else available.forEach(item=>item.plotValue=item.value);
    const values=available.map(item=>item.plotValue),low=Math.min(...values),high=Math.max(...values),rawSpan=high-low||Math.max(Math.abs(high)*.1,1),step=niceStep(rawSpan,5),min=Math.floor(low/step)*step,max=Math.ceil(high/step)*step||min+step;
    const minTime=Math.min(...available.map(item=>item.time)),maxTime=Math.max(...available.map(item=>item.time));
    const x=t=>p.l+(t-minTime)*(w-p.l-p.r)/(maxTime-minTime||1),y=v=>h-p.b-(v-min)*(h-p.t-p.b)/(max-min||1),parts=[];
    for(let value=min;value<=max+step*.001;value+=step){const yy=y(value);parts.push('<line x1="'+p.l+'" y1="'+yy+'" x2="'+(w-p.r)+'" y2="'+yy+'" stroke="#e9edf2"/><text x="'+(p.l-10)+'" y="'+(yy+4)+'" text-anchor="end" fill="#718198" font-size="12">'+fmt(value)+'</text>');}
    const spanMonths=Math.max(1,(maxTime-minTime)/(86400000*30.4375)),tickCount=Math.min(6,Math.max(2,Math.floor(spanMonths/3)+1));
    for(let i=0;i<tickCount;i++){const tickTime=minTime+(maxTime-minTime)*i/(tickCount-1),label=new Date(tickTime).toISOString().slice(0,7);parts.push('<line x1="'+x(tickTime)+'" y1="'+(h-p.b)+'" x2="'+x(tickTime)+'" y2="'+(h-p.b+5)+'" stroke="#718198"/><text x="'+x(tickTime)+'" y="'+(h-12)+'" text-anchor="middle" fill="#718198" font-size="12">'+label+'</text>');}
    parts.push('<line x1="'+p.l+'" y1="'+p.t+'" x2="'+p.l+'" y2="'+(h-p.b)+'" stroke="#8b98a9"/><line x1="'+p.l+'" y1="'+(h-p.b)+'" x2="'+(w-p.r)+'" y2="'+(h-p.b)+'" stroke="#8b98a9"/>');
    filteredGroups.forEach(group=>{const rows=group.rows.filter(row=>Number.isFinite(dateNumber(row.period))&&Number.isFinite(Number(row.value)));if(!rows.length)return;const base=baselines.get(group.name),safeName=escapeHtml(group.name);const points=rows.map(row=>{const value=Number(row.value),plot=normalized&&base?value/base*100:value;return x(dateNumber(row.period))+','+y(plot);}).join(' ');parts.push('<polyline points="'+points+'" fill="none" stroke="'+group.color+'" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>');const stride=Math.max(1,Math.floor(rows.length/30));rows.forEach((row,index)=>{const value=Number(row.value),plot=normalized&&base?value/base*100:value,cx=x(dateNumber(row.period)),cy=y(plot),tip=safeName+' \u00b7 '+displayDate(row.period)+' \u00b7 '+fmt(value)+' '+escapeHtml(row.unit||'');parts.push('<circle class="data-point" tabindex="0" data-tip="'+tip+'" cx="'+cx+'" cy="'+cy+'" r="'+(index%stride===0||index===rows.length-1?4:6)+'" fill="'+group.color+'" fill-opacity="'+(index%stride===0||index===rows.length-1?'1':'0.01')+'" stroke="'+group.color+'" stroke-opacity="'+(index%stride===0||index===rows.length-1?'1':'0')+'"><title>'+tip+'</title></circle>');});});
    svg.innerHTML=parts.join('');
    document.getElementById('legend').innerHTML=filteredGroups.filter(group=>group.rows.length).map(group=>'<span class="swatch" style="background:'+group.color+'"></span><span>'+escapeHtml(group.name)+'</span>').join('');
    document.getElementById('axis-note').textContent=normalized?'Unidades distintas: cada serie se expresa como base 100 al inicio del intervalo.':(unitNames.values().next().value||'Valores originales');
  }

  function refreshViewStatus(message) {
    document.getElementById('load-status').textContent=message;
  }

  function plainName(value) { return String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es').replace(/[^a-z0-9]+/g,' ').trim(); }

  function selectGeneral(payload, aliases) {
    const rejected=['variacion','variaciones','tasa','porcentaje','media','promedio','acumulado'];
    const candidates=(payload||[]).map(item=>{
      const name=String(item.Nombre||'').trim(),plain=plainName(name),words=plain.split(/\s+/);
      if(!words.includes('indice')||rejected.some(word=>words.includes(word)))return null;
      const matchIndex=aliases.findIndex(alias=>plain.includes(plainName(alias)));
      if(matchIndex<0)return null;
      const score=100+(aliases.length-matchIndex)*100+(plain.endsWith('indice')?60:0)+(words.includes('nacional')||words.includes('espana')?40:0)-Math.floor(plain.length/100);
      return {item,name,score};
    }).filter(Boolean);
    const max=Math.max(-Infinity,...candidates.map(item=>item.score)),top=candidates.filter(item=>item.score===max);
    if(top.length!==1)throw new Error(top.length?'Selección ambigua de serie general del INE.':'No se encontró la serie general en la tabla del INE.');
    return top[0].item;
  }

  async function refreshIne() {
    const button=document.getElementById('refresh');button.disabled=true;button.textContent='Actualizando…';
    try {
      const retrievedAt=new Date().toISOString(),fresh=[];
      const retailResponse=await fetch('https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/75808?nult=12&tip=A',{cache:'no-store'});
      if(!retailResponse.ok)throw new Error('INE respondió HTTP '+retailResponse.status+' al consultar ventas minoristas.');
      const retailPayload=await retailResponse.json(),retailMatches=retailPayload.filter(series=>plainName(series.Nombre).includes(plainName(INE_NEEDLE)));
      if(retailMatches.length!==1)throw new Error('No se encontró una única serie de ventas minoristas; conserva los datos previos.');
      const specs=[{id:'75808',series:INE_ID,label:'Índice de ventas minoristas — Madrid',aliases:[],retail:true},...AUTOMATION_TABLES];
      for(const spec of specs){
        let series;
        if(spec.retail)series=retailMatches[0];
        else {const response=await fetch('https://servicios.ine.es/wstempus/js/es/DATOS_TABLA/'+spec.id+'?tip=AM',{cache:'no-store'});if(!response.ok)throw new Error('INE respondió HTTP '+response.status+' al consultar '+spec.id+'.');series=selectGeneral(await response.json(),spec.aliases);}
        (series.Data||[]).forEach(observation=>{
          if(observation.Fecha==null||observation.Valor==null)return;
          const time=typeof observation.Fecha==='number'?observation.Fecha:Number(observation.Fecha),date=new Date(Number.isFinite(time)?time:observation.Fecha);
          if(Number.isNaN(date.getTime()))return;
          fresh.push({series_id:spec.series,series_name:spec.label,source:'INE',period:spec.retail?date.toISOString().slice(0,10):date.toISOString().slice(0,7),value:String(observation.Valor),unit:'Índice (2021=100)',frequency:'M',retrieved_at:retrievedAt});
        });
      }
      if(!fresh.length)throw new Error('Las respuestas no contienen observaciones válidas.');
      const merged=new Map(currentRows.map(row=>[row.series_id+'|'+row.period,row]));fresh.forEach(row=>merged.set(row.series_id+'|'+row.period,row));currentRows=Array.from(merged.values()).sort((a,b)=>a.series_id.localeCompare(b.series_id)||a.period.localeCompare(b.period));
      updateCards();renderSeriesOptions(document.getElementById('indicator').value);renderSourceOptions();draw();refreshViewStatus('Vista actualizada desde el INE (ventas minoristas, IASS e IPI): '+new Date(retrievedAt).toLocaleString('es-ES')+'. Para guardar el histórico en GitHub se mantiene la acción diaria.');
    } catch(error) {refreshViewStatus('No se pudo completar la actualización del INE: '+error.message);}
    finally {button.disabled=false;button.textContent='Actualizar datos';}
  }

  function escapeCsv(value) {
    const text=String(value??'');
    return /[",\r\n]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text;
  }

  function downloadCsv() {
    const selectedSources=new Set(Array.from(document.querySelectorAll('#source-options input:checked')).map(input=>input.value));
    const groups=selectedGroups();
    const candidates=currentRows.filter(row=>selectedSources.has(row.source)&&groups.some(group=>group.rows.includes(row)));
    const bounds=dateBounds(candidates);
    const ordered=candidates.filter(row=>{const t=dateNumber(row.period);return t>=bounds.min&&t<=bounds.max;}).sort((a,b)=>a.series_id.localeCompare(b.series_id)||a.period.localeCompare(b.period));
    if(!ordered.length){refreshViewStatus('La selección actual no contiene filas para descargar.');return;}
    const csv='\uFEFF'+[CSV_FIELDS.join(','),...ordered.map(row=>CSV_FIELDS.map(field=>escapeCsv(row[field])).join(','))].join('\r\n');
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download='future_of_work_series.csv';document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
  }

  async function initialize() {
    try {
      const response=await fetch('./data/observations.csv',{cache:'no-store'});if(!response.ok)throw new Error('CSV HTTP '+response.status);
      currentRows=parseCsv(await response.text());
      if(!currentRows.some(row=>row.source==='INE'&&row.series_id===INE_ID))throw new Error('El CSV no contiene la serie INE esperada.');
      updateCards();renderSourceOptions();renderSeriesOptions(document.getElementById('indicator').value);draw();const retrieved=currentRows.map(row=>row.retrieved_at).filter(Boolean).sort().at(-1);
      refreshViewStatus('Datos del repositorio ('+currentRows.filter(row=>row.series_id.startsWith('IPC')||row.series_id.startsWith('ICM')).length+' observaciones IPC/ICM): '+(retrieved?new Date(retrieved).toLocaleString('es-ES'):'fecha no disponible')+'. Usa “Actualizar datos” para consultar el INE ahora.');
    } catch(error) {refreshViewStatus('No se pudieron cargar los datos: '+error.message);document.getElementById('chart').innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">Datos no disponibles.</text>';}
    document.getElementById('range').addEventListener('change',draw);
    document.getElementById('date-from').addEventListener('change',draw);
    document.getElementById('date-to').addEventListener('change',draw);
    document.getElementById('indicator').addEventListener('change',()=>{persistVisibleSeries();renderSeriesOptions(document.getElementById('indicator').value);draw();});
    const persistVisibleSeries=()=>{if(!activeSeriesMode)return;const selection=seriesSelectionByMode[activeSeriesMode]||new Set();document.querySelectorAll('#series-options input').forEach(input=>{if(input.checked)selection.add(input.value);else selection.delete(input.value);});seriesSelectionByMode[activeSeriesMode]=selection;};
    document.getElementById('series-options').addEventListener('change',()=>{persistVisibleSeries();renderSeriesOptions(document.getElementById('indicator').value);draw();});
    document.getElementById('series-search').addEventListener('input',()=>{persistVisibleSeries();renderSeriesOptions(document.getElementById('indicator').value);});
    document.getElementById('series-clear-search').addEventListener('click',()=>{persistVisibleSeries();document.getElementById('series-search').value='';renderSeriesOptions(document.getElementById('indicator').value);});
    document.getElementById('source-options').addEventListener('change',event=>{if(event.target.classList.contains('source-option')){if(event.target.checked)sourceSelection.add(event.target.value);else sourceSelection.delete(event.target.value);}});
    document.getElementById('series-all').addEventListener('click',()=>{const mode=document.getElementById('indicator').value,selection=seriesSelectionByMode[mode]||new Set();document.querySelectorAll('#series-options input').forEach(input=>selection.add(input.value));seriesSelectionByMode[mode]=selection;renderSeriesOptions(mode);draw();});
    document.getElementById('series-none').addEventListener('click',()=>{const mode=document.getElementById('indicator').value;seriesSelectionByMode[mode]=new Set();renderSeriesOptions(mode);draw();});
    document.getElementById('source-all').addEventListener('click',()=>{document.querySelectorAll('#source-options input').forEach(input=>input.checked=true);sourceSelection.clear();document.querySelectorAll('#source-options input').forEach(input=>sourceSelection.add(input.value));});
    document.getElementById('source-none').addEventListener('click',()=>{document.querySelectorAll('#source-options input').forEach(input=>input.checked=false);sourceSelection.clear();});
    const chart=document.getElementById('chart'),tooltip=document.getElementById('chart-tooltip');
    const showPointTip=(event)=>{const point=event.target.closest&&event.target.closest('.data-point');if(!point)return;tooltip.textContent=point.getAttribute('data-tip');tooltip.hidden=false;tooltip.style.left=Math.min(event.clientX+14,window.innerWidth-330)+'px';tooltip.style.top=Math.max(8,event.clientY-42)+'px';};
    chart.addEventListener('pointerover',showPointTip);chart.addEventListener('pointermove',showPointTip);
    chart.addEventListener('pointerout',event=>{if(event.target.closest&&event.target.closest('.data-point'))tooltip.hidden=true;});
    chart.addEventListener('focusin',event=>{const point=event.target.closest&&event.target.closest('.data-point');if(point){tooltip.textContent=point.getAttribute('data-tip');tooltip.hidden=false;const box=point.getBoundingClientRect();tooltip.style.left=Math.min(box.right+8,window.innerWidth-330)+'px';tooltip.style.top=Math.max(8,box.top-35)+'px';}});
    chart.addEventListener('focusout',()=>{tooltip.hidden=true;});
    document.getElementById('refresh').addEventListener('click',refreshIne);
    document.getElementById('download').addEventListener('click',downloadCsv);
  }
  initialize();
}());
