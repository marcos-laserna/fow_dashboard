(function () {
  'use strict';

  const INE_ID = 'ine_retail_sales_madrid';
  const INE_NEEDLE = 'Madrid, Comunidad de. Cifra de negocio a precios constantes. Comercio al por menor, excepto de vehículos de motor y motocicletas. General. Índice';
  const CSV_FIELDS = ['series_id','series_name','source','period','value','unit','frequency','retrieved_at'];
  let currentRows = [];
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

  function draw() {
    const svg=document.getElementById('chart'),w=1000,h=360,p={l:72,r:22,t:18,b:45};
    const ine=currentRows.filter(r=>r.source==='INE'&&r.series_id===INE_ID);
    const manual=currentRows.filter(r=>r.source.startsWith('Excel:'));
    const groups=[{name:'INE · Madrid',rows:ine,color:'#2463eb'}];
    const manualGroups=new Map();
    manual.forEach(row=>{const key=row.series_name||'Serie Excel';if(!manualGroups.has(key))manualGroups.set(key,[]);manualGroups.get(key).push(row);});
    Array.from(manualGroups.entries()).forEach((entry,index)=>groups.push({name:entry[0],rows:entry[1],color:index===0?'#0c9488':'#d97706'}));
    const all=groups.flatMap(group=>group.rows.map(row=>({row,time:dateNumber(row.period),value:Number(row.value)}))).filter(item=>Number.isFinite(item.time)&&Number.isFinite(item.value));
    if(!all.length){svg.innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">No hay observaciones para mostrar.</text>';return;}
    const times=all.map(item=>item.time),latestTime=Math.max(...times),choice=document.getElementById('range').value;
    const filteredGroups=groups.map(group=>({...group,rows:group.rows.filter(row=>{const t=dateNumber(row.period);if(choice==='all')return true;const start=new Date(latestTime);start.setUTCMonth(start.getUTCMonth()-Number(choice));return t>=start.getTime()&&t<=latestTime;}).sort((a,b)=>dateNumber(a.period)-dateNumber(b.period))}));
    const available=filteredGroups.flatMap(group=>group.rows.map(row=>({row,time:dateNumber(row.period),value:Number(row.value),group}))).filter(item=>Number.isFinite(item.time)&&Number.isFinite(item.value));
    if(!available.length){svg.innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">No hay observaciones en este intervalo.</text>';return;}
    const unitNames=new Set(available.map(item=>item.row.unit).filter(Boolean)),normalized=unitNames.size>1||available.some(item=>!item.row.unit);
    const baselineTime=normalized?Math.max(...filteredGroups.filter(group=>group.rows.length).map(group=>Math.min(...group.rows.map(row=>dateNumber(row.period))))):null;
    const baselines=new Map();
    if(normalized){filteredGroups.forEach(group=>{const base=group.rows.find(row=>dateNumber(row.period)>=baselineTime&&Number(row.value)!==0);if(base)baselines.set(group.name,Number(base.value));});available.forEach(item=>{const base=baselines.get(item.group.name);item.plotValue=base?item.value/base*100:item.value;});}
    else available.forEach(item=>item.plotValue=item.value);
    const values=available.map(item=>item.plotValue),low=Math.min(...values),high=Math.max(...values),padding=(high-low||1)*.12,min=low-padding,max=high+padding;
    const minTime=Math.min(...available.map(item=>item.time)),maxTime=Math.max(...available.map(item=>item.time));
    const x=t=>p.l+(t-minTime)*(w-p.l-p.r)/(maxTime-minTime||1),y=v=>h-p.b-(v-min)*(h-p.t-p.b)/(max-min||1),parts=[];
    for(let i=0;i<5;i++){const value=min+(max-min)*i/4,yy=y(value);parts.push('<line x1="'+p.l+'" y1="'+yy+'" x2="'+(w-p.r)+'" y2="'+yy+'" stroke="#e9edf2"/><text x="'+(p.l-10)+'" y="'+(yy+4)+'" text-anchor="end" fill="#718198" font-size="12">'+fmt(value)+'</text>');}
    for(let i=0;i<6;i++){const tickTime=minTime+(maxTime-minTime)*i/5;parts.push('<text x="'+x(tickTime)+'" y="'+(h-12)+'" text-anchor="middle" fill="#718198" font-size="12">'+new Date(tickTime).toISOString().slice(0,7)+'</text>');}
    filteredGroups.forEach(group=>{const rows=group.rows.filter(row=>Number.isFinite(dateNumber(row.period))&&Number.isFinite(Number(row.value)));if(!rows.length)return;const base=baselines.get(group.name),safeName=escapeHtml(group.name);const points=rows.map(row=>{const value=Number(row.value),plot=normalized&&base?value/base*100:value;return x(dateNumber(row.period))+','+y(plot);}).join(' ');parts.push('<polyline points="'+points+'" fill="none" stroke="'+group.color+'" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>');const stride=Math.max(1,Math.floor(rows.length/25));rows.forEach((row,index)=>{if(index%stride===0||index===rows.length-1){const value=Number(row.value),plot=normalized&&base?value/base*100:value;parts.push('<circle cx="'+x(dateNumber(row.period))+'" cy="'+y(plot)+'" r="3.5" fill="'+group.color+'"><title>'+safeName+' · '+displayDate(row.period)+': '+fmt(value)+'</title></circle>');}});});
    svg.innerHTML=parts.join('');
    document.getElementById('legend').innerHTML=filteredGroups.filter(group=>group.rows.length).map(group=>'<span class="swatch" style="background:'+group.color+'"></span><span>'+escapeHtml(group.name)+'</span>').join('');
    document.getElementById('axis-note').textContent=normalized?'Unidades distintas: cada serie se expresa como base 100 al inicio del intervalo.':(unitNames.values().next().value||'Valores originales');
  }

  function refreshViewStatus(message) {
    document.getElementById('load-status').textContent=message;
  }

  async function refreshIne() {
    const button=document.getElementById('refresh');button.disabled=true;button.textContent='Actualizando…';
    try {
      const url='https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/75808?nult=12&tip=A';
      const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('INE respondió HTTP '+response.status);
      const payload=await response.json(),matches=payload.filter(series=>String(series.Nombre||'').trim().toLocaleLowerCase('es').includes(INE_NEEDLE.toLocaleLowerCase('es')));
      if(matches.length!==1)throw new Error('No se encontró una única serie INE; se conserva la vista anterior.');
      const retrievedAt=new Date().toISOString(),series=matches[0],fresh=[];
      (series.Data||[]).forEach(observation=>{if(observation.Fecha==null||observation.Valor==null)return;const date=new Date(observation.Fecha);if(Number.isNaN(date.getTime()))return;fresh.push({series_id:INE_ID,series_name:'Índice de ventas minoristas — Madrid',source:'INE',period:date.toISOString().slice(0,10),value:String(observation.Valor),unit:'Índice (2021=100)',frequency:'M',retrieved_at:retrievedAt});});
      if(!fresh.length)throw new Error('La respuesta no contiene observaciones válidas.');
      const merged=new Map(currentRows.map(row=>[row.series_id+'|'+row.period,row]));fresh.forEach(row=>merged.set(row.series_id+'|'+row.period,row));currentRows=Array.from(merged.values()).sort((a,b)=>a.series_id.localeCompare(b.series_id)||a.period.localeCompare(b.period));
      updateCards();draw();refreshViewStatus('Vista actualizada directamente desde la API del INE: '+new Date(retrievedAt).toLocaleString('es-ES')+'. Para guardar el histórico en GitHub se mantiene la acción diaria.');
    } catch(error) {refreshViewStatus('No se pudo actualizar desde el INE: '+error.message);}
    finally {button.disabled=false;button.textContent='Actualizar datos';}
  }

  function escapeCsv(value) {
    const text=String(value??'');
    return /[",\r\n]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text;
  }

  function downloadCsv() {
    const ordered=currentRows.slice().sort((a,b)=>a.series_id.localeCompare(b.series_id)||a.period.localeCompare(b.period));
    const csv='\uFEFF'+[CSV_FIELDS.join(','),...ordered.map(row=>CSV_FIELDS.map(field=>escapeCsv(row[field])).join(','))].join('\r\n');
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download='future_of_work_series.csv';document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
  }

  async function initialize() {
    try {
      const response=await fetch('./data/observations.csv',{cache:'no-store'});if(!response.ok)throw new Error('CSV HTTP '+response.status);
      currentRows=parseCsv(await response.text());
      if(!currentRows.some(row=>row.source==='INE'&&row.series_id===INE_ID))throw new Error('El CSV no contiene la serie INE esperada.');
      updateCards();draw();const retrieved=currentRows.map(row=>row.retrieved_at).filter(Boolean).sort().at(-1);
      refreshViewStatus('Datos del repositorio: '+(retrieved?new Date(retrieved).toLocaleString('es-ES'):'fecha no disponible')+'. Usa “Actualizar datos” para consultar el INE ahora.');
    } catch(error) {refreshViewStatus('No se pudieron cargar los datos: '+error.message);document.getElementById('chart').innerHTML='<text x="500" y="180" text-anchor="middle" class="empty">Datos no disponibles.</text>';}
    document.getElementById('range').addEventListener('change',draw);
    document.getElementById('refresh').addEventListener('click',refreshIne);
    document.getElementById('download').addEventListener('click',downloadCsv);
  }
  initialize();
}());
