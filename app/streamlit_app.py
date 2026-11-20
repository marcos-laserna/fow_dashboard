"""Series Dashboard — Streamlit version of the Haver-style series browser.

Mirrors the GitHub Pages site (site/): same layout (title bar, toolbar,
catalog on the left, selected series + chart on the right), same transforms,
same switch between published versions (original / calendar / seasonally
adjusted), the published rates of an index used instead of computing them,
several transformations at once, automatic second axis, and the same
shareable URL (?s=ID1,ID2:r&t=level,yoy&adj=sa&from=2020-01).
"""

from __future__ import annotations

import html
import io
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
MAX_SERIES = 8
COLORS = ["#0b2e6b", "#c0392b", "#1e8449", "#d68910", "#6c3483", "#2e86c1", "#7b7d7d", "#a04000"]
GROUP_LABELS = {
    "retail": "Ventas minoristas", "ipc": "IPC · precios", "icm": "ICM · comercio minorista",
    "iass": "IASS · servicios", "ipi": "IPI · industria", "eurostat": "Eurostat · UE",
    "manual": "Excel manuales", "other": "Otros",
}
MEASURE_LABELS = {"level": "Nivel", "pct": "% m/m", "yoy": "% a/a", "ytd": "% acum. año"}
# Transformations; several can be shown at once. pct/yoy/ytd use the rate the
# source publishes when there is one ("oficial"); ytd is never computed.
TRANSFORMS = ["level", "pct", "yoy", "ytd", "diff", "rebase"]
TRANSFORM_LABELS = {
    "level": "Nivel", "pct": "% periodo anterior", "yoy": "% interanual", "ytd": "% acum. año",
    "diff": "Diferencia", "rebase": "Base 100",
}
TRANSFORM_BUTTONS = {**TRANSFORM_LABELS, "pct": "% vs. periodo anterior"}
TRANSFORM_SHORT = {"level": "nivel", "pct": "% m/m", "yoy": "% a/a", "ytd": "% acum.", "diff": "dif.", "rebase": "base 100"}
TRANSFORM_HINTS = {
    "level": "Nivel: valores tal como los publica la fuente.",
    "pct": "% periodo anterior: variación respecto al mes (o trimestre) anterior.",
    "yoy": "% interanual: variación respecto al mismo periodo del año anterior.",
    "ytd": "% acum. año: solo cuando la fuente la publica.",
    "diff": "Diferencia: cambio absoluto respecto al periodo anterior.",
    "rebase": "Base 100: índice = 100 en la primera fecha visible.",
}
RATE_SHORT = {"pct": "m/m", "yoy": "a/a", "ytd": "acum."}
DASH = {"level": "solid", "pct": "dot", "yoy": "dash", "ytd": "dashdot", "diff": "longdash", "rebase": "longdashdot"}
# Levels and changes on different axes, so rates are not squashed near zero.
CHANGE_KINDS = {"pct", "yoy", "ytd", "diff"}
AXIS_LABELS = {"auto": "Auto", "y": "Izq.", "y2": "Dcha."}
AXIS_NEXT = {"auto": "y", "y": "y2", "y2": "auto"}
ADJ_ORDER = ["nsa", "cal", "sa", "trend"]
ADJ_LABELS = {"nsa": "Original", "cal": "Corr. calendario", "sa": "Desestacionalizada", "trend": "Tendencia"}
ADJ_SHORT = {"nsa": "Orig.", "cal": "Cal.", "sa": "Desest.", "trend": "Tend."}
ADJ_BUTTONS = {"": "Todas", "nsa": "Original", "cal": "Corr. calendario", "sa": "Desestacionalizada"}
YOY_LAG = {"M": 12, "Q": 4, "A": 1}
DEFAULT_PICK = ["EUR_UNE_RT_M_ES", "EUR_UNE_RT_M_EA"]

st.set_page_config(page_title="Series Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Haver-style, white desktop look: dense grids, thin rules, navy accents (same tokens as site/style.css).
st.markdown(
    """<style>
    :root { --ink:#111; --muted:#5f6670; --rule:#c9ced6; --rule-soft:#e4e7ec; --navy:#0b2e6b; --bar:#f3f4f6; }
    html, body, .stApp, .stApp input, .stApp button, .stApp select, .stApp textarea {
        font-family: "Segoe UI", Tahoma, Arial, sans-serif !important; }
    header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stSidebarCollapsedControl"], footer { display: none !important; }
    .block-container, [data-testid="stMainBlockContainer"] {
        padding: 0 12px 1rem !important; max-width: 100% !important; }
    [data-testid="stVerticalBlock"] { gap: .4rem; }
    /* Streamlit gives markdown blocks margin-bottom:-1rem, which makes the next element overlap. */
    [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
    [data-testid="stMarkdownContainer"] p { margin: 0; line-height: 1.4; }
    [data-testid="stWidgetLabel"] p { font-size: 12px !important; color: var(--muted); line-height: 1.3; }
    [data-testid="stWidgetLabel"] { min-height: 0 !important; margin-bottom: 1px; }
    /* compact inputs, like the Pages toolbar */
    [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"] { min-height: 30px; }
    [data-baseweb="select"] > div > div { padding-top: 2px; padding-bottom: 2px; }
    [data-baseweb="input"] input, [data-baseweb="base-input"] input { padding-top: 4px; padding-bottom: 4px; font-size: 13px; }
    .stButton button, .stDownloadButton button {
        min-height: 0; padding: 2px 10px; font-size: 12px; border-radius: 2px;
        border: 1px solid var(--rule); background: linear-gradient(#fff, #eceef1); color: var(--ink); }
    .stButton button:hover, .stDownloadButton button:hover { border-color: var(--navy); color: var(--ink); }

    .titlebar { display:flex; gap:14px; align-items:baseline; padding:6px 12px; background:var(--navy);
        color:#fff; font-size:13px; margin: 0 -12px; }
    .titlebar span { color:#c8d4ea; font-size:11px; }
    .st-key-toolbar { background:var(--bar); border-bottom:1px solid var(--rule); padding:4px 12px 6px;
        margin: -0.4rem -12px 0; width: auto !important; gap: 0; }
    .pane-title { padding:4px 8px; background:var(--bar); border:1px solid var(--rule); border-width:0 0 1px;
        font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
    .pane-title .hint { text-transform:none; font-weight:400; letter-spacing:0; }
    .foot { color:var(--muted); font-size:11px; }
    .st-key-catalog_pane { border-right:1px solid var(--rule); padding-right:10px; }

    /* selected-series grid */
    .st-key-selected [data-testid="stHorizontalBlock"] { align-items:center; gap:.4rem;
        border-bottom:1px solid var(--rule-soft); padding:1px 0; }
    .st-key-selected p { font-size:12px; margin:0; }
    .st-key-selected .th p { font-weight:600; color:var(--muted); }
    .st-key-selected .stButton button { padding:0 6px; font-size:11px; }
    .code { font-family: Consolas, "Courier New", monospace; color:var(--navy); font-size:12px; }
    .swatch { display:inline-block; width:14px; height:3px; vertical-align:middle; }
    .muted { color:var(--muted); }
    [data-testid="stButtonGroup"] button { min-height:0; padding:1px 7px; font-size:11px; }

    /* view bar: how the chart shows the data, right above it */
    .st-key-viewbar { background:var(--bar); border:1px solid var(--rule); padding:8px 10px 6px; gap:.2rem; }
    .st-key-viewbar [data-testid="stHorizontalBlock"] { gap: 1.2rem; }
    .st-key-viewbar [data-testid="stWidgetLabel"] p { font-weight:600; font-size:11px !important;
        text-transform:uppercase; letter-spacing:.04em; }
    .st-key-viewbar [data-testid="stButtonGroup"] button { padding:3px 10px; font-size:12px; }
    .view-hint { color:var(--muted); font-size:11px; }
    .warn { color:#8a5a10; }
    .st-key-chart_box { border-top:0 !important; margin-top:-.4rem; }

    /* chart box */
    .st-key-chart_box { border:1px solid var(--rule); padding:12px 14px 8px; }
    .chart-title { font-size:14px; font-weight:600; }
    .chart-sub { color:var(--muted); font-size:12px; }
    .chart-source { color:var(--muted); font-size:11px; border-top:1px solid var(--rule-soft); padding-top:4px; }
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = pd.read_csv(DATA / "catalog.csv", dtype=str).fillna("")
    for col, default in (("adjustment", "nsa"), ("base", ""), ("stem", "")):
        if col not in catalog:
            catalog[col] = default
    catalog.loc[catalog["concept"] == "", "concept"] = catalog["series_name"]
    catalog.loc[catalog["measure"] == "", "measure"] = "level"
    catalog.loc[catalog["adjustment"] == "", "adjustment"] = "nsa"
    catalog.loc[catalog["stem"] == "", "stem"] = catalog["series_id"]
    obs = pd.read_csv(DATA / "observations.csv", dtype={"period": str, "series_id": str})
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    return catalog, obs


@st.cache_data(ttl=3600)
def families(catalog: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    """versions: series_id -> ids of its published versions (original / calendar / SA), in ADJ_ORDER.
    rates: series_id -> {measure: id} for the index and the rates the source publishes for it."""
    versions: dict[str, list[str]] = {}
    for _, fam in catalog[catalog["base"] != ""].groupby(["group", "base"]):
        # Only a family where each adjustment appears once is unambiguous.
        if len(fam) > 1 and fam["adjustment"].is_unique:
            ids = list(fam.sort_values("adjustment", key=lambda a: a.map(ADJ_ORDER.index))["series_id"])
            for sid in ids:
                versions[sid] = ids
    rates: dict[str, dict[str, str]] = {}
    for _, fam in catalog.groupby(["group", "stem", "adjustment"]):
        slot: dict[str, str] = {}
        for sid, m in zip(fam["series_id"], fam["measure"]):
            slot.setdefault(m, sid)
        for sid in fam["series_id"]:
            rates[sid] = slot
    return versions, rates


def to_date(period: str) -> pd.Timestamp:
    if "-Q" in period:
        return pd.Timestamp(year=int(period[:4]), month=(int(period[-1]) - 1) * 3 + 1, day=1)
    if len(period) == 7:
        return pd.Timestamp(f"{period}-01")
    if len(period) == 4:
        return pd.Timestamp(year=int(period), month=1, day=1)
    return pd.Timestamp(period)


def transform(s: pd.Series, kind: str, freq: str) -> pd.Series:
    """s: values indexed by date, sorted. Mirrors pipeline/transforms.py."""
    if kind == "pct":
        return s.pct_change(fill_method=None) * 100
    if kind == "diff":
        return s.diff()
    if kind == "yoy":
        if freq not in YOY_LAG:
            return s * float("nan")
        # Match by calendar period (not position) so gaps don't misalign.
        prev = s.copy()
        prev.index = prev.index + pd.DateOffset(months={"M": 1, "Q": 3, "A": 12}[freq] * YOY_LAG[freq])
        return (s / prev.reindex(s.index) - 1) * 100
    if kind == "rebase":
        first = s.dropna()
        return s / first.iloc[0] * 100 if len(first) and first.iloc[0] != 0 else s * float("nan")
    return s


catalog, obs = load()
meta = catalog.set_index("series_id")
versions, rates = families(catalog)
ss = st.session_state


def parent_of(sid: str) -> str:
    """A published rate whose index is also published is reached through the index."""
    if meta.at[sid, "measure"] != "level":
        return rates.get(sid, {}).get("level", sid)
    return sid


listed = catalog[[parent_of(s) == s for s in catalog["series_id"]]]


def describe(sid: str) -> str:
    variant = meta.at[sid, "variant"]
    return meta.at[sid, "concept"] + (f" · {variant}" if variant else "")


def published_rates(sid: str) -> str:
    r = rates.get(sid, {})
    return " · ".join(RATE_SHORT[m] for m in ("pct", "yoy", "ytd") if r.get(m) and r[m] != sid)


def fmt(v: str) -> str:
    x = pd.to_numeric(v, errors="coerce")
    return "—" if pd.isna(x) else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- state (restored once from the URL, like the Pages hash) ----------
if "picked" not in ss:
    qp = st.query_params
    ss.picked, ss.axis = [], {}
    for token in qp.get("s", "").split(","):
        raw, _, ax = token.partition(":")
        if raw not in meta.index:
            continue
        sid = parent_of(raw)  # old links may point at a published rate
        if sid not in ss.picked and len(ss.picked) < MAX_SERIES:
            ss.picked.append(sid)
            ss.axis[sid] = {"r": "y2", "l": "y"}.get(ax, "auto")
    kinds = [k for k in TRANSFORMS if k in qp.get("t", "").split(",")]
    ss.kinds = kinds or ["level"]
    ss.adj_pref = qp.get("adj", "") if qp.get("adj") in ADJ_LABELS else ""
    ss.dual = "0" if qp.get("axes") == "1" else "1"
    ss.kinds_last, ss.adj_last, ss.dual_last = list(ss.kinds), ss.adj_pref, ss.dual

    def _month(text: str | None, fallback: date | None) -> date | None:
        try:
            return date.fromisoformat(f"{text}-01") if text else fallback
        except ValueError:
            return fallback

    if not ss.picked:  # default view: unemployment Spain vs euro area
        ss.picked = [s for s in DEFAULT_PICK if s in meta.index]
    ss.start = _month(qp.get("from"), date(2015, 1, 1))
    ss.end = _month(qp.get("to"), None)
    ss.editor_version = 0
    ss.notice = ""


def toggle(sid: str) -> None:
    if sid in ss.picked:
        ss.picked.remove(sid)
        ss.axis.pop(sid, None)
    elif len(ss.picked) < MAX_SERIES:
        ss.picked.append(sid)
        ss.axis[sid] = "auto"
    else:
        ss.notice = f"Máximo {MAX_SERIES} series a la vez."


def swap(old: str, new: str) -> bool:
    """Replace a selected series by another version, keeping its position and axis."""
    if old == new or new in ss.picked or old not in ss.picked:
        return False
    ss.picked[ss.picked.index(old)] = new
    ss.axis[new] = ss.axis.pop(old, "auto")
    return True


def on_catalog_edit(key: str, ids: list[str]) -> None:
    for row, change in ss[key]["edited_rows"].items():
        if "✓" in change and change["✓"] != (ids[int(row)] in ss.picked):
            toggle(ids[int(row)])
    ss.editor_version += 1  # fresh editor so its checkboxes reflect ss.picked


def on_row_adjust(old: str) -> None:
    new = ss[f"adj_{old}"]
    if new is None:  # segmented control was clicked off: keep the current version
        ss[f"adj_{old}"] = old
    elif not swap(old, new) and new != old:
        ss.notice = "Esa versión ya está seleccionada."


def on_kinds() -> None:
    if not ss.kinds:  # at least one transformation
        ss.kinds = list(ss.kinds_last)
        ss.notice = "Deja al menos una transformación."
    ss.kinds = [k for k in TRANSFORMS if k in ss.kinds]
    ss.kinds_last = list(ss.kinds)


def on_dual() -> None:
    if ss.dual is None:
        ss.dual = ss.dual_last
    ss.dual_last = ss.dual


def on_adj_pref() -> None:
    """Preferred published version: swaps the selection and filters the catalog."""
    if ss.adj_pref is None:
        ss.adj_pref = ss.adj_last
    ss.adj_last = adj = ss.adj_pref
    if not adj:
        ss.notice = "Ajuste: se muestran todas las versiones publicadas"
        return
    changed = missing = 0
    for sid in list(ss.picked):
        fam = versions.get(sid)
        target = next((v for v in fam if meta.at[v, "adjustment"] == adj), None) if fam else None
        if target is None:
            missing += meta.at[sid, "adjustment"] != adj
        elif swap(sid, target):
            changed += 1
    ss.editor_version += 1
    ss.notice = f"{ADJ_LABELS[adj]}: {changed} serie(s) cambiada(s)" + (
        f" · {missing} sin esa versión publicada" if missing else "")


def clear() -> None:
    ss.picked, ss.axis = [], {}
    ss.editor_version += 1


# ---------- title bar ----------
updated = catalog["retrieved_at"].max()[:10] if len(catalog) else "—"
status = ss.notice or f"{len(listed)} series · datos actualizados {updated}"
ss.notice = ""
st.markdown(
    f'<div class="titlebar"><strong>Series Dashboard</strong><span>{html.escape(status)}</span></div>',
    unsafe_allow_html=True,
)

# ---------- toolbar ----------
with st.container(key="toolbar"):
    t2, t3, _, t6, t7, t8 = st.columns([1.1, 1.1, 3.6, 1.1, 1.1, 0.8], vertical_alignment="bottom")
    t2.date_input("Desde", key="start", min_value=date(1950, 1, 1), format="YYYY-MM-DD")
    t3.date_input("Hasta", key="end", min_value=date(1950, 1, 1), format="YYYY-MM-DD")
    t8.button("Limpiar", on_click=clear, width="stretch")

kinds: list[str] = ss.kinds
adj_pref: str = ss.adj_pref
dual: bool = ss.dual == "1"
left, work = st.columns([1, 2.7], gap="medium")

# ---------- catalog (left pane): indexes only; their published rates come through "Mostrar como" ----------
with left, st.container(key="catalog_pane"):
    st.markdown('<div class="pane-title">Bases de datos</div>', unsafe_allow_html=True)
    query = st.text_input("Buscar", placeholder="Buscar código o descripción…", label_visibility="collapsed")
    view = listed
    for term in query.lower().split():
        text = (view["series_id"] + " " + view["series_name"] + " " + view["source"] + " "
                + view["group"].map(GROUP_LABELS).fillna("") + " " + view["adjustment"].map(ADJ_LABELS).fillna(""))
        view = view[text.str.lower().str.contains(term, regex=False)]
    groups = sorted(view["group"].unique(), key=lambda g: GROUP_LABELS.get(g, g))
    group = st.selectbox("Base", ["*"] + groups, format_func=lambda g: "Todas las bases" if g == "*" else GROUP_LABELS.get(g, g),
                         label_visibility="collapsed")
    if group != "*":
        view = view[view["group"] == group]
    if adj_pref:  # one version per family: the preferred one when it exists
        has_pref = {sid for sid, fam in versions.items() if any(meta.at[v, "adjustment"] == adj_pref for v in fam)}
        view = view[~view["series_id"].isin(has_pref) | (view["adjustment"] == adj_pref)]

    def _tags(r: pd.Series) -> str:
        parts = [] if r["measure"] == "level" else [MEASURE_LABELS[r["measure"]]]
        if published_rates(r["series_id"]):
            parts.append("+ tasas")
        if r["series_id"] in versions or r["adjustment"] != "nsa":
            parts.append(ADJ_SHORT[r["adjustment"]])
        return " ".join(parts)

    def _desc(r: pd.Series) -> str:
        v = r["variant"]
        return r["concept"] if not v or (r["measure"] == "level" and v.lower() in ("índice", "indice")) else f'{r["concept"]} · {v}'

    grid = pd.DataFrame({
        "✓": view["series_id"].isin(ss.picked).values,
        "Código": view["series_id"].values,
        "Descripción": view.apply(_desc, axis=1).values if len(view) else [],
        "Tipo": view.apply(_tags, axis=1).values if len(view) else [],
    })
    ids = list(view["series_id"])
    key = f"catalog_{ss.editor_version}"
    st.data_editor(
        grid, key=key, hide_index=True, height=520, width="stretch",
        disabled=["Código", "Descripción", "Tipo"],
        column_config={
            "✓": st.column_config.CheckboxColumn("", width=30),
            "Código": st.column_config.TextColumn(width=125),
            "Descripción": st.column_config.TextColumn(width="large"),
            "Tipo": st.column_config.TextColumn(width="small", help="«+ tasas»: la fuente publica sus tasas (m/m, a/a, acum.), "
                                                                   "que se eligen en «Mostrar como». Orig./Desest.: versión publicada."),
        },
        on_change=on_catalog_edit, args=(key, ids),
    )
    st.markdown(f'<div class="foot">{len(view)} de {len(listed)} series · las tasas oficiales '
                f'({len(catalog) - len(listed)}) se eligen en «Mostrar como»</div>', unsafe_allow_html=True)

picked: list[str] = ss.picked
axis_choice: dict[str, str] = ss.axis
start = pd.Timestamp(ss.start) if ss.start else None
end = pd.Timestamp(ss.end) if ss.end else None


# ---------- traces: one per (series, transformation) ----------
def series_of(sid: str) -> pd.Series:
    rows = obs[obs["series_id"] == sid]
    s = pd.Series(rows["value"].values, index=rows["period"].map(to_date)).sort_index()
    return s[~s.index.duplicated(keep="last")]


def clip(s: pd.Series) -> pd.Series:
    if start is not None:
        s = s[s.index >= start]
    if end is not None:
        s = s[s.index <= end]
    return s


traces: list[dict] = []   # {sid, color, kind, origin: pub | oficial | calc, src, s, axis}
missing: dict[str, list[str]] = {}
for i, sid in enumerate(picked):
    color = COLORS[i % len(COLORS)]
    if meta.at[sid, "measure"] != "level":  # a rate with no published index: shown as published
        traces.append(dict(sid=sid, color=color, kind=meta.at[sid, "measure"], origin="pub", src=sid, s=clip(series_of(sid))))
        continue
    level = series_of(sid)
    fam = rates.get(sid, {})
    for kind in kinds:
        if kind == "level":
            traces.append(dict(sid=sid, color=color, kind=kind, origin="pub", src=sid, s=clip(level)))
        elif fam.get(kind) and fam[kind] != sid:  # published by the source: used as is
            traces.append(dict(sid=sid, color=color, kind=kind, origin="oficial", src=fam[kind], s=clip(series_of(fam[kind]))))
        elif kind == "ytd":  # never computed
            missing.setdefault(sid, []).append(kind)
        else:
            base = level[level.index >= start] if kind == "rebase" and start is not None else level
            traces.append(dict(sid=sid, color=color, kind=kind, origin="calc", src=sid,
                               s=clip(transform(base, kind, meta.at[sid, "frequency"]))))

# Axis per trace: a manual choice per series wins; otherwise, when the chart mixes
# levels and changes, changes go right; else, when scales differ by more than ~4x,
# the smaller-scale series go right.
for t in traces:
    t["axis"] = "y" if axis_choice.get(t["sid"], "auto") == "auto" else axis_choice[t["sid"]]
auto = [t for t in traces if axis_choice.get(t["sid"], "auto") == "auto"]
if dual and len(auto) > 1:
    if any(t["kind"] in CHANGE_KINDS for t in auto) and any(t["kind"] not in CHANGE_KINDS for t in auto):
        for t in auto:
            t["axis"] = "y2" if t["kind"] in CHANGE_KINDS else "y"
    else:
        mags = [(t, t["s"].abs().median()) for t in auto]
        mags = [(t, m) for t, m in mags if pd.notna(m) and m > 0]
        if len(mags) > 1:
            hi, lo = max(m for _, m in mags), min(m for _, m in mags)
            if hi / lo >= 4:
                cut = (hi * lo) ** 0.5
                for t, m in mags:
                    t["axis"] = "y" if m >= cut else "y2"


def trace_label(t: dict) -> str:
    return "Nivel" if t["kind"] == "level" else MEASURE_LABELS.get(t["kind"], TRANSFORM_LABELS[t["kind"]])


def origin_label(t: dict) -> str:
    return {"pub": "", "oficial": " (oficial)", "calc": " (calc.)"}[t["origin"]]


def trace_unit(t: dict) -> str:
    unit = meta.at[t["sid"], "unit"]
    if t["kind"] == "level":
        return unit or "Nivel"
    if t["kind"] == "diff":
        return f"Dif. ({unit or 'unid.'})"
    return "Base 100" if t["kind"] == "rebase" else "%"


def trace_code(t: dict) -> str:
    """Official rates are separate series with their own code (IPC251861 is the m/m of IPC251859)."""
    return t["src"] if t["origin"] == "oficial" else t["sid"]


def trace_name(t: dict) -> str:
    multi = len(kinds) > 1 or t["kind"] != "level"
    label = f" · {trace_label(t)}" + (" calc." if t["origin"] == "calc" else "") if multi else ""
    return trace_code(t) + label + (" (dcha.)" if t["axis"] == "y2" else "")


# ---------- work area: selected grid + view bar + chart ----------
with work:
    st.markdown('<div class="pane-title">Series seleccionadas</div>', unsafe_allow_html=True)
    if not picked:
        st.markdown('<p class="muted">Marca series en el catálogo de la izquierda (máx. 8).</p>', unsafe_allow_html=True)
    else:
        widths = [0.25, 1.4, 3.0, 0.4, 1.35, 0.75, 1.1, 1.7, 2.0, 0.6, 0.35]
        with st.container(key="selected"):
            head = st.columns(widths)
            for col, label in zip(head, ["", "Código", "Descripción", "Frec.", "Rango", "Último", "Tasas oficiales",
                                         "Ajuste", "Mostrado como", "Eje", ""]):
                col.markdown(f'<div class="th"><p>{label}</p></div>', unsafe_allow_html=True)
            for i, sid in enumerate(list(picked)):
                mine = [t for t in traces if t["sid"] == sid]
                c = st.columns(widths, vertical_alignment="center")
                c[0].markdown(f'<span class="swatch" style="background:{COLORS[i % len(COLORS)]}"></span>', unsafe_allow_html=True)
                c[1].markdown(f'<span class="code">{html.escape(sid)}</span>', unsafe_allow_html=True)
                c[2].markdown(html.escape(describe(sid)))
                c[3].markdown(meta.at[sid, "frequency"])
                c[4].markdown(f'{meta.at[sid, "first_period"]} – {meta.at[sid, "last_period"]}')
                c[5].markdown(fmt(meta.at[sid, "last_value"]))
                pub = published_rates(sid) if meta.at[sid, "measure"] == "level" else f'{MEASURE_LABELS[meta.at[sid, "measure"]]} (es la serie)'
                c[6].markdown(html.escape(pub) if pub else '<span class="muted">—</span>', unsafe_allow_html=True)
                if sid in versions:
                    ss[f"adj_{sid}"] = sid
                    c[7].segmented_control(
                        "Ajuste", versions[sid], key=f"adj_{sid}", label_visibility="collapsed",
                        format_func=lambda v: ADJ_SHORT[meta.at[v, "adjustment"]],
                        on_change=on_row_adjust, args=(sid,),
                    )
                else:
                    adj = meta.at[sid, "adjustment"]
                    if adj_pref and adj != adj_pref:
                        c[7].markdown(f'<span class="warn" title="La fuente no publica esta serie en versión '
                                      f'{ADJ_LABELS[adj_pref].lower()}">{ADJ_SHORT[adj]} · sin {ADJ_SHORT[adj_pref].lower()}</span>',
                                      unsafe_allow_html=True)
                    else:
                        c[7].markdown(f'<span class="muted">{ADJ_SHORT[adj] if adj != "nsa" else "—"}</span>', unsafe_allow_html=True)
                shown = [f'<span class="{"muted" if t["origin"] == "calc" else ""}">{html.escape(trace_label(t))}'
                         + (f' <span class="code">{html.escape(t["src"])}</span>' if t["origin"] == "oficial"
                            else html.escape(origin_label(t))) + "</span>"
                         for t in mine]
                shown += [f'<span class="warn">{TRANSFORM_SHORT[k]}: no publicada</span>' for k in missing.get(sid, [])]
                c[8].markdown(" · ".join(shown), unsafe_allow_html=True)
                choice = axis_choice.get(sid, "auto")
                sides = "/".join(dict.fromkeys("izq." if t["axis"] == "y" else "dcha." for t in mine)) or "izq."
                if c[9].button(AXIS_LABELS[choice], key=f"ax_{sid}",
                               help=f"Automático: ahora en eje {sides} · clic para fijarlo" if choice == "auto"
                               else "Clic: Auto → Izq. → Dcha."):
                    axis_choice[sid] = AXIS_NEXT[choice]
                    st.rerun()
                if c[10].button("✕", key=f"rm_{sid}", help="Quitar"):
                    toggle(sid)
                    ss.editor_version += 1
                    st.rerun()

    with st.container(key="viewbar"):
        v1, v2 = st.columns([1.5, 1])
        v1.segmented_control("Mostrar como (varias a la vez)", TRANSFORMS, selection_mode="multi",
                             format_func=TRANSFORM_BUTTONS.get, key="kinds", on_change=on_kinds,
                             help="Las tasas que publica la fuente se usan tal cual (oficial); el resto se calcula. "
                                  "«% acum. año» solo si la fuente la publica.")
        v2.segmented_control("Ejes", ["1", "0"], format_func={"1": "Doble automático", "0": "Uno solo"}.get,
                             key="dual", on_change=on_dual,
                             help="Doble automático: niveles a la izquierda y variaciones a la derecha; también separa "
                                  "series de escalas muy distintas. Cada fila puede fijar su eje.")
        st.segmented_control("Ajuste estacional", list(ADJ_BUTTONS), format_func=ADJ_BUTTONS.get,
                             key="adj_pref", on_change=on_adj_pref,
                             help="Elige la versión publicada por la fuente. Cambia las series seleccionadas y "
                                  "filtra el catálogo; «Todas» muestra todas las versiones.")
        hints = [TRANSFORM_HINTS[k] for k in kinds]
        if any(t["origin"] == "oficial" for t in traces):
            hints.append("Las tasas que publica la fuente se usan tal cual (oficial); el resto se calcula (calc.).")
        if missing:
            hints.append(f"{len(missing)} serie(s) sin % acum. año publicada.")
        if adj_pref:
            without = sum(meta.at[s, "adjustment"] != adj_pref for s in picked)
            hints.append(f"Catálogo filtrado a la versión {ADJ_LABELS[adj_pref].lower()} cuando existe"
                         + (f"; {without} serie(s) seleccionada(s) no la tienen." if without else "."))
        st.markdown(f'<div class="view-hint">{html.escape(" ".join(hints))}</div>', unsafe_allow_html=True)

    def axis_title(axis: str) -> str:
        return ", ".join(dict.fromkeys(trace_unit(t) for t in traces if t["axis"] == axis))

    with st.container(key="chart_box"):
        if picked:
            title = describe(picked[0]) if len(picked) == 1 else f"{len(picked)} series"
            left_t, right_t = axis_title("y"), axis_title("y2")
            subtitle = "  |  ".join(x for x in (left_t and f"eje izq.: {left_t}", right_t and f"eje dcho.: {right_t}") if x)
            st.markdown(f'<div class="chart-title">{html.escape(title)}</div><div class="chart-sub">{html.escape(subtitle)}</div>',
                        unsafe_allow_html=True)
        axis = dict(showline=True, linecolor="#111", ticks="outside", tickcolor="#111", zeroline=False)
        fig = go.Figure()
        for t in traces:
            s = t["s"].dropna()
            name = trace_name(t)
            fig.add_trace(go.Scatter(
                x=s.index, y=s.values, mode="lines", name=name, yaxis=t["axis"],
                line={"color": t["color"], "width": 1.9 if t["kind"] == "level" else 1.5, "dash": DASH.get(t["kind"], "solid")},
                hovertemplate=f"%{{x|%Y-%m}}  %{{y:,.2f}}<extra>{html.escape(name)}</extra>",
            ))
        has_right = any(t["axis"] == "y2" for t in traces)
        zero = {a: any(t["axis"] == a and t["kind"] in CHANGE_KINDS for t in traces) for a in ("y", "y2")}
        fig.update_layout(
            height=440, hovermode="x unified", margin={"l": 55, "r": 60 if has_right else 15, "t": 10, "b": 30},
            paper_bgcolor="#fff", plot_bgcolor="#fff",
            font={"family": "Segoe UI, Arial, sans-serif", "color": "#111", "size": 11},
            showlegend=len(traces) > 1, legend={"orientation": "h", "x": 0, "y": 1.1},
            xaxis={**axis, "type": "date", "showgrid": False},
            yaxis={**axis, "showgrid": True, "gridcolor": "#eceef1", "zeroline": zero["y"], "zerolinecolor": "#888"},
            yaxis2={**axis, "overlaying": "y", "side": "right", "showgrid": False, "visible": has_right,
                    "zeroline": zero["y2"], "zerolinecolor": "#bbb"},
        )
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
        if picked:
            sources = sorted({"Excel manual" if meta.at[s, "source"].startswith("Excel:") else meta.at[s, "source"] for s in picked})
            note = (" · tasas oficiales de la fuente" if any(t["origin"] == "oficial" for t in traces) else "") + (
                " · (calc.) = calculado a partir del nivel" if any(t["origin"] == "calc" for t in traces) else "")
            st.markdown(f'<div class="chart-source">Fuente: {html.escape(", ".join(sources) + note)}</div>', unsafe_allow_html=True)

    if traces:
        cols = [trace_code(t) if t["origin"] != "calc" else f'{t["sid"]} {TRANSFORM_SHORT[t["kind"]]} calc.' for t in traces]
        table = pd.DataFrame({c: t["s"] for c, t in zip(cols, traces)}).sort_index()
        table.index = table.index.strftime("%Y-%m")
        table.index.name = "period"
        with st.expander("Datos", expanded=False):
            st.dataframe(table.iloc[::-1], width="stretch")

# ---------- export (toolbar buttons, filled once the data is known) ----------
if traces:
    header = pd.DataFrame(
        [[describe(t["sid"]) for t in traces],
         [trace_unit(t) + ("" if t["kind"] == "level" else " · " + trace_label(t)) + origin_label(t) for t in traces],
         [t["src"] for t in traces],
         [meta.at[t["sid"], "source"] for t in traces]],
        index=["descripcion", "mostrado_como", "serie_origen", "fuente"], columns=cols,
    )
    export = pd.concat([header, table.astype(object)])
    export.index.name = "period"
    stamp = date.today().isoformat()
    t6.download_button("Exportar CSV", export.to_csv().encode("utf-8-sig"), f"series_{stamp}.csv", "text/csv",
                       width="stretch")
    buf = io.BytesIO()
    export.to_excel(buf, sheet_name="datos")
    t7.download_button("Exportar Excel", buf.getvalue(), f"series_{stamp}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

# ---------- shareable URL (same keys as the Pages hash) ----------
params = {}
if picked:
    params["s"] = ",".join(s + {"y": ":l", "y2": ":r"}.get(axis_choice.get(s, "auto"), "") for s in picked)
if kinds != ["level"]:
    params["t"] = ",".join(kinds)
if adj_pref:
    params["adj"] = adj_pref
if not dual:
    params["axes"] = "1"
if ss.start:
    params["from"] = ss.start.strftime("%Y-%m")
if ss.end:
    params["to"] = ss.end.strftime("%Y-%m")
if dict(st.query_params) != params:
    st.query_params.from_dict(params)
