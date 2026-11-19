"""Series Dashboard — Streamlit version of the Haver-style series browser."""

from __future__ import annotations

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
TRANSFORMS = {
    "Nivel": "level", "% periodo anterior": "pct", "% interanual": "yoy",
    "Diferencia": "diff", "Base 100 = inicio": "rebase",
}
YOY_LAG = {"M": 12, "Q": 4, "A": 1}

st.set_page_config(page_title="Series Dashboard", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 1.2rem;}
    h1 {font-size: 1.25rem !important; color: #0b2e6b;}
    [data-testid="stSidebar"] {border-right: 1px solid #c9ced6;}
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = pd.read_csv(DATA / "catalog.csv", dtype=str).fillna("")
    catalog.loc[catalog["concept"] == "", "concept"] = catalog["series_name"]
    catalog.loc[catalog["measure"] == "", "measure"] = "level"
    obs = pd.read_csv(DATA / "observations.csv", dtype={"period": str, "series_id": str})
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    return catalog, obs


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


def describe(sid: str) -> str:
    variant = meta.at[sid, "variant"]
    return meta.at[sid, "concept"] + (f" · {variant}" if variant else "")


# ---------- sidebar: database tree (group → concept → series) ----------
with st.sidebar:
    st.markdown("**BASES DE DATOS**")
    query = st.text_input("Buscar código o descripción", placeholder="p. ej. paro, IPC general…")
    view = catalog
    for term in query.lower().split():
        text = (view["series_id"] + " " + view["series_name"] + " " + view["source"]).str.lower()
        view = view[text.str.contains(term, regex=False)]
    groups = sorted(view["group"].unique())
    group = st.selectbox("Base", ["(todas)"] + groups, format_func=lambda g: GROUP_LABELS.get(g, g))
    if group != "(todas)":
        view = view[view["group"] == group]
    concepts = sorted(view["concept"].unique())
    concept = st.selectbox("Concepto", ["(todos)"] + concepts)
    if concept != "(todos)":
        view = view[view["concept"] == concept]
    st.caption(f"{len(view)} series · {view['concept'].nunique()} conceptos")

    grid = view.assign(Medida=view["measure"].map(MEASURE_LABELS))[
        ["series_id", "concept", "variant", "Medida", "frequency", "last_period"]
    ]
    grid.columns = ["Código", "Concepto", "Variante", "Medida", "Frec.", "Fin"]
    st.dataframe(grid, hide_index=True, height=300)

    if "picked" not in st.session_state:
        st.session_state.picked = [s for s in ("EUR_UNE_RT_M_ES", "EUR_UNE_RT_M_EA") if s in meta.index]
    options = list(dict.fromkeys(list(view["series_id"]) + st.session_state.picked))
    st.multiselect(
        "Series seleccionadas", options, key="picked", max_selections=MAX_SERIES,
        format_func=lambda sid: f"{sid} — {describe(sid)}"[:90],
        help="El desplegable muestra las series que cumplen la búsqueda, la base y el concepto.",
    )

picked = st.session_state.picked

# ---------- toolbar ----------
st.title("Series Dashboard")
updated = catalog["retrieved_at"].max()[:10] if len(catalog) else "—"
st.caption(f"{len(catalog)} series · datos actualizados {updated} · INE, Eurostat y Excel manuales")

c1, c2, c3, c4 = st.columns([2, 1, 1, 3])
kind_label = c1.selectbox("Transformación (solo series en nivel)", list(TRANSFORMS), key="kind")
kind = TRANSFORMS[kind_label]
start = c2.date_input("Desde", date(2015, 1, 1), min_value=date(1950, 1, 1))
end = c3.date_input("Hasta", date.today(), min_value=date(1950, 1, 1))
right = c4.multiselect("Eje derecho", picked, key="right")

if not picked:
    st.info("Elige series en el panel de la izquierda.")
    st.stop()


def shown_as(sid: str) -> str:
    m = meta.at[sid, "measure"]
    return kind_label if m == "level" else f"{MEASURE_LABELS[m]} (origen)"


# ---------- data ----------
frames = {}
for sid in picked:
    rows = obs[obs["series_id"] == sid]
    s = pd.Series(rows["value"].values, index=rows["period"].map(to_date)).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    # Series the source already publishes as a rate are never re-transformed.
    k = kind if meta.at[sid, "measure"] == "level" else "level"
    if k == "rebase":
        s = s[s.index >= pd.Timestamp(start)]
    s = transform(s, k, meta.at[sid, "frequency"])
    frames[sid] = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
wide = pd.DataFrame(frames).sort_index()

# ---------- selected grid ----------
sel = pd.DataFrame({
    "Código": picked,
    "Descripción": [describe(s) for s in picked],
    "Frec.": [meta.at[s, "frequency"] for s in picked],
    "Inicio": [meta.at[s, "first_period"] for s in picked],
    "Fin": [meta.at[s, "last_period"] for s in picked],
    "Último": [pd.to_numeric(meta.at[s, "last_value"], errors="coerce") for s in picked],
    "Medida": [MEASURE_LABELS[meta.at[s, "measure"]] for s in picked],
    "Mostrado como": [shown_as(s) for s in picked],
    "Eje": ["Der." if s in right else "Izq." for s in picked],
})
st.dataframe(sel, hide_index=True, width="stretch", key="selected_grid")


# ---------- chart (Haver-like: white, black axes, title + source line) ----------
def axis_title(ids: list[str]) -> str:
    labels = {meta.at[s, "unit"] if shown_as(s) == "Nivel" else shown_as(s).replace(" (origen)", "") for s in ids}
    return labels.pop() if len(labels) == 1 else ""


title = describe(picked[0]) if len(picked) == 1 else f"{len(picked)} series"
subtitle = "  |  eje dcho.: ".join(
    t for t in (axis_title([s for s in picked if s not in right]), axis_title(right)) if t
)
st.markdown(f"**{title}**  \n<span style='color:#5f6670'>{subtitle}</span>", unsafe_allow_html=True)

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
    height=460, hovermode="x unified", margin={"l": 55, "r": 55 if right else 15, "t": 10, "b": 30},
    paper_bgcolor="#fff", plot_bgcolor="#fff", font={"color": "#111", "size": 11},
    showlegend=len(picked) > 1, legend={"orientation": "h", "x": 0, "y": 1.08},
    xaxis={**axis, "showgrid": False},
    yaxis={**axis, "showgrid": True, "gridcolor": "#eceef1", "zeroline": any_rate, "zerolinecolor": "#888"},
    yaxis2={**axis, "overlaying": "y", "side": "right", "showgrid": False, "visible": bool(right)},
)
st.plotly_chart(fig, width="stretch")
sources = sorted({"Excel manual" if meta.at[s, "source"].startswith("Excel:") else meta.at[s, "source"] for s in picked})
st.caption(f"Fuente: {', '.join(sources)}")

# ---------- table & export ----------
table = wide.copy()
table.index = table.index.strftime("%Y-%m-%d")
table.index.name = "period"
with st.expander("Datos", expanded=False):
    st.dataframe(table.iloc[::-1], width="stretch")

header = pd.DataFrame(
    [[describe(s) for s in picked],
     [meta.at[s, "unit"] if shown_as(s) == "Nivel" else shown_as(s) for s in picked],
     [meta.at[s, "source"] for s in picked]],
    index=["descripcion", "mostrado_como", "fuente"], columns=picked,
)
export = pd.concat([header, table.astype(object)])
export.index.name = "period"
stamp = date.today().isoformat()
d1, d2, _ = st.columns([1, 1, 4])
d1.download_button("Exportar CSV", export.to_csv().encode("utf-8-sig"), f"series_{stamp}.csv", "text/csv")
buf = io.BytesIO()
export.to_excel(buf, sheet_name="datos")
d2.download_button("Exportar Excel", buf.getvalue(), f"series_{stamp}.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
