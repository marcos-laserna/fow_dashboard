from __future__ import annotations
import csv
from pathlib import Path
from .classify import classify
from .model import FIELDS, normalize_unit

CATALOG_FIELDS = (
    "series_id",
    "series_name",
    "source",
    "group",
    "concept",
    "variant",
    "measure",
    "adjustment",
    "base",
    "stem",
    "frequency",
    "unit",
    "first_period",
    "last_period",
    "n_obs",
    "last_value",
    "retrieved_at",
)


def merge_write(
    rows: list[dict[str, str]],
    output_path: Path,
    catalog_path: Path,
    groups: dict[str, str] | None = None,
    previous_catalog: Path | None = None,
    meta: dict[str, dict[str, str]] | None = None,
) -> int:
    """meta: optional per-series overrides of concept/variant/measure/adjustment/base/stem
    (from config)."""
    groups = groups or {}
    meta = meta or {}
    previous = {}
    if previous_catalog and previous_catalog.exists():
        with previous_catalog.open(newline="", encoding="utf-8-sig") as f:
            previous = {
                r["series_id"]: r.get("group", "other") for r in csv.DictReader(f)
            }
    existing = {}
    if output_path.exists():
        with output_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (
                    row.get("source", "").startswith("Excel:")
                    or row.get("series_id") == "manual_series"
                ):
                    continue
                row["unit"] = normalize_unit(row.get("unit", ""))
                if row.get("frequency") == "M" and len(row["period"]) == 10:
                    row["period"] = row["period"][:7]
                existing[(row["series_id"], row["period"])] = row
    for row in rows:
        item = dict(row)
        item["unit"] = normalize_unit(item.get("unit", ""))
        existing[(item["series_id"], item["period"])] = item
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(existing.values(), key=lambda r: (r["series_id"], r["period"]))
    with output_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)
    by = {}
    for r in ordered:
        by.setdefault(r["series_id"], []).append(r)
    catalog = []
    for sid, obs in by.items():
        obs.sort(key=lambda r: r["period"])
        last = obs[-1]
        info = {**classify(last["series_name"]), **meta.get(sid, {})}
        catalog.append(
            dict(
                **info,
                series_id=sid,
                series_name=last["series_name"],
                source=last["source"],
                group=groups.get(
                    sid,
                    previous.get(
                        sid,
                        "manual" if last["source"].startswith("Excel:") else "other",
                    ),
                ),
                frequency=last["frequency"],
                unit=normalize_unit(last["unit"]),
                first_period=obs[0]["period"],
                last_period=last["period"],
                n_obs=len(obs),
                last_value=last["value"],
                retrieved_at=last["retrieved_at"],
            )
        )
    catalog.sort(key=lambda r: (r["group"], r["concept"], r["series_id"]))
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with catalog_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CATALOG_FIELDS)
        w.writeheader()
        w.writerows(catalog)
    return len(rows)
