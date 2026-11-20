// Series Dashboard — Haver-style static series browser.
// Data: catalog.csv (one row per series, with concept/variant/measure) and
// observations.csv (long format). Both produced by pipeline/.
'use strict';

const MAX_SERIES = 8;
const COLORS = ['#0b2e6b', '#c0392b', '#1e8449', '#d68910', '#6c3483', '#2e86c1', '#7b7d7d', '#a04000'];
const GROUP_LABELS = {
  retail: 'Ventas minoristas', ipc: 'IPC · precios', icm: 'ICM · comercio minorista',
  iass: 'IASS · servicios', ipi: 'IPI · industria', eurostat: 'Eurostat · UE',
  manual: 'Excel manuales', other: 'Otros',
};
const MEASURE_LABELS = { level: 'Nivel', pct: '% m/m', yoy: '% a/a', ytd: '% acum. año' };
// Published versions of the same series (detected by pipeline/classify.py).
const ADJ_ORDER = ['nsa', 'cal', 'sa', 'trend'];
const ADJ_LABELS = { nsa: 'Original', cal: 'Corr. calendario', sa: 'Desestacionalizada', trend: 'Tendencia' };
const ADJ_SHORT = { nsa: 'Orig.', cal: 'Cal.', sa: 'Desest.', trend: 'Tend.' };
const TRANSFORM_LABELS = {
  level: 'Nivel', pct: '% periodo anterior', yoy: '% interanual', diff: 'Diferencia', rebase: 'Base 100',
};
const TRANSFORM_HINTS = {
  level: 'Valores tal como los publica la fuente.',
  pct: 'Variación (%) respecto al periodo anterior: mes anterior en series mensuales, trimestre anterior en trimestrales.',
  yoy: 'Variación (%) respecto al mismo periodo del año anterior.',
  diff: 'Diferencia absoluta respecto al periodo anterior, en las unidades de la serie.',
  rebase: 'Índice = 100 en la primera fecha visible (campo «Desde»), para comparar evoluciones.',
};

const state = {
  catalog: [], byId: new Map(), obs: new Map(),
  transform: 'level',    // how level series are shown (rates published by the source never change)
  adjPref: '',           // preferred published version: '' (all) | nsa | cal | sa | trend
  versions: new Map(),   // "group|base" -> series sorted by ADJ_ORDER (only when >1)
  selected: [],          // [{id, axis: 'y' | 'y2'}]
  open: new Set(),       // expanded tree nodes ("g:ipc", "c:ipc|Nacional. Índice general")
};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v) => (v == null || Number.isNaN(v) ? '—' : v.toLocaleString('es-ES', { maximumFractionDigits: 2 }));

// ---------- data ----------
// On Pages the workflow copies the CSVs into site/data/; locally (serving the
// repo root) they are read from data/processed/.
async function loadCsv(name) {
  for (const url of [`data/${name}`, `../data/processed/${name}`]) {
    const res = await fetch(url, { cache: 'no-cache' }).catch(() => null);
    if (res && res.ok) return Papa.parse(await res.text(), { header: true, skipEmptyLines: true }).data;
  }
  throw new Error(`No se encontró ${name}`);
}

// ---------- periods & transforms (mirror pipeline/transforms.py) ----------
function ordinal(p) {
  if (/^\d{4}-\d{2}$/.test(p)) return { f: 'M', n: +p.slice(0, 4) * 12 + (+p.slice(5) - 1) };
  if (/^\d{4}-Q[1-4]$/.test(p)) return { f: 'Q', n: +p.slice(0, 4) * 4 + (+p.slice(-1) - 1) };
  if (/^\d{4}$/.test(p)) return { f: 'A', n: +p };
  return { f: 'D', n: null };
}
function toDate(p) {
  if (/^\d{4}-\d{2}$/.test(p)) return `${p}-01`;
  if (/^\d{4}-Q[1-4]$/.test(p)) return `${p.slice(0, 4)}-${String((+p.slice(-1) - 1) * 3 + 1).padStart(2, '0')}-01`;
  if (/^\d{4}$/.test(p)) return `${p}-01-01`;
  return p;
}
function transform(points, kind, fromMonth) {
  if (kind === 'level') return points;
  if (kind === 'pct' || kind === 'diff') {
    return points.map(([p, v], i) => {
      const prev = i ? points[i - 1][1] : null;
      if (prev == null || v == null || (kind === 'pct' && prev === 0)) return [p, null];
      return [p, kind === 'pct' ? (v / prev - 1) * 100 : v - prev];
    });
  }
  if (kind === 'yoy') {
    const lag = { M: 12, Q: 4, A: 1 };
    const byOrd = new Map(points.map(([p, v]) => [ordinal(p).n, v]));
    return points.map(([p, v]) => {
      const o = ordinal(p);
      const base = lag[o.f] ? byOrd.get(o.n - lag[o.f]) : null;
      return [p, base == null || base === 0 || v == null ? null : (v / base - 1) * 100];
    });
  }
  if (kind === 'rebase') {
    const start = fromMonth ? toDate(fromMonth) : '';
    const base = points.find(([p, v]) => toDate(p) >= start && v != null);
    return points.map(([p, v]) => [p, !base || base[1] === 0 || v == null ? null : (v / base[1]) * 100]);
  }
  return points;
}
// Series that the source already publishes as a rate are never re-transformed.
const effectiveKind = (s) => (s.measure === 'level' ? state.transform : 'level');
const shownAs = (s) => (s.measure === 'level' ? TRANSFORM_LABELS[state.transform] : `${MEASURE_LABELS[s.measure]} (origen)`);

// ---------- seasonal-adjustment versions ----------
const versionsOf = (s) => (s ? state.versions.get(`${s.group}|${s.base}`) || [] : []);
function indexVersions(catalog) {
  const fam = new Map();
  for (const s of catalog) {
    if (!s.base) continue;
    const k = `${s.group}|${s.base}`;
    if (!fam.has(k)) fam.set(k, []);
    fam.get(k).push(s);
  }
  for (const [k, list] of fam) {
    // Only a family where each adjustment appears once is unambiguous.
    if (list.length > 1 && new Set(list.map((s) => s.adjustment)).size === list.length) {
      state.versions.set(k, list.sort((a, b) => ADJ_ORDER.indexOf(a.adjustment) - ADJ_ORDER.indexOf(b.adjustment)));
    }
  }
}
// Replace a selected series by another version of it, keeping its axis and colour slot.
function swapVersion(fromId, toId) {
  if (fromId === toId || state.selected.some((x) => x.id === toId)) return false;
  const sel = state.selected.find((x) => x.id === fromId);
  if (!sel) return false;
  sel.id = toId;
  return true;
}
function setAdjustment(adj) {
  state.adjPref = adj;
  if (!adj) { update(); return setStatus('Ajuste: se muestran todas las versiones publicadas'); }
  let changed = 0, missing = 0;
  for (const sel of [...state.selected]) {
    const vs = versionsOf(state.byId.get(sel.id));
    if (!vs.length) { if (state.byId.get(sel.id).adjustment !== adj) missing++; continue; }
    const target = vs.find((v) => v.adjustment === adj);
    if (!target) { missing++; continue; }
    if (swapVersion(sel.id, target.series_id)) changed++;
  }
  update();
  setStatus(`${ADJ_LABELS[adj]}: ${changed} serie(s) cambiada(s)` + (missing ? ` · ${missing} sin esa versión publicada` : ''));
}
function adjCell(s) {
  const vs = versionsOf(s);
  if (!vs.length) {
    if (state.adjPref && s.adjustment !== state.adjPref) {
      return `<span class="warn" title="La fuente no publica esta serie en versión ${esc(ADJ_LABELS[state.adjPref].toLowerCase())}">${ADJ_SHORT[s.adjustment]} · sin ${ADJ_SHORT[state.adjPref].toLowerCase()}</span>`;
    }
    return `<span class="muted">${s.adjustment !== 'nsa' ? ADJ_SHORT[s.adjustment] : '—'}</span>`;
  }
  return `<span class="seg">${vs.map((v) => `<button type="button" class="${v.series_id === s.series_id ? 'on' : ''}"
    data-swap="${esc(s.series_id)}" data-to="${esc(v.series_id)}"
    title="${esc(ADJ_LABELS[v.adjustment])} · ${esc(v.series_id)}">${ADJ_SHORT[v.adjustment]}</button>`).join('')}</span>`;
}
function renderViewBar() {
  for (const b of $('transform-seg').querySelectorAll('button')) b.classList.toggle('on', b.dataset.t === state.transform);
  for (const b of $('adjust-seg').querySelectorAll('button')) b.classList.toggle('on', b.dataset.adj === state.adjPref);
  const hints = [TRANSFORM_HINTS[state.transform]];
  const rates = state.selected.filter((x) => state.byId.get(x.id).measure !== 'level').length;
  if (rates && state.transform !== 'level') hints.push(`${rates} serie(s) ya publicada(s) como tasa se muestran sin transformar.`);
  if (state.adjPref) {
    const without = state.selected.filter((x) => state.byId.get(x.id).adjustment !== state.adjPref).length;
    hints.push(`Catálogo filtrado a la versión ${ADJ_LABELS[state.adjPref].toLowerCase()} cuando existe`
      + (without ? `; ${without} serie(s) seleccionada(s) no la tienen.` : '.'));
  }
  $('view-hint').textContent = hints.join(' ');
}

// ---------- tree: group → concept → series ----------
function buildTree(rows) {
  const groups = new Map();
  for (const s of rows) {
    if (!groups.has(s.group)) groups.set(s.group, new Map());
    const concepts = groups.get(s.group);
    if (!concepts.has(s.concept)) concepts.set(s.concept, []);
    concepts.get(s.concept).push(s);
  }
  return groups;
}

function leafHtml(s, sel) {
  const on = sel.has(s.series_id);
  const tag = (s.measure === 'level' ? '' : `<span class="tag tx" title="La fuente ya publica esta serie transformada">${MEASURE_LABELS[s.measure]}</span>`)
    + (versionsOf(s).length || s.adjustment !== 'nsa' ? `<span class="tag adj" title="${esc(ADJ_LABELS[s.adjustment])}">${ADJ_SHORT[s.adjustment]}</span>` : '');
  return `<div class="node leaf ${on ? 'on' : ''}" data-id="${esc(s.series_id)}" role="treeitem" aria-selected="${on}"
      title="${esc(s.series_name)} · ${esc(s.source)} · ${s.first_period}–${s.last_period}">
    <input type="checkbox" tabindex="-1" ${on ? 'checked' : ''}>
    <span class="code">${esc(s.series_id)}</span>
    <span class="lbl">${esc(s.variant || s.series_name)}</span><span class="tags">${tag}</span></div>`;
}

function renderTree() {
  const terms = $('search').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let rows = state.catalog.filter((s) =>
    terms.every((t) => `${s.series_id} ${s.series_name} ${s.source} ${GROUP_LABELS[s.group] || s.group} ${ADJ_LABELS[s.adjustment]}`.toLowerCase().includes(t)));
  if (state.adjPref) { // one version per family: the preferred one when it exists
    for (let i = rows.length - 1; i >= 0; i--) {
      const vs = versionsOf(rows[i]);
      if (vs.length && rows[i].adjustment !== state.adjPref && vs.some((v) => v.adjustment === state.adjPref)) rows.splice(i, 1);
    }
  }
  const searching = terms.length > 0;
  const sel = new Set(state.selected.map((s) => s.id));
  let html = '';
  for (const [group, concepts] of buildTree(rows)) {
    const gKey = `g:${group}`, gOpen = searching || state.open.has(gKey);
    const n = [...concepts.values()].reduce((a, l) => a + l.length, 0);
    html += `<div class="node lvl0" data-toggle="${esc(gKey)}"><span class="tw">${gOpen ? '▾' : '▸'}</span>${esc(GROUP_LABELS[group] || group)}<span class="count">(${n})</span></div>`;
    if (!gOpen) continue;
    for (const [concept, list] of concepts) {
      if (list.length === 1 && !list[0].variant) { // lone series: no folder needed
        html += leafHtml(list[0], sel).replace('node leaf', 'node leaf lvl1');
        continue;
      }
      const cKey = `c:${group}|${concept}`, cOpen = searching || state.open.has(cKey);
      html += `<div class="node lvl1" data-toggle="${esc(cKey)}" title="${esc(concept)}"><span class="tw">${cOpen ? '▾' : '▸'}</span>${esc(concept)}<span class="count">(${list.length})</span></div>`;
      if (cOpen) html += list.map((s) => leafHtml(s, sel)).join('');
    }
  }
  $('tree').innerHTML = html || '<div class="node">Sin resultados</div>';
  $('catalog-count').textContent = `${rows.length} de ${state.catalog.length} series · ${new Set(rows.map((s) => s.group + s.concept)).size} conceptos`;
}

function toggleSeries(id) {
  const i = state.selected.findIndex((s) => s.id === id);
  if (i >= 0) state.selected.splice(i, 1);
  else if (state.selected.length < MAX_SERIES) state.selected.push({ id, axis: 'y' });
  else return setStatus(`Máximo ${MAX_SERIES} series a la vez.`);
  update();
}

// ---------- selected grid + chart ----------
function visibleData() {
  const from = $('from').value, to = $('to').value;
  return state.selected.map((sel, i) => {
    const s = state.byId.get(sel.id);
    const pts = transform(state.obs.get(sel.id) || [], effectiveKind(s), from)
      .filter(([p]) => (!from || toDate(p) >= `${from}-01`) && (!to || toDate(p) <= `${to}-31`));
    return { ...sel, s, color: COLORS[i % COLORS.length], pts };
  });
}

function renderSelected(data) {
  $('empty').hidden = data.length > 0;
  $('selected').hidden = data.length === 0;
  $('selected').querySelector('tbody').innerHTML = data.map((d) => `
    <tr>
      <td><span class="swatch" style="background:${d.color}"></span></td>
      <td class="code">${esc(d.id)}</td>
      <td class="desc">${esc(d.s.concept)}${d.s.variant ? ` <span style="color:var(--muted)">· ${esc(d.s.variant)}</span>` : ''}</td>
      <td>${d.s.frequency}</td><td>${d.s.first_period}</td><td>${d.s.last_period}</td>
      <td class="num">${fmt(+d.s.last_value)}</td>
      <td>${MEASURE_LABELS[d.s.measure] || '—'}</td>
      <td>${adjCell(d.s)}</td>
      <td>${esc(shownAs(d.s))}</td>
      <td><button type="button" data-axis="${esc(d.id)}">${d.axis === 'y' ? 'Izq.' : 'Der.'}</button></td>
      <td><button type="button" data-remove="${esc(d.id)}" aria-label="Quitar">✕</button></td>
    </tr>`).join('');
}

function axisTitle(data, axis) {
  const labels = [...new Set(data.filter((d) => d.axis === axis).map((d) =>
    (d.s.measure === 'level' && effectiveKind(d.s) === 'level' ? d.s.unit : shownAs(d.s).replace(' (origen)', '')) || ''))];
  return labels.length === 1 ? labels[0] : '';
}

function renderChart(data) {
  const one = data.length === 1 ? data[0].s : null;
  $('chart-title').textContent = !data.length ? '' : one ? `${one.concept}${one.variant ? ' · ' + one.variant : ''}` : `${data.length} series`;
  $('chart-sub').textContent = data.length ? [axisTitle(data, 'y'), axisTitle(data, 'y2')].filter(Boolean).join('  |  eje dcho.: ') : '';
  const sources = [...new Set(data.map((d) => d.s.source.replace(/^Excel:.*/, 'Excel manual')))];
  $('chart-source').textContent = data.length ? `Fuente: ${sources.join(', ')}` : '';

  const axisStyle = { showline: true, linecolor: '#111', ticks: 'outside', tickcolor: '#111', mirror: false, zeroline: false };
  const traces = data.map((d) => ({
    x: d.pts.map(([p]) => toDate(p)), y: d.pts.map(([, v]) => (v == null ? null : +v)),
    name: `${d.id}${d.axis === 'y2' ? ' (dcha.)' : ''}`, yaxis: d.axis, type: 'scatter', mode: 'lines',
    line: { color: d.color, width: 1.8 },
    hovertemplate: `%{x|%Y-%m}  %{y:,.2f}<extra>${esc(d.id)}</extra>`,
  }));
  const hasRight = data.some((d) => d.axis === 'y2');
  const anyRate = data.some((d) => d.s.measure !== 'level' || effectiveKind(d.s) !== 'level');
  Plotly.react('chart', traces, {
    margin: { l: 55, r: hasRight ? 55 : 15, t: 10, b: 30 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fff', font: { family: 'Segoe UI, Arial, sans-serif', color: '#111', size: 11 },
    showlegend: data.length > 1, legend: { orientation: 'h', x: 0, y: 1.08 }, hovermode: 'x unified',
    xaxis: { ...axisStyle, type: 'date', showgrid: false },
    yaxis: { ...axisStyle, showgrid: true, gridcolor: '#eceef1', zeroline: anyRate, zerolinecolor: '#888' },
    yaxis2: { ...axisStyle, overlaying: 'y', side: 'right', showgrid: false, visible: hasRight },
  }, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] });
}

function update() {
  const data = visibleData();
  renderSelected(data);
  renderChart(data);
  renderViewBar();
  renderTree();
  const params = new URLSearchParams(); // shareable view: #s=ID1,ID2:r&t=yoy&from=2020-01
  if (state.selected.length) params.set('s', state.selected.map((s) => s.id + (s.axis === 'y2' ? ':r' : '')).join(','));
  if (state.transform !== 'level') params.set('t', state.transform);
  if (state.adjPref) params.set('adj', state.adjPref);
  if ($('from').value) params.set('from', $('from').value);
  if ($('to').value) params.set('to', $('to').value);
  history.replaceState(null, '', params.toString() ? `#${params}` : location.pathname);
}

// ---------- export (wide table of what is plotted) ----------
function wideTable() {
  const data = visibleData();
  const periods = [...new Set(data.flatMap((d) => d.pts.map(([p]) => p)))].sort();
  const maps = data.map((d) => new Map(d.pts));
  return [
    ['period', ...data.map((d) => d.id)],
    ['descripcion', ...data.map((d) => `${d.s.concept}${d.s.variant ? ' · ' + d.s.variant : ''}`)],
    ['mostrado_como', ...data.map((d) => (effectiveKind(d.s) === 'level' && d.s.measure === 'level' ? d.s.unit : shownAs(d.s)))],
    ['fuente', ...data.map((d) => d.s.source)],
    ...periods.map((p) => [p, ...maps.map((m) => (m.get(p) == null ? '' : +m.get(p)))]),
  ];
}
function download(type) {
  if (!state.selected.length) return setStatus('No hay series seleccionadas.');
  const rows = wideTable(), stamp = new Date().toISOString().slice(0, 10);
  if (type === 'csv') {
    const blob = new Blob(['﻿' + Papa.unparse(rows)], { type: 'text/csv;charset=utf-8' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `series_${stamp}.csv` });
    a.click(); URL.revokeObjectURL(a.href);
  } else {
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), 'datos');
    XLSX.writeFile(wb, `series_${stamp}.xlsx`);
  }
}
function setStatus(text) { $('status').textContent = text; }

// ---------- init ----------
function restoreFromHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  state.selected = (params.get('s') || '').split(',').filter(Boolean)
    .map((t) => { const [id, ax] = t.split(':'); return { id, axis: ax === 'r' ? 'y2' : 'y' }; })
    .filter((s) => state.byId.has(s.id)).slice(0, MAX_SERIES);
  if (TRANSFORM_LABELS[params.get('t')]) state.transform = params.get('t');
  if (ADJ_LABELS[params.get('adj')]) state.adjPref = params.get('adj');
  $('from').value = params.get('from') || '';
  $('to').value = params.get('to') || '';
  if (!state.selected.length) { // default view: unemployment Spain vs euro area
    state.selected = ['EUR_UNE_RT_M_ES', 'EUR_UNE_RT_M_EA'].filter((id) => state.byId.has(id)).map((id) => ({ id, axis: 'y' }));
    if (!$('from').value) $('from').value = '2015-01';
  }
  for (const s of state.selected) { // expand the tree where the selection lives
    const c = state.byId.get(s.id);
    state.open.add(`g:${c.group}`); state.open.add(`c:${c.group}|${c.concept}`);
  }
}

async function init() {
  try {
    if (typeof Plotly === 'undefined') throw new Error('no se pudo cargar la librería de gráficos (Plotly)');
    const [catalog, obs] = await Promise.all([loadCsv('catalog.csv'), loadCsv('observations.csv')]);
    for (const s of catalog) {
      s.concept ||= s.series_name; s.measure ||= 'level'; s.variant ||= '';
      s.adjustment ||= 'nsa'; s.base ||= '';
    }
    state.catalog = catalog;
    indexVersions(catalog);
    state.byId = new Map(catalog.map((s) => [s.series_id, s]));
    for (const r of obs) {
      if (!state.obs.has(r.series_id)) state.obs.set(r.series_id, []);
      state.obs.get(r.series_id).push([r.period, r.value === '' ? null : +r.value]);
    }
    for (const pts of state.obs.values()) pts.sort((a, b) => (a[0] < b[0] ? -1 : 1));
    const latest = catalog.map((s) => s.retrieved_at).sort().pop() || '';
    setStatus(`${catalog.length} series · datos actualizados ${latest.slice(0, 10)}`);
    restoreFromHash();
    update();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

$('search').addEventListener('input', renderTree);
$('tree').addEventListener('click', (e) => {
  const node = e.target.closest('[data-toggle], [data-id]');
  if (!node) return;
  if (node.dataset.id) return toggleSeries(node.dataset.id);
  const key = node.dataset.toggle;
  state.open.has(key) ? state.open.delete(key) : state.open.add(key);
  renderTree();
});
$('selected').addEventListener('click', (e) => {
  const { axis, remove, swap, to } = e.target.dataset;
  if (swap) {
    if (swap !== to && !swapVersion(swap, to)) setStatus('Esa versión ya está seleccionada.');
    return update();
  }
  if (axis) { const s = state.selected.find((x) => x.id === axis); s.axis = s.axis === 'y' ? 'y2' : 'y'; update(); }
  if (remove) toggleSeries(remove);
});
['from', 'to'].forEach((id) => $(id).addEventListener('change', update));
$('dl-csv').addEventListener('click', () => download('csv'));
$('dl-xlsx').addEventListener('click', () => download('xlsx'));
$('transform-seg').addEventListener('click', (e) => { if (e.target.dataset.t) { state.transform = e.target.dataset.t; update(); } });
$('adjust-seg').addEventListener('click', (e) => { if (e.target.dataset.adj != null) setAdjustment(e.target.dataset.adj); });
$('clear').addEventListener('click', () => { state.selected = []; update(); });
init();
