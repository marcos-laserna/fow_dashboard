from __future__ import annotations
import re, time, unicodedata, urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable
from ..http import get_json
from ..model import normalize_unit


def _plain(text: Any) -> str:
    value = (
        unicodedata.normalize("NFKD", str(text))
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _period(raw: Any, monthly: bool = False) -> str:
    if isinstance(raw, (int, float)) or str(raw).isdigit():
        stamp = float(raw)
        stamp = stamp * 1000 if stamp < 10_000_000_000 else stamp
        d = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).date()
    else:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    if monthly:
        d = d.replace(day=1)
        return d.strftime("%Y-%m")
    return d.isoformat()


def fetch_ine(
    ine: dict[str, Any], retrieved_at: str, fetch_json: Callable = get_json
) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"nult": 240, "tip": "A"})
    url = (
        f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{ine['table_id']}?{query}"
    )
    payload = fetch_json(url, 60)
    needle = ine["series_name_contains"].casefold()
    matches = [
        s for s in payload if needle in str(s.get("Nombre", "")).strip().casefold()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Se esperaba una única serie INE que contuviera {ine['series_name_contains']!r}; encontradas: {len(matches)}"
        )
    rows = []
    for o in matches[0].get("Data", []):
        if o.get("Fecha") is None or o.get("Valor") in (None, "", ".."):
            continue
        rows.append(
            dict(
                series_id=ine["series_id"],
                series_name=ine["label"],
                source="INE",
                period=_period(o["Fecha"], ine.get("frequency") == "M"),
                value=str(o["Valor"]),
                unit=normalize_unit(ine["unit"]),
                frequency=ine["frequency"],
                retrieved_at=retrieved_at,
            )
        )
    if not rows:
        raise RuntimeError(
            "La serie del INE no contiene observaciones con fecha y valor."
        )
    return rows


def fetch_ine_general_index(
    ine: dict[str, Any], retrieved_at: str, fetch_json: Callable = get_json
) -> list[dict[str, str]]:
    url = (
        f"https://servicios.ine.es/wstempus/js/es/DATOS_TABLA/{ine['table_id']}?tip=AM"
    )
    payload = fetch_json(url, 60)
    if not isinstance(payload, list):
        raise RuntimeError(f"Formato inesperado en la tabla INE {ine['table_id']}.")
    aliases = [_plain(v) for v in ine["match_any"]]
    rejected = {
        "variacion",
        "variaciones",
        "tasa",
        "porcentaje",
        "media",
        "promedio",
        "acumulado",
    }
    ranked = []
    for item in payload:
        name = str(item.get("Nombre", "")).strip()
        plain = _plain(name)
        words = set(plain.split())
        if "indice" not in words or words & rejected:
            continue
        idx = next((i for i, a in enumerate(aliases) if a in plain), None)
        if idx is None:
            continue
        score = (
            100
            + (len(aliases) - idx) * 100
            + (60 if plain.endswith("indice") else 0)
            + (40 if {"nacional", "espana"} & words else 0)
            - len(plain) // 100
        )
        ranked.append((score, item))
    if not ranked:
        raise RuntimeError(
            f"No se identificó el índice general en INE {ine['table_id']}."
        )
    best = max(x[0] for x in ranked)
    chosen = [x[1] for x in ranked if x[0] == best]
    if len(chosen) != 1:
        raise RuntimeError(f"Selección ambigua en INE {ine['table_id']}.")
    return _convert(chosen[0], ine, retrieved_at, normalize_unit("Índice (2021=100)"))


def _convert(item, spec, retrieved_at, unit):
    rows = []
    for o in item.get("Data", []):
        raw = o.get("Fecha")
        val = o.get("Valor")
        if raw is None or val in (None, "", ".."):
            continue
        rows.append(
            dict(
                series_id=spec["series_id"],
                series_name=spec["label"],
                source="INE",
                period=_period(raw, True),
                value=str(val),
                unit=unit,
                frequency="M",
                retrieved_at=retrieved_at,
            )
        )
    if not rows:
        raise RuntimeError(
            f"La serie general de INE {spec['table_id']} no contiene observaciones."
        )
    return rows


def fetch_catalog_table(
    catalog: dict[str, Any],
    retrieved_at: str,
    full_history: bool = False,
    fetch_json: Callable = get_json,
) -> list[dict[str, str]]:
    params = {"tip": "AM"}
    if not full_history:
        params["nult"] = 3
    url = f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{catalog['table_id']}?{urllib.parse.urlencode(params)}"
    payload = fetch_json(url, 90)
    if not isinstance(payload, list):
        raise RuntimeError(f"Formato inesperado para tabla INE {catalog['table_id']}.")
    wanted = {s["series_id"]: s for s in catalog["series"]}
    by_name = {_plain(s["label"]): s for s in catalog["series"]}
    rows = []
    seen = set()
    for item in payload:
        spec = wanted.get(str(item.get("COD", ""))) or by_name.get(
            _plain(item.get("Nombre", ""))
        )
        if not spec:
            continue
        seen.add(spec["series_id"])
        for o in item.get("Data", []):
            raw = o.get("Fecha")
            val = o.get("Valor")
            if raw is None or val in (None, "", ".."):
                continue
            rows.append(
                dict(
                    series_id=spec["series_id"],
                    series_name=str(item.get("Nombre", spec.get("label", ""))).strip(),
                    source="INE",
                    period=_period(raw, True),
                    value=str(val),
                    unit=normalize_unit(spec.get("unit", "INE")),
                    frequency="M",
                    retrieved_at=retrieved_at,
                )
            )
    missing = set(wanted) - seen
    if missing:
        print(
            f"Aviso: la tabla INE {catalog['table_id']} no devolvió {len(missing)} series del catálogo {catalog.get('family', '')}: {sorted(missing)}"
        )
    print(
        f"Tabla INE {catalog['table_id']}: {len(seen)}/{len(wanted)} series encontradas; {len(rows)} observaciones descargadas."
    )
    time.sleep(0.5)
    return rows
