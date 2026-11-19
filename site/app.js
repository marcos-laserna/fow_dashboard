// Series Dashboard — static, Haver-style series browser.
// Data: catalog.csv (one row per series) + observations.csv (long format).
'use strict';

const MAX_SERIES = 8;
const COLORS = ['#1f4e8c', '#d1495b', '#2a9d8f', '#e9a03b', '#6a4c93', '#3d5a80', '#8d6e63', '#43aa8b'];
const GROUP_LABELS = {
  retail: 'Ventas minoristas', ipc: 'IPC · precios', icm: 'ICM · comercio minorista',
  iass: 'IASS · servicios', ipi: 'IPI · industria', eurostat: 'Eurostat · UE',
  manual: 'Excel manuales', other: 'Otros',
};
const TRANSFORM_LABELS = {
  level: 'Nivel', pct: '% periodo anterior', yoy: '% interanual', diff: 'Diferencia', rebase: 'Base 100',
};

const state = { catalog: [], obs: new Map(), selected: [] }; // selected: [{id, axis:'y'|'y2'}]
const $ = (id) => document.getElementById(id);

// ---------- data loading ----------
// On Pages the workflow copies the CSVs into site/data/. Locally (serving the
// repo root) they are read straight from data/processed/.
async function loadCsv(name) {
  for (const url of [`data/${name}`, `../data/processed/${name}`]) {
    const res = await fetch(url, { cache: 'no-cache' }).catch(() => null);
    if (res && res.ok) {
      return Papa.parse(await res.text(), { header: true, skipEmptyLines: true }).data;
    }
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
  // points: [[period, value]] sorted by period
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

// ---------- catalog panel ----------
function renderGroups() {
  const groups = [...new Set(state.catalog.map((s) => s.group))].sort();
  $('group').innerHTML = '<option value="">Todos los grupos</option>' +
    groups.map((g) => `<option value="${g}">${GROUP_LABELS[g] || g}</option>`).join('');
}

function renderCatalog() {
  const q = $('search').value.trim().toLowerCase();
  const g = $('group').value;
  const terms = q.split(/\s+/).filter(Boolean);
  const rows = state.catalog.filter((s) =>
    (!g || s.group === g) &&
    terms.every((t) => `${s.series_id} ${s.series_name} ${s.source}`.toLowerCase().includes(t)));
  const sel = new Set(state.selected.map((s) => s.id));
  $('catalog-count').textContent = `${rows.length} de ${state.catalog.length} series`;
  $('catalog').innerHTML = rows.slice(0, 400).map((s) => `
    <li data-id="${s.series_id}" class="${sel.has(s.series_id) ? 'on' : ''}">
      <input type="checkbox" tabindex="-1" ${sel.has(s.series_id) ? 'checked' : ''}>
      <div><span class="code">${s.series_id}</span>
        <span class="name">${s.series_name}</span>
        <span class="meta">${s.source} · ${s.frequency} · ${s.first_period}–${s.last_period} · último ${fmt(+s.last_value)}</span>
      </div>
    </li>`).join('');
}

function toggleSeries(id) {
  const i = state.selected.findIndex((s) => s.id === id);
  if (i >= 0) state.selected.splice(i, 1);
  else if (state.selected.length < MAX_SERIES) state.selected.push({ id, axis: 'y' });
  else return setStatus(`Máximo ${MAX_SERIES} series a la vez.`);
  update();
}

// ---------- workspace ----------
const meta = (id) => state.catalog.find((s) => s.series_id === id) || { series_id: id, series_name: id, unit: '' };
const fmt = (v) => (v == null || Number.isNaN(v) ? '—' : v.toLocaleString('es-ES', { maximumFractionDigits: 2 }));

function visibleData() {
  const from = $('from').value, to = $('to').value, kind = $('transform').value;
  return state.selected.map((s, i) => {
    const pts = transform(state.obs.get(s.id) || [], kind, from)
      .filter(([p]) => (!from || toDate(p) >= `${from}-01`) && (!to || toDate(p) <= `${to}-31`));
    return { ...s, color: COLORS[i % COLORS.length], meta: meta(s.id), pts };
  });
}

function renderChips(data) {
  $('selected').innerHTML = data.map((d) => `
    <span class="chip" title="${d.meta.series_name}">
      <span class="dot" style="background:${d.color}"></span>
      <span class="code">${d.id}</span>
      <button type="button" data-axis="${d.id}">${d.axis === 'y' ? 'Eje izq.' : 'Eje der.'}</button>
      <button type="button" data-remove="${d.id}" aria-label="Quitar">✕</button>
    </span>`).join('');
}

function renderChart(data) {
  $('empty').hidden = data.length > 0;
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  const ink = dark ? '#e6e8eb' : '#1b1f24', grid = dark ? '#2e343c' : '#e6e9ee';
  const kind = $('transform').value;
  const unit = (axis) => {
    if (kind !== 'level') return TRANSFORM_LABELS[kind];
    const units = [...new Set(data.filter((d) => d.axis === axis).map((d) => d.meta.unit).filter(Boolean))];
    return units.length === 1 ? units[0] : '';
  };
  const traces = data.map((d) => ({
    x: d.pts.map(([p]) => toDate(p)), y: d.pts.map(([, v]) => (v == null ? null : +v)),
    name: `${d.id} — ${d.meta.series_name}`.slice(0, 90), yaxis: d.axis,
    type: 'scatter', mode: 'lines', line: { color: d.color, width: 2, dash: d.axis === 'y2' ? 'dot' : 'solid' },
    hovertemplate: `%{x|%Y-%m}  %{y:,.2f}<extra>${d.id}</extra>`,
  }));
  const hasRight = data.some((d) => d.axis === 'y2');
  Plotly.react('chart', traces, {
    margin: { l: 60, r: hasRight ? 60 : 20, t: 20, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: ink, size: 12 },
    legend: { orientation: 'h', y: -0.15 }, hovermode: 'x unified',
    xaxis: { gridcolor: grid, type: 'date' },
    yaxis: { gridcolor: grid, title: { text: unit('y') }, zeroline: kind !== 'level' },
    yaxis2: { overlaying: 'y', side: 'right', showgrid: false, visible: hasRight, title: { text: unit('y2') } },
  }, { responsive: true, displaylogo: false });
}

function update() {
  const data = visibleData();
  renderChips(data);
  renderChart(data);
  renderCatalog();
  // Keep the view shareable: #s=ID1,ID2:r&t=yoy&from=2020-01
  const params = new URLSearchParams();
  if (state.selected.length) params.set('s', state.selected.map((s) => s.id + (s.axis === 'y2' ? ':r' : '')).join(','));
  if ($('transform').value !== 'level') params.set('t', $('transform').value);
  if ($('from').value) params.set('from', $('from').value);
  if ($('to').value) params.set('to', $('to').value);
  history.replaceState(null, '', params.toString() ? `#${params}` : location.pathname);
}

// ---------- downloads (wide table of what is plotted) ----------
function wideTable() {
  const data = visibleData();
  const periods = [...new Set(data.flatMap((d) => d.pts.map(([p]) => p)))].sort();
  const maps = data.map((d) => new Map(d.pts));
  const kind = TRANSFORM_LABELS[$('transform').value];
  const header = ['period', ...data.map((d) => d.id)];
  const names = ['nombre', ...data.map((d) => d.meta.series_name)];
  const units = ['unidad', ...data.map((d) => ($('transform').value === 'level' ? d.meta.unit : kind))];
  const body = periods.map((p) => [p, ...maps.map((m) => (m.get(p) == null ? '' : +m.get(p)))]);
  return [header, names, units, ...body];
}
function download(type) {
  if (!state.selected.length) return setStatus('No hay series seleccionadas.');
  const rows = wideTable();
  const stamp = new Date().toISOString().slice(0, 10);
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
  const known = new Set(state.catalog.map((s) => s.series_id));
  state.selected = (params.get('s') || '').split(',').filter(Boolean)
    .map((t) => { const [id, ax] = t.split(':'); return { id, axis: ax === 'r' ? 'y2' : 'y' }; })
    .filter((s) => known.has(s.id)).slice(0, MAX_SERIES);
  if (params.get('t')) $('transform').value = params.get('t');
  $('from').value = params.get('from') || '';
  $('to').value = params.get('to') || '';
  if (!state.selected.length) {
    // Default view: Spain vs euro area unemployment, if available.
    state.selected = ['EUR_UNE_RT_M_ES', 'EUR_UNE_RT_M_EA'].filter((id) => known.has(id)).map((id) => ({ id, axis: 'y' }));
    if (!$('from').value) $('from').value = '2015-01';
  }
}

async function init() {
  try {
    const [catalog, obs] = await Promise.all([loadCsv('catalog.csv'), loadCsv('observations.csv')]);
    state.catalog = catalog.sort((a, b) => a.group.localeCompare(b.group) || a.series_id.localeCompare(b.series_id));
    for (const r of obs) {
      if (!state.obs.has(r.series_id)) state.obs.set(r.series_id, []);
      state.obs.get(r.series_id).push([r.period, r.value === '' ? null : +r.value]);
    }
    for (const pts of state.obs.values()) pts.sort((a, b) => (a[0] < b[0] ? -1 : 1));
    const latest = catalog.map((s) => s.retrieved_at).sort().pop() || '';
    setStatus(`${catalog.length} series · actualizado ${latest.slice(0, 10)}`);
    renderGroups();
    restoreFromHash();
    update();
  } catch (err) {
    setStatus(`Error al cargar datos: ${err.message}`);
  }
}

$('search').addEventListener('input', renderCatalog);
$('group').addEventListener('change', renderCatalog);
$('catalog').addEventListener('click', (e) => {
  const li = e.target.closest('li[data-id]');
  if (li) toggleSeries(li.dataset.id);
});
$('selected').addEventListener('click', (e) => {
  const axisId = e.target.dataset.axis, removeId = e.target.dataset.remove;
  if (axisId) { const s = state.selected.find((x) => x.id === axisId); s.axis = s.axis === 'y' ? 'y2' : 'y'; update(); }
  if (removeId) toggleSeries(removeId);
});
['transform', 'from', 'to'].forEach((id) => $(id).addEventListener('change', update));
$('dl-csv').addEventListener('click', () => download('csv'));
$('dl-xlsx').addEventListener('click', () => download('xlsx'));
$('clear').addEventListener('click', () => { state.selected = []; update(); });
init();
