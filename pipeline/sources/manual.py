from __future__ import annotations
import math, re, unicodedata
from pathlib import Path
from typing import Any
from openpyxl import load_workbook
from ..model import normalize_period, infer_frequency, normalize_unit


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", "_", s).strip("_") or "SERIE"


def read_manual_files(
    settings: dict[str, Any], retrieved_at: str, manual_dir: Path
) -> list[dict[str, str]]:
    defaults = settings.get("manual", {})
    rows = []
    for path in sorted(manual_dir.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb["datos"] if "datos" in wb.sheetnames else wb[wb.sheetnames[0]]
            raw = list(ws.iter_rows(values_only=True))
            if not raw:
                continue
            headers = [
                str(x).strip().casefold() if x is not None else "" for x in raw[0]
            ]
            columns = {h: i for i, h in enumerate(headers) if h}
            long = {"period", "value"} <= set(columns)
            if not long and (not headers or headers[0] != "period"):
                raise ValueError(
                    f"{path.name}: se requiere encabezado period y value o diseño ancho"
                )
            grouped = {}
            for rn, cells in enumerate(raw[1:], 2):
                if not cells or all(v is None for v in cells):
                    continue
                try:
                    period = normalize_period(
                        cells[columns["period"]] if long else cells[0]
                    )
                    entries = []
                    if long:
                        val = cells[columns["value"]]
                        name = (
                            cells[columns["series_name"]]
                            if "series_name" in columns
                            and columns["series_name"] < len(cells)
                            else None
                        ) or defaults.get("default_label", "Serie del Excel")
                        sid = (
                            cells[columns["series_id"]]
                            if "series_id" in columns
                            and columns["series_id"] < len(cells)
                            else None
                        )
                        unit = (
                            cells[columns["unit"]]
                            if "unit" in columns and columns["unit"] < len(cells)
                            else None
                        )
                        entries = [(str(sid or name), str(name), unit, val)]
                    else:
                        entries = [
                            (str(h), str(h), None, cells[i] if i < len(cells) else None)
                            for i, h in enumerate(raw[0][1:], 1)
                            if h is not None and str(h).strip()
                        ]
                    for key, name, unit, val in entries:
                        if val is None:
                            continue
                        if isinstance(val, bool):
                            raise ValueError("value no es numérico")
                        number = float(val)
                        if not math.isfinite(number):
                            raise ValueError("value no es finito")
                        sid = "XL_" + _slug(path.stem) + "_" + _slug(str(key))
                        grouped.setdefault(sid, (name, unit, []))[2].append(
                            (period, number)
                        )
                except (ValueError, TypeError, IndexError) as exc:
                    raise ValueError(f"{path.name}, fila {rn}: {exc}") from exc
            for sid, (name, unit, obs) in grouped.items():
                for period, value in obs:
                    rows.append(
                        dict(
                            series_id=sid,
                            series_name=name,
                            source="Excel:" + path.name,
                            period=period,
                            value=str(value),
                            unit=normalize_unit(
                                unit
                                if unit is not None
                                else defaults.get("default_unit", "")
                            ),
                            frequency=infer_frequency(period),
                            retrieved_at=retrieved_at,
                        )
                    )
        finally:
            wb.close()
    return rows
