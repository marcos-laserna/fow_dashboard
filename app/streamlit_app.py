"""Series Dashboard — Streamlit version of the Haver-style series browser.

Mirrors the GitHub Pages site (site/): same layout (title bar, toolbar,
catalog on the left, selected series + chart on the right), same transforms,
same switch between published versions (original / calendar / seasonally
adjusted) and the same shareable URL (?s=ID1,ID2:r&t=yoy&from=2020-01).
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
TRANSFORM_LABELS = {
    "level": "Nivel", "pct": "% periodo anterior", "yoy": "% interanual",
    "diff": "Diferencia", "rebase": "Base 100 = inicio",
}
ADJ_ORDER = ["nsa", "cal", "sa", "trend"]
ADJ_LABELS = {"nsa": "Original", "cal": "Corr. calendario", "sa": "Desestacionalizada", "trend": "Tendencia"}
ADJ_SHORT = {"nsa": "Orig.", "cal": "Cal.", "sa": "Desest.", "trend": "Tend."}
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
    for col, default in (("adjustment", "nsa"), ("base", "")):
        if col not in catalog:
            catalog[col] = default
    catalog.loc[catalog["concept"] == "", "concept"] = catalog["series_name"]
    catalog.loc[catalog["measure"] == "", "measure"] = "level"
    catalog.loc[catalog["adjustment"] == "", "adjustment"] = "nsa"
    obs = pd.read_csv(DATA / "observations.csv", dtype={"period": str, "series_id": str})
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    return catalog, obs


@st.cache_data(ttl=3600)
def version_index(catalog: pd.DataFrame) -> dict[str, list[str]]:
    """series_id -> ids of all published versions of that series, in ADJ_ORDER."""
    out: dict[str, list[str]] = {}
    for _, fam in catalog[catalog["base"] != ""].groupby(["group", "base"]):
        # Only a family where each adjustment appears once is unambiguous.
        if len(fam) > 1 and fam["adjustment"].is_unique:
            ids = list(fam.sort_values("adjustment", key=lambda a: a.map(ADJ_ORDER.index))["series_id"])
            for sid in ids:
                out[sid] = ids
    return out


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
versions = version_index(catalog)
ss = st.session_state


def describe(sid: str) -> str:
    variant = meta.at[sid, "variant"]
    return meta.at[sid, "concept"] + (f" · {variant}" if variant else "")


def fmt(v: str) -> str:
    x = pd.to_numeric(v, errors="coerce")
    return "—" if pd.isna(x) else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- state (restored once from the URL, like the Pages hash) ----------
if "picked" not in ss:
    qp = st.query_params
    ss.picked, ss.right = [], set()
    for token in qp.get("s", "").split(","):
        sid, _, ax = token.partition(":")
        if sid in meta.index and sid not in ss.picked and len(ss.picked) < MAX_SERIES:
            ss.picked.append(sid)
            if ax == "r":
                ss.right.add(sid)
    ss.kind = qp.get("t", "level") if qp.get("t") in TRANSFORM_LABELS else "level"

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
        ss.right.discard(sid)
    elif len(ss.picked) < MAX_SERIES:
        ss.picked.append(sid)
    else:
        ss.notice = f"Máximo {MAX_SERIES} series a la vez."


def swap(old: str, new: str) -> bool:
    """Replace a selected series by another version, keeping its position and axis."""
    if old == new or new in ss.picked or old not in ss.picked:
        return False
    ss.picked[ss.picked.index(old)] = new
    if old in ss.right:
        ss.right.discard(old)
        ss.right.add(new)
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


def on_adjust_all() -> None:
    adj = ss.adj_all
    if adj is None:
        return
    changed = missing = 0
    for sid in list(ss.picked):
        fam = versions.get(sid)
        if not fam:
            continue
        target = next((v for v in fam if meta.at[v, "adjustment"] == adj), None)
        if target is None:
            missing += 1
        elif swap(sid, target):
            changed += 1
    ss.notice = f"{ADJ_LABELS[adj]}: {changed} serie(s) cambiada(s)" + (
        f" · {missing} sin esa versión" if missing else "")


def clear() -> None:
    ss.picked, ss.right = [], set()
    ss.editor_version += 1


# ---------- title bar ----------
updated = catalog["retrieved_at"].max()[:10] if len(catalog) else "—"
status = ss.notice or f"{len(catalog)} series · datos actualizados {updated}"
ss.notice = ""
st.markdown(
    f'<div class="titlebar"><strong>Series Dashboard</strong><span>{html.escape(status)}</span></div>',
    unsafe_allow_html=True,
)

# ---------- toolbar ----------
with st.container(key="toolbar"):
    t1, t2, t3, t4, _, t6, t7, t8 = st.columns([1.6, 1.1, 1.1, 2.4, 0.6, 1.1, 1.1, 0.8], vertical_alignment="bottom")
    kind = t1.selectbox("Transformación", list(TRANSFORM_LABELS), format_func=TRANSFORM_LABELS.get, key="kind")
    t2.date_input("Desde", key="start", min_value=date(1950, 1, 1), format="YYYY-MM-DD")
    t3.date_input("Hasta", key="end", min_value=date(1950, 1, 1), format="YYYY-MM-DD")
    with_versions = [s for s in ss.picked if s in versions]
    if with_versions:
        available = [a for a in ADJ_ORDER if any(meta.at[v, "adjustment"] == a for s in with_versions for v in versions[s])]
        current = {meta.at[s, "adjustment"] for s in with_versions}
        ss.adj_all = current.pop() if len(current) == 1 else None
        t4.segmented_control(
            "Ajuste (todas)", available, format_func=ADJ_SHORT.get, key="adj_all", on_change=on_adjust_all,
            help="Cambia cada serie seleccionada a su versión publicada: original, corregida de calendario o desestacionalizada.",
        )
    t8.button("Limpiar", on_click=clear, width="stretch")

left, work = st.columns([1, 2.7], gap="medium")

# ---------- catalog (left pane) ----------
with left, st.container(key="catalog_pane"):
    st.markdown('<div class="pane-title">Bases de datos</div>', unsafe_allow_html=True)
    query = st.text_input("Buscar", placeholder="Buscar código o descripción…", label_visibility="collapsed")
    view = catalog
    for term in query.lower().split():
        text = (view["series_id"] + " " + view["series_name"] + " " + view["source"] + " "
                + view["group"].map(GROUP_LABELS).fillna("") + " " + view["adjustment"].map(ADJ_LABELS).fillna(""))
        view = view[text.str.lower().str.contains(term, regex=False)]
    groups = sorted(view["group"].unique(), key=lambda g: GROUP_LABELS.get(g, g))
    group = st.selectbox("Base", ["*"] + groups, format_func=lambda g: "Todas las bases" if g == "*" else GROUP_LABELS.get(g, g),
                         label_visibility="collapsed")
    if group != "*":
        view = view[view["group"] == group]

    tags = view["measure"].map(lambda m: "" if m == "level" else MEASURE_LABELS[m]) + view.apply(
        lambda r: (" " if r["measure"] != "level" else "") + ADJ_SHORT[r["adjustment"]]
        if r["series_id"] in versions or r["adjustment"] != "nsa" else "", axis=1)
    grid = pd.DataFrame({
        "✓": view["series_id"].isin(ss.picked).values,
        "Código": view["series_id"].values,
        "Descripción": (view["concept"] + view["variant"].map(lambda v: f" · {v}" if v else "")).values,
        "Tipo": tags.values,
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
            "Tipo": st.column_config.TextColumn(width="small", help="Medida publicada por la fuente y versión (original / desestacionalizada)"),
        },
        on_change=on_catalog_edit, args=(key, ids),
    )
    st.markdown(f'<div class="foot">{len(view)} de {len(catalog)} series · {view["concept"].nunique()} conceptos</div>',
                unsafe_allow_html=True)

picked: list[str] = ss.picked
right: set[str] = ss.right


def shown_as(sid: str) -> str:
    m = meta.at[sid, "measure"]
    return TRANSFORM_LABELS[kind] if m == "level" else f"{MEASURE_LABELS[m]} (origen)"


# ---------- data ----------
start = pd.Timestamp(ss.start) if ss.start else None
end = pd.Timestamp(ss.end) if ss.end else None
frames = {}
for sid in picked:
    rows = obs[obs["series_id"] == sid]
    s = pd.Series(rows["value"].values, index=rows["period"].map(to_date)).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    # Series the source already publishes as a rate are never re-transformed.
    k = kind if meta.at[sid, "measure"] == "level" else "level"
    if k == "rebase" and start is not None:
        s = s[s.index >= start]
    s = transform(s, k, meta.at[sid, "frequency"])
    if start is not None:
        s = s[s.index >= start]
    if end is not None:
        s = s[s.index <= end]
    frames[sid] = s
wide = pd.DataFrame(frames).sort_index() if frames else pd.DataFrame()

# ---------- work area: selected grid + chart ----------
with work:
    st.markdown('<div class="pane-title">Series seleccionadas <span class="hint">· la transformación solo se aplica a '
                'series en nivel</span></div>', unsafe_allow_html=True)
    if not picked:
        st.markdown('<p class="muted">Marca series en el catálogo de la izquierda (máx. 8).</p>', unsafe_allow_html=True)
    else:
        widths = [0.25, 1.5, 3.4, 0.4, 1.4, 0.8, 0.7, 1.7, 1.3, 0.5, 0.35]
        with st.container(key="selected"):
            head = st.columns(widths)
            for col, label in zip(head, ["", "Código", "Descripción", "Frec.", "Rango", "Último", "Medida", "Ajuste",
                                         "Mostrado como", "Eje", ""]):
                col.markdown(f'<div class="th"><p>{label}</p></div>', unsafe_allow_html=True)
            for i, sid in enumerate(list(picked)):
                c = st.columns(widths, vertical_alignment="center")
                c[0].markdown(f'<span class="swatch" style="background:{COLORS[i % len(COLORS)]}"></span>', unsafe_allow_html=True)
                c[1].markdown(f'<span class="code">{html.escape(sid)}</span>', unsafe_allow_html=True)
                c[2].markdown(html.escape(describe(sid)))
                c[3].markdown(meta.at[sid, "frequency"])
                c[4].markdown(f'{meta.at[sid, "first_period"]} – {meta.at[sid, "last_period"]}')
                c[5].markdown(fmt(meta.at[sid, "last_value"]))
                c[6].markdown(MEASURE_LABELS[meta.at[sid, "measure"]])
                if sid in versions:
                    ss[f"adj_{sid}"] = sid
                    c[7].segmented_control(
                        "Ajuste", versions[sid], key=f"adj_{sid}", label_visibility="collapsed",
                        format_func=lambda v: ADJ_SHORT[meta.at[v, "adjustment"]],
                        on_change=on_row_adjust, args=(sid,),
                    )
                else:
                    adj = meta.at[sid, "adjustment"]
                    c[7].markdown(f'<span class="muted">{ADJ_SHORT[adj] if adj != "nsa" else "—"}</span>', unsafe_allow_html=True)
                c[8].markdown(shown_as(sid))
                if c[9].button("Der." if sid in right else "Izq.", key=f"ax_{sid}"):
                    right.symmetric_difference_update({sid})
                    st.rerun()
                if c[10].button("✕", key=f"rm_{sid}", help="Quitar"):
                    toggle(sid)
                    ss.editor_version += 1
                    st.rerun()

    # chart (Haver-like: white, black axes, title + units + source line)
    def axis_title(ids: list[str]) -> str:
        labels = {meta.at[s, "unit"] if shown_as(s) == "Nivel" else shown_as(s).replace(" (origen)", "") for s in ids}
        return labels.pop() if len(labels) == 1 else ""

    with st.container(key="chart_box"):
        if picked:
            title = describe(picked[0]) if len(picked) == 1 else f"{len(picked)} series"
            subtitle = "  |  eje dcho.: ".join(
                t for t in (axis_title([s for s in picked if s not in right]), axis_title([s for s in picked if s in right])) if t)
            st.markdown(f'<div class="chart-title">{html.escape(title)}</div><div class="chart-sub">{html.escape(subtitle)}</div>',
                        unsafe_allow_html=True)
        axis = dict(showline=True, linecolor="#111", ticks="outside", tickcolor="#111", zeroline=False)
        fig = go.Figure()
        for i, sid in enumerate(picked):
            s = wide[sid].dropna()
            fig.add_trace(go.Scatter(
                x=s.index, y=s.values, mode="lines", name=sid + (" (dcha.)" if sid in right else ""),
                yaxis="y2" if sid in right else "y", line={"color": COLORS[i % len(COLORS)], "width": 1.8},
                hovertemplate=f"%{{x|%Y-%m}}  %{{y:,.2f}}<extra>{sid}</extra>",
            ))
        any_rate = any(meta.at[s, "measure"] != "level" for s in picked) or kind != "level"
        fig.update_layout(
            height=440, hovermode="x unified", margin={"l": 55, "r": 55 if right else 15, "t": 10, "b": 30},
            paper_bgcolor="#fff", plot_bgcolor="#fff",
            font={"family": "Segoe UI, Arial, sans-serif", "color": "#111", "size": 11},
            showlegend=len(picked) > 1, legend={"orientation": "h", "x": 0, "y": 1.08},
            xaxis={**axis, "type": "date", "showgrid": False},
            yaxis={**axis, "showgrid": True, "gridcolor": "#eceef1", "zeroline": any_rate, "zerolinecolor": "#888"},
            yaxis2={**axis, "overlaying": "y", "side": "right", "showgrid": False, "visible": bool(right)},
        )
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
        if picked:
            sources = sorted({"Excel manual" if meta.at[s, "source"].startswith("Excel:") else meta.at[s, "source"] for s in picked})
            st.markdown(f'<div class="chart-source">Fuente: {html.escape(", ".join(sources))}</div>', unsafe_allow_html=True)

    if picked:
        table = wide.copy()
        table.index = table.index.strftime("%Y-%m")
        table.index.name = "period"
        with st.expander("Datos", expanded=False):
            st.dataframe(table.iloc[::-1], width="stretch")

# ---------- export (toolbar buttons, filled once the data is known) ----------
if picked:
    header = pd.DataFrame(
        [[describe(s) for s in picked],
         [meta.at[s, "unit"] if shown_as(s) == "Nivel" else shown_as(s) for s in picked],
         [meta.at[s, "source"] for s in picked]],
        index=["descripcion", "mostrado_como", "fuente"], columns=picked,
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
    params["s"] = ",".join(s + (":r" if s in right else "") for s in picked)
if kind != "level":
    params["t"] = kind
if ss.start:
    params["from"] = ss.start.strftime("%Y-%m")
if ss.end:
    params["to"] = ss.end.strftime("%Y-%m")
if dict(st.query_params) != params:
    st.query_params.from_dict(params)
