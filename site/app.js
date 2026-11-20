// Series Dashboard — Haver-style static series browser.
// Data: catalog.csv (one row per series, with concept/variant/measure/adjustment/
// base/stem) and observations.csv (long format). Both produced by pipeline/.
'use strict';

const MAX_SERIES = 8;
const COLORS = ['#0b2e6b', '#c0392b', '#1e8449', '#d68910', '#6c3483', '#2e86c1', '#7b7d7d', '#a04000'];
const GROUP_LABELS = {
  retail: 'Ventas minoristas', ipc: 'IPC · precios', icm: 'ICM · comercio minorista',
  iass: 'IASS · servicios', ipi: 'IPI · industria', eurostat: 'Eurostat · UE',
  manual: 'Excel manuales', other: 'Otros',
};
const MEASURE_LABELS = { level: 'Nivel', pct: '% m/m', yoy: '% a/a', ytd: '% acum. año' };
const RATE_SHORT = { pct: 'm/m', yoy: 'a/a', ytd: 'acum.' };
// Published versions of the same series (detected by pipeline/classify.py).
const ADJ_ORDER = ['nsa', 'cal', 'sa', 'trend'];
const ADJ_LABELS = { nsa: 'Original', cal: 'Corr. calendario', sa: 'Desestacionalizada', trend: 'Tendencia' };
const ADJ_SHORT = { nsa: 'Orig.', cal: 'Cal.', sa: 'Desest.', trend: 'Tend.' };
// Transformations; several can be shown at once. pct/yoy/ytd use the rate the
// source publishes when there is one ("oficial"); ytd is never computed.
const TRANSFORMS = ['level', 'pct', 'yoy', 'ytd', 'diff', 'rebase'];
const TRANSFORM_LABELS = {
  level: 'Nivel', pct: '% periodo anterior', yoy: '% interanual', ytd: '% acum. año', diff: 'Diferencia', rebase: 'Base 100',
};
const TRANSFORM_SHORT = { level: 'nivel', pct: '% m/m', yoy: '% a/a', ytd: '% acum.', diff: 'dif.', rebase: 'base 100' };
const TRANSFORM_HINTS = {
  level: 'Nivel: valores tal como los publica la fuente.',
  pct: '% periodo anterior: variación respecto al mes (o trimestre) anterior.',
  yoy: '% interanual: variación respecto al mismo periodo del año anterior.',
  ytd: '% acum. año: solo cuando la fuente la publica.',
  diff: 'Diferencia: cambio absoluto respecto al periodo anterior.',
  rebase: 'Base 100: índice = 100 en la primera fecha visible.',
};
const DASH = { level: 'solid', pct: 'dot', yoy: 'dash', ytd: 'dashdot', diff: 'longdash', rebase: 'longdashdot' };
// Levels and changes on different axes, so rates are not squashed near zero.
const CHANGE_KINDS = new Set(['pct', 'yoy', 'ytd', 'diff']);
const AXIS_LABELS = { auto: 'Auto', y: 'Izq.', y2: 'Dcha.' };
const AXIS_NEXT = { auto: 'y', y: 'y2', y2: 'auto' };

const state = {
  catalog: [], byId: new Map(), obs: new Map(),
  transforms: ['level'], // shown at once, in TRANSFORMS order
  adjPref: '',           // preferred published version: '' (all) | nsa | cal | sa | trend
  dualAxis: true,        // automatic second axis
  versions: new Map(),   // "group|base" -> series sorted by ADJ_ORDER (only when >1)
  rates: new Map(),      // "group|stem|adjustment" -> {level, pct, yoy, ytd} published siblings
  selected: [],          // [{id, axis: 'auto' | 'y' | 'y2'}]
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

// ---------- families ----------
const versionsOf = (s) => (s ? state.versions.get(`${s.group}|${s.base}`) || [] : []);
const ratesOf = (s) => (s ? state.rates.get(`${s.group}|${s.stem}|${s.adjustment}`) || {} : {});
// A published rate whose index is also published is reached through the index.
const parentOf = (s) => (s && s.measure !== 'level' && ratesOf(s).level) || s;
const isListed = (s) => parentOf(s) === s;

function indexFamilies(catalog) {
  const fam = new Map();
  for (const s of catalog) {
    if (s.base) {
      const k = `${s.group}|${s.base}`;
      if (!fam.has(k)) fam.set(k, []);
      fam.get(k).push(s);
    }
    const r = `${s.group}|${s.stem}|${s.adjustment}`;
    if (!state.rates.has(r)) state.rates.set(r, {});
    const slot = state.rates.get(r);
    if (!slot[s.measure]) slot[s.measure] = s;
  }
  for (const [k, list] of fam) {
    // Only a family where each adjustment appears once is unambiguous.
    if (list.length > 1 && new Set(list.map((s) => s.adjustment)).size === list.length) {
      state.versions.set(k, list.sort((a, b) => ADJ_ORDER.indexOf(a.adjustment) - ADJ_ORDER.indexOf(b.adjustment)));
    }
  }
}
function publishedRatesLabel(s) {
  const r = ratesOf(s);
  return ['pct', 'yoy', 'ytd'].filter((m) => r[m] && r[m] !== s).map((m) => RATE_SHORT[m]).join(' · ');
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

function leafHtml(s, sel, label) {
  const on = sel.has(s.series_id);
  const rates = publishedRatesLabel(s);
  const tag = (s.measure === 'level' ? '' : `<span class="tag tx" title="La fuente publica esta serie ya transformada">${MEASURE_LABELS[s.measure]}</span>`)
    + (rates ? `<span class="tag rt" title="Tasas oficiales publicadas: ${esc(rates)}. Se eligen en «Mostrar como».">+ tasas</span>` : '')
    + (versionsOf(s).length || s.adjustment !== 'nsa' ? `<span class="tag adj" title="${esc(ADJ_LABELS[s.adjustment])}">${ADJ_SHORT[s.adjustment]}</span>` : '');
  return `<div class="node leaf ${on ? 'on' : ''}" data-id="${esc(s.series_id)}" role="treeitem" aria-selected="${on}"
      title="${esc(s.series_name)} · ${esc(s.source)} · ${s.first_period}–${s.last_period}">
    <input type="checkbox" tabindex="-1" ${on ? 'checked' : ''}>
    <span class="code">${esc(s.series_id)}</span>
    <span class="lbl">${esc(label || s.variant || s.series_name)}</span><span class="tags">${tag}</span></div>`;
}

function renderTree() {
  const terms = $('search').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const rows = state.catalog.filter((s) => isListed(s)
    && terms.every((t) => `${s.series_id} ${s.series_name} ${s.source} ${GROUP_LABELS[s.group] || s.group} ${ADJ_LABELS[s.adjustment]}`.toLowerCase().includes(t)));
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
      if (list.length === 1) { // lone series: no folder needed
        const s = list[0];
        const label = s.measure === 'level' && /^[íi]ndice$/i.test(s.variant) ? concept
          : s.variant ? `${concept} · ${s.variant}` : concept;
        html += leafHtml(s, sel, label).replace('node leaf', 'node leaf lvl1');
        continue;
      }
      const cKey = `c:${group}|${concept}`, cOpen = searching || state.open.has(cKey);
      html += `<div class="node lvl1" data-toggle="${esc(cKey)}" title="${esc(concept)}"><span class="tw">${cOpen ? '▾' : '▸'}</span>${esc(concept)}<span class="count">(${list.length})</span></div>`;
      if (cOpen) html += list.map((s) => leafHtml(s, sel)).join('');
    }
  }
  $('tree').innerHTML = html || '<div class="node">Sin resultados</div>';
  const listed = state.catalog.filter(isListed).length;
  $('catalog-count').textContent = `${rows.length} de ${listed} series · las tasas oficiales (${state.catalog.length - listed}) se eligen en «Mostrar como»`;
}

function toggleSeries(id) {
  const i = state.selected.findIndex((s) => s.id === id);
  if (i >= 0) state.selected.splice(i, 1);
  else if (state.selected.length < MAX_SERIES) state.selected.push({ id, axis: 'auto' });
  else return setStatus(`Máximo ${MAX_SERIES} series a la vez.`);
  update();
}

// ---------- traces: one per (series, transformation) ----------
// origin: 'pub' (as published), 'oficial' (rate published by the source) or 'calc'.
function seriesTraces(sel, i, from, to) {
  const s = state.byId.get(sel.id);
  const color = COLORS[i % COLORS.length];
  const inRange = ([p]) => (!from || toDate(p) >= `${from}-01`) && (!to || toDate(p) <= `${to}-31`);
  const out = [], missing = [];
  if (s.measure !== 'level') { // a rate with no published index: shown as published
    out.push({ sel, s, color, kind: s.measure, origin: 'pub', pts: (state.obs.get(s.series_id) || []).filter(inRange) });
    return { out, missing };
  }
  const rates = ratesOf(s);
  const level = state.obs.get(s.series_id) || [];
  for (const kind of state.transforms) {
    let pts, origin, src = s;
    if (kind === 'level') { pts = level; origin = 'pub'; }
    else if (rates[kind] && rates[kind] !== s) { src = rates[kind]; pts = state.obs.get(src.series_id) || []; origin = 'oficial'; }
    else if (kind === 'ytd') { missing.push(kind); continue; }
    else { pts = transform(level, kind, from); origin = 'calc'; }
    out.push({ sel, s, src, color, kind, origin, pts: pts.filter(inRange) });
  }
  return { out, missing };
}
const traceLabel = (t) => (t.kind === 'level' ? 'Nivel' : `${MEASURE_LABELS[t.kind] || TRANSFORM_LABELS[t.kind]}`);
const originLabel = (t) => ({ pub: '', oficial: ' (oficial)', calc: ' (calc.)' }[t.origin]);
const traceUnit = (t) => (t.kind === 'level' ? t.s.unit || 'Nivel' : t.kind === 'diff' ? `Dif. (${t.s.unit || 'unid.'})` : t.kind === 'rebase' ? 'Base 100' : '%');

function median(values) {
  const v = values.filter((x) => x != null && Number.isFinite(x)).map(Math.abs).sort((a, b) => a - b);
  return v.length ? v[Math.floor(v.length / 2)] : null;
}
// Axis per trace: manual choice per series wins; otherwise, when the chart mixes
// levels and changes, changes go right; else, when scales differ by more than
// ~4x, the smaller-scale series go right.
function assignAxes(traces) {
  const auto = traces.filter((t) => t.sel.axis === 'auto');
  for (const t of traces) t.axis = t.sel.axis === 'auto' ? 'y' : t.sel.axis;
  if (!state.dualAxis || auto.length < 2) return;
  const isChange = (t) => CHANGE_KINDS.has(t.kind);
  if (auto.some(isChange) && auto.some((t) => !isChange(t))) {
    for (const t of auto) t.axis = isChange(t) ? 'y2' : 'y';
    return;
  }
  const mags = auto.map((t) => [t, median(t.pts.map(([, v]) => v))]).filter(([, m]) => m);
  if (mags.length < 2) return;
  const max = Math.max(...mags.map(([, m]) => m)), min = Math.min(...mags.map(([, m]) => m));
  if (max / min < 4) return;
  const cut = Math.sqrt(max * min);
  for (const [t, m] of mags) t.axis = m >= cut ? 'y' : 'y2';
}

function visibleData() {
  const from = $('from').value, to = $('to').value;
  const traces = [], missing = new Map();
  state.selected.forEach((sel, i) => {
    const r = seriesTraces(sel, i, from, to);
    traces.push(...r.out);
    if (r.missing.length) missing.set(sel.id, r.missing);
  });
  assignAxes(traces);
  return { traces, missing };
}

// ---------- selected grid + chart ----------
function renderSelected({ traces, missing }) {
  $('empty').hidden = state.selected.length > 0;
  $('selected').hidden = state.selected.length === 0;
  $('selected').querySelector('tbody').innerHTML = state.selected.map((sel, i) => {
    const s = state.byId.get(sel.id);
    const mine = traces.filter((t) => t.sel === sel);
    const shown = mine.map((t) => `<span class="${t.origin === 'calc' ? 'muted' : ''}" title="${t.src && t.src !== s ? esc(t.src.series_id) : ''}">${esc(traceLabel(t))}${originLabel(t)}</span>`)
      .concat((missing.get(sel.id) || []).map((k) => `<span class="warn" title="La fuente no publica esta tasa">${esc(TRANSFORM_SHORT[k])}: no publicada</span>`))
      .join(' · ');
    const sides = [...new Set(mine.map((t) => t.axis))].map((a) => (a === 'y' ? 'izq.' : 'dcha.')).join('/');
    const axisLabel = AXIS_LABELS[sel.axis];
    const axisTitleText = sel.axis === 'auto' ? `Automático: ahora en eje ${sides || 'izq.'} · clic para fijarlo` : 'Clic: Auto → Izq. → Dcha.';
    const rates = s.measure === 'level' ? publishedRatesLabel(s) : `${MEASURE_LABELS[s.measure]} (es la serie)`;
    return `
    <tr>
      <td><span class="swatch" style="background:${COLORS[i % COLORS.length]}"></span></td>
      <td class="code">${esc(sel.id)}</td>
      <td class="desc">${esc(s.concept)}${s.variant ? ` <span class="muted">· ${esc(s.variant)}</span>` : ''}</td>
      <td>${s.frequency}</td><td>${s.first_period}</td><td>${s.last_period}</td>
      <td class="num">${fmt(+s.last_value)}</td>
      <td>${rates ? esc(rates) : '<span class="muted">—</span>'}</td>
      <td>${adjCell(s)}</td>
      <td class="shown">${shown}</td>
      <td><button type="button" data-axis="${esc(sel.id)}" title="${esc(axisTitleText)}">${esc(axisLabel)}</button></td>
      <td><button type="button" data-remove="${esc(sel.id)}" aria-label="Quitar">✕</button></td>
    </tr>`;
  }).join('');
}

function axisTitle(traces, axis) {
  const labels = [...new Set(traces.filter((t) => t.axis === axis).map(traceUnit))];
  return labels.length === 1 ? labels[0] : labels.length ? labels.join(', ') : '';
}

function renderChart({ traces }) {
  const n = state.selected.length;
  const one = n === 1 ? state.byId.get(state.selected[0].id) : null;
  $('chart-title').textContent = !n ? '' : one ? `${one.concept}${one.variant ? ' · ' + one.variant : ''}` : `${n} series`;
  const left = axisTitle(traces, 'y'), right = axisTitle(traces, 'y2');
  $('chart-sub').textContent = traces.length ? [left && `eje izq.: ${left}`, right && `eje dcho.: ${right}`].filter(Boolean).join('  |  ') : '';
  const sources = [...new Set(state.selected.map((x) => state.byId.get(x.id).source.replace(/^Excel:.*/, 'Excel manual')))];
  const anyCalc = traces.some((t) => t.origin === 'calc'), anyOfficial = traces.some((t) => t.origin === 'oficial');
  $('chart-source').textContent = n ? `Fuente: ${sources.join(', ')}` + (anyOfficial ? ' · tasas oficiales de la fuente' : '')
    + (anyCalc ? ' · (calc.) = calculado a partir del nivel' : '') : '';

  const multi = state.transforms.length > 1;
  const axisStyle = { showline: true, linecolor: '#111', ticks: 'outside', tickcolor: '#111', mirror: false, zeroline: false };
  const plotted = traces.map((t) => {
    const name = `${t.sel.id}${multi || t.kind !== 'level' ? ` · ${traceLabel(t)}` : ''}${t.axis === 'y2' ? ' (dcha.)' : ''}`;
    return {
      x: t.pts.map(([p]) => toDate(p)), y: t.pts.map(([, v]) => (v == null ? null : +v)),
      name, yaxis: t.axis, type: 'scatter', mode: 'lines',
      line: { color: t.color, width: t.kind === 'level' ? 1.9 : 1.5, dash: DASH[t.kind] || 'solid' },
      hovertemplate: `%{x|%Y-%m}  %{y:,.2f}<extra>${esc(name)}</extra>`,
    };
  });
  const hasRight = traces.some((t) => t.axis === 'y2');
  const zero = (axis) => traces.some((t) => t.axis === axis && (CHANGE_KINDS.has(t.kind)));
  Plotly.react('chart', plotted, {
    margin: { l: 55, r: hasRight ? 60 : 15, t: 10, b: 30 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fff', font: { family: 'Segoe UI, Arial, sans-serif', color: '#111', size: 11 },
    showlegend: plotted.length > 1, legend: { orientation: 'h', x: 0, y: 1.1 }, hovermode: 'x unified',
    xaxis: { ...axisStyle, type: 'date', showgrid: false },
    yaxis: { ...axisStyle, showgrid: true, gridcolor: '#eceef1', zeroline: zero('y'), zerolinecolor: '#888' },
    yaxis2: { ...axisStyle, overlaying: 'y', side: 'right', showgrid: false, visible: hasRight,
      zeroline: zero('y2'), zerolinecolor: '#bbb' },
  }, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] });
}

function renderViewBar({ traces, missing }) {
  for (const b of $('transform-seg').querySelectorAll('button')) b.classList.toggle('on', state.transforms.includes(b.dataset.t));
  for (const b of $('adjust-seg').querySelectorAll('button')) b.classList.toggle('on', b.dataset.adj === state.adjPref);
  for (const b of $('axis-seg').querySelectorAll('button')) b.classList.toggle('on', (b.dataset.dual === '1') === state.dualAxis);
  const hints = state.transforms.map((k) => TRANSFORM_HINTS[k]);
  if (traces.some((t) => t.origin === 'oficial')) hints.push('Las tasas que publica la fuente se usan tal cual (oficial); el resto se calcula (calc.).');
  if (missing.size) hints.push(`${missing.size} serie(s) sin % acum. año publicada.`);
  if (state.adjPref) {
    const without = state.selected.filter((x) => state.byId.get(x.id).adjustment !== state.adjPref).length;
    hints.push(`Catálogo filtrado a la versión ${ADJ_LABELS[state.adjPref].toLowerCase()} cuando existe`
      + (without ? `; ${without} serie(s) seleccionada(s) no la tienen.` : '.'));
  }
  $('view-hint').textContent = hints.join(' ');
}

function update() {
  const data = visibleData();
  renderSelected(data);
  renderChart(data);
  renderViewBar(data);
  renderTree();
  // shareable view: #s=ID1,ID2:r&t=level,yoy&adj=sa&from=2020-01
  const params = new URLSearchParams();
  if (state.selected.length) params.set('s', state.selected.map((s) => s.id + ({ y: ':l', y2: ':r' }[s.axis] || '')).join(','));
  if (state.transforms.join(',') !== 'level') params.set('t', state.transforms.join(','));
  if (state.adjPref) params.set('adj', state.adjPref);
  if (!state.dualAxis) params.set('axes', '1');
  if ($('from').value) params.set('from', $('from').value);
  if ($('to').value) params.set('to', $('to').value);
  history.replaceState(null, '', params.toString() ? `#${params}` : location.pathname);
}

// ---------- export (wide table of what is plotted) ----------
function wideTable() {
  const { traces } = visibleData();
  const periods = [...new Set(traces.flatMap((t) => t.pts.map(([p]) => p)))].sort();
  const maps = traces.map((t) => new Map(t.pts));
  return [
    ['period', ...traces.map((t) => (t.kind === 'level' ? t.sel.id : `${t.sel.id} ${TRANSFORM_SHORT[t.kind]}`))],
    ['descripcion', ...traces.map((t) => `${t.s.concept}${t.s.variant ? ' · ' + t.s.variant : ''}`)],
    ['mostrado_como', ...traces.map((t) => `${traceUnit(t)}${t.kind === 'level' ? '' : ' · ' + traceLabel(t)}${originLabel(t)}`)],
    ['serie_origen', ...traces.map((t) => (t.src || t.s).series_id)],
    ['fuente', ...traces.map((t) => t.s.source)],
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
  const seen = new Set();
  state.selected = (params.get('s') || '').split(',').filter(Boolean)
    .map((t) => {
      const [raw, ax] = t.split(':');
      const s = parentOf(state.byId.get(raw)); // old links may point at a published rate
      return s && { id: s.series_id, axis: ax === 'r' ? 'y2' : ax === 'l' ? 'y' : 'auto' };
    })
    .filter((s) => s && !seen.has(s.id) && seen.add(s.id)).slice(0, MAX_SERIES);
  const t = (params.get('t') || '').split(',').filter((k) => TRANSFORM_LABELS[k]);
  state.transforms = t.length ? TRANSFORMS.filter((k) => t.includes(k)) : ['level'];
  if (ADJ_LABELS[params.get('adj')]) state.adjPref = params.get('adj');
  state.dualAxis = params.get('axes') !== '1';
  $('from').value = params.get('from') || '';
  $('to').value = params.get('to') || '';
  if (!state.selected.length) { // default view: unemployment Spain vs euro area
    state.selected = ['EUR_UNE_RT_M_ES', 'EUR_UNE_RT_M_EA'].filter((id) => state.byId.has(id)).map((id) => ({ id, axis: 'auto' }));
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
      s.adjustment ||= 'nsa'; s.base ||= ''; s.stem ||= s.series_id;
    }
    state.catalog = catalog;
    state.byId = new Map(catalog.map((s) => [s.series_id, s]));
    indexFamilies(catalog);
    for (const r of obs) {
      if (!state.obs.has(r.series_id)) state.obs.set(r.series_id, []);
      state.obs.get(r.series_id).push([r.period, r.value === '' ? null : +r.value]);
    }
    for (const pts of state.obs.values()) pts.sort((a, b) => (a[0] < b[0] ? -1 : 1));
    const latest = catalog.map((s) => s.retrieved_at).sort().pop() || '';
    setStatus(`${catalog.filter(isListed).length} series · datos actualizados ${latest.slice(0, 10)}`);
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
  if (axis) { const s = state.selected.find((x) => x.id === axis); s.axis = AXIS_NEXT[s.axis]; update(); }
  if (remove) toggleSeries(remove);
});
['from', 'to'].forEach((id) => $(id).addEventListener('change', update));
$('dl-csv').addEventListener('click', () => download('csv'));
$('dl-xlsx').addEventListener('click', () => download('xlsx'));
$('transform-seg').addEventListener('click', (e) => {
  const k = e.target.dataset.t;
  if (!k) return;
  const on = new Set(state.transforms);
  if (on.has(k)) { if (on.size === 1) return setStatus('Deja al menos una transformación.'); on.delete(k); } else on.add(k);
  state.transforms = TRANSFORMS.filter((x) => on.has(x));
  update();
});
$('adjust-seg').addEventListener('click', (e) => { if (e.target.dataset.adj != null) setAdjustment(e.target.dataset.adj); });
$('axis-seg').addEventListener('click', (e) => { if (e.target.dataset.dual) { state.dualAxis = e.target.dataset.dual === '1'; update(); } });
$('clear').addEventListener('click', () => { state.selected = []; update(); });
init();
