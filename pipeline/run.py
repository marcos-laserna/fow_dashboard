from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from .sources.ine import fetch_ine, fetch_ine_general_index, fetch_catalog_table
from .sources.eurostat import fetch_eurostat
from .sources.manual import read_manual_files
from .store import merge_write

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    config = json.loads((ROOT / "data/series.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = []
    groups = {}
    meta = {}  # config overrides for concept / variant / measure
    remote = config.get("sources", [])
    failures = 0
    for spec in remote:
        # Assign groups from config up front so series that a source omits in
        # this run (but that exist from earlier runs) keep their group.
        group = spec.get("group", spec.get("family", "other"))
        for item in spec.get("series", []):
            groups[item["series_id"]] = group
        if "series_id" in spec:
            groups[spec["series_id"]] = group
        override = {k: spec[k] for k in ("concept", "variant", "measure") if k in spec}
        if override:
            for sid in [spec.get("series_id")] + [
                i["series_id"] for i in spec.get("series", [])
            ]:
                if sid:
                    meta[sid] = override
        try:
            typ = spec["type"]
            if typ == "ine_series":
                data = fetch_ine(spec, now)
            elif typ == "ine_general_index":
                data = fetch_ine_general_index(spec, now)
            elif typ == "ine_catalog":
                data = fetch_catalog_table(
                    spec,
                    now,
                    os.environ.get("INE_FULL_HISTORY", "0").lower()
                    in {"1", "true", "yes"},
                )
            elif typ == "eurostat":
                data = fetch_eurostat(spec, now)
            else:
                raise ValueError(f"Tipo de fuente desconocido: {typ}")
            rows.extend(data)
            for row in data:
                groups[row["series_id"]] = group
        except Exception as exc:
            failures += 1
            print(
                f"Aviso: falló la fuente {spec.get('series_id', spec.get('table_id', '?'))}: {exc}"
            )
    try:
        rows.extend(read_manual_files(config, now, ROOT / "data/manual"))
    except Exception as exc:
        # Excel rows are rebuilt from scratch on every write, so writing after a
        # failed read would silently drop every manual series. Abort instead.
        print(f"Error en archivos Excel; no se guarda nada: {exc}")
        return 1
    for row in rows:
        if row["source"].startswith("Excel:"):
            groups[row["series_id"]] = "manual"
    merge_write(
        rows,
        ROOT / "data/processed/observations.csv",
        ROOT / "data/processed/catalog.csv",
        groups,
        ROOT / "data/processed/catalog.csv",
        meta,
    )
    print(f"Observaciones recibidas: {len(rows)}")
    if remote and failures == len(remote):
        return 1
    return 0
