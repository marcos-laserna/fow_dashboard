from __future__ import annotations
import urllib.parse
from typing import Any, Callable
from ..http import get_json
from ..model import normalize_period, normalize_unit

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def parse_jsonstat(
    payload: dict[str, Any], spec: dict[str, Any], retrieved_at: str
) -> list[dict[str, str]]:
    ids = payload.get("id", [])
    sizes = payload.get("size", [])
    dims = payload.get("dimension", {})
    if not ids or len(ids) != len(sizes):
        raise ValueError("JSON-stat sin dimensiones válidas")
    time_dim = next(
        (i for i, k in enumerate(ids) if k.lower() in ("time", "time_period")), None
    )
    if time_dim is None:
        raise ValueError("JSON-stat sin dimensión temporal")
    cats = []
    for key, size in zip(ids, sizes):
        idx = dims.get(key, {}).get("category", {}).get("index", {})
        if isinstance(idx, list):
            vals = idx
        else:
            vals = [k for k, _ in sorted(idx.items(), key=lambda x: x[1])]
        cats.append(vals)
        if len(vals) != size:
            raise ValueError(f"Dimensión {key} inválida")
    combinations = 1
    for i, size in enumerate(sizes):
        if i != time_dim:
            combinations *= size
    if combinations > 1:
        raise ValueError(
            "La consulta Eurostat deja más de una combinación de dimensiones no temporales"
        )
    data = payload.get("value", {})
    out = []
    total = 1
    for size in sizes:
        total *= size
    iterator = data.items() if isinstance(data, dict) else enumerate(data)
    for flat, val in iterator:
        if val is None:
            continue
        n = int(flat)
        coords = [0] * len(sizes)
        for i in range(len(sizes) - 1, -1, -1):
            coords[i] = n % sizes[i]
            n //= sizes[i]
        label = cats[time_dim][coords[time_dim]]
        period = normalize_period(
            label.replace("M", "-") if len(label) == 7 and label[4] == "M" else label
        )
        out.append(
            dict(
                series_id=spec["series_id"],
                series_name=spec["label"],
                source="Eurostat",
                period=period,
                value=str(val),
                unit=normalize_unit(spec.get("unit", "")),
                frequency=spec.get("frequency", "M"),
                retrieved_at=retrieved_at,
            )
        )
    return out


def fetch_eurostat(
    spec: dict[str, Any], retrieved_at: str, fetch_json: Callable = get_json
) -> list[dict[str, str]]:
    params = {
        "format": "JSON",
        "lang": "EN",
        "sinceTimePeriod": "2000-01",
        **spec.get("filters", {}),
    }
    url = (
        BASE
        + urllib.parse.quote(spec["dataset"])
        + "?"
        + urllib.parse.urlencode(params)
    )
    return parse_jsonstat(fetch_json(url, 90), spec, retrieved_at)
