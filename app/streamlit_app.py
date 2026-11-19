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
GROUP_LABELS = {
    "retail": "Ventas minoristas", "ipc": "IPC · precios", "icm": "ICM · comercio minorista",
    "iass": "IASS · servicios", "ipi": "IPI · industria", "eurostat": "Eurostat · UE",
    "manual": "Excel manuales", "other": "Otros",
}
TRANSFORMS = {
    "Nivel": "level", "% periodo anterior": "pct", "% interanual": "yoy",
    "Diferencia": "diff", "Base 100 = inicio": "rebase",
}
YOY_LAG = {"M": 12, "Q": 4, "A": 1}

st.set_page_config(page_title="Series Dashboard", layout="wide")


@st.cache_data(ttl=3600)
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = pd.read_csv(DATA / "catalog.csv", dtype=str)
    obs = pd.read_csv(DATA / "observations.csv", dtype={"period": str, "series_id": str})
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    return catalog, obs


def to_date(period: str) -> pd.Timestamp:
    if len(period) == 7 and period[4] == "-" and period[5] != "Q":
        return pd.Timestamp(f"{period}-01")
    if "-Q" in period:
        return pd.Timestamp(year=int(period[:4]), month=(int(period[-1]) - 1) * 3 + 1, day=1)
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
        lag = YOY_LAG.get(freq)
        if not lag:
            return s * float("nan")
        # Match by calendar period (not position) so gaps don't misalign.
        months = {"M": 1, "Q": 3, "A": 12}[freq] * lag
        prev = s.copy()
        prev.index = prev.index + pd.DateOffset(months=months)
        return (s / prev.reindex(s.index) - 1) * 100
    if kind == "rebase":
        first = s.dropna()
        return s / first.iloc[0] * 100 if len(first) and first.iloc[0] != 0 else s * float("nan")
    return s


catalog, obs = load()
catalog["label"] = catalog["series_id"] + " — " + catalog["series_name"]

# ---------- sidebar: catalog ----------
with st.sidebar:
    st.header("Catálogo")
    groups = sorted(catalog["group"].unique())
    group = st.selectbox("Grupo", ["(todos)"] + groups, format_func=lambda g: GROUP_LABELS.get(g, g))
    query = st.text_input("Buscar código o nombre")
    view = catalog if group == "(todos)" else catalog[catalog["group"] == group]
    for term in query.lower().split():
        view = view[view["label"].str.lower().str.contains(term, regex=False)]
    st.caption(f"{len(view)} de {len(catalog)} series")

    default = [s for s in ("EUR_UNE_RT_M_ES", "EUR_UNE_RT_M_EA") if s in set(catalog["series_id"])]
    if "picked" not in st.session_state:
        st.session_state.picked = default
    options = sorted(set(view["series_id"]) | set(st.session_state.picked))
    labels = dict(zip(catalog["series_id"], catalog["label"]))
    picked = st.multiselect(
        "Series", options, key="picked", max_selections=MAX_SERIES,
        format_func=lambda sid: labels.get(sid, sid)[:80],
    )
    st.dataframe(
        view[["series_id", "series_name", "source", "frequency", "last_period", "last_value"]],
        hide_index=True, height=320,
    )

# ---------- controls ----------
st.title("Series Dashboard")
updated = catalog["retrieved_at"].max()[:10] if len(catalog) else "—"
st.caption(f"{len(catalog)} series · actualizado {updated} · fuentes: INE, Eurostat y Excel manuales")

c1, c2, c3, c4 = st.columns([2, 1, 1, 3])
kind = TRANSFORMS[c1.selectbox("Transformación", list(TRANSFORMS), key="kind")]
start = c2.date_input("Desde", date(2015, 1, 1), min_value=date(1950, 1, 1))
end = c3.date_input("Hasta", date.today(), min_value=date(1950, 1, 1))
right = c4.multiselect("Eje derecho", picked, key="right")

if not picked:
    st.info("Selecciona series en el catálogo de la izquierda.")
    st.stop()

# ---------- build data ----------
meta = catalog.set_index("series_id")
frames = {}
for sid in picked:
    rows = obs[obs["series_id"] == sid]
    s = pd.Series(rows["value"].values, index=rows["period"].map(to_date)).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if kind == "rebase":
        s = s[s.index >= pd.Timestamp(start)]
    s = transform(s, kind, meta.at[sid, "frequency"])
    frames[sid] = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
wide = pd.DataFrame(frames).sort_index()


def axis_title(ids: list[str]) -> str:
    if kind != "level":
        return next(k for k, v in TRANSFORMS.items() if v == kind)
    units = {meta.at[sid, "unit"] for sid in ids if isinstance(meta.at[sid, "unit"], str)}
    return units.pop() if len(units) == 1 else ""


fig = go.Figure()
for sid in picked:
    s = wide[sid].dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", name=labels[sid][:90],
        yaxis="y2" if sid in right else "y",
        line={"dash": "dot" if sid in right else "solid", "width": 2},
        hovertemplate=f"%{{x|%Y-%m}}  %{{y:,.2f}}<extra>{sid}</extra>",
    ))
fig.update_layout(
    height=520, hovermode="x unified", margin={"l": 60, "r": 60, "t": 20, "b": 40},
    legend={"orientation": "h", "y": -0.15},
    yaxis={"title": axis_title([s for s in picked if s not in right])},
    yaxis2={"title": axis_title(right), "overlaying": "y", "side": "right",
            "showgrid": False, "visible": bool(right)},
)
st.plotly_chart(fig, width="stretch")

# ---------- table & downloads ----------
table = wide.copy()
table.index = table.index.strftime("%Y-%m-%d")
table.index.name = "period"
with st.expander("Datos", expanded=False):
    st.dataframe(table.iloc[::-1], width="stretch")

header = pd.DataFrame(
    [[meta.at[s, "series_name"] for s in picked],
     [meta.at[s, "unit"] if kind == "level" else kind for s in picked]],
    index=["nombre", "unidad"], columns=picked,
)
export = pd.concat([header, table.astype(object)])
export.index.name = "period"
stamp = date.today().isoformat()
d1, d2, _ = st.columns([1, 1, 4])
d1.download_button("Descargar CSV", export.to_csv().encode("utf-8-sig"),
                   f"series_{stamp}.csv", "text/csv")
buf = io.BytesIO()
export.to_excel(buf, sheet_name="datos")
d2.download_button("Descargar Excel", buf.getvalue(), f"series_{stamp}.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
