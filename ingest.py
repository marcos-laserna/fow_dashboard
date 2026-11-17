#!/usr/bin/env python3
"""Download the configured INE series and merge manually supplied Excel data."""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "data" / "series.json"
MANUAL_DIR = ROOT / "data" / "manual"
OUTPUT_PATH = ROOT / "data" / "processed" / "observations.csv"
FIELDS = (
    "series_id",
    "series_name",
    "source",
    "period",
    "value",
    "unit",
    "frequency",
    "retrieved_at",
)


def read_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def normalize_period(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError("El período está vacío.")
    if len(text) == 7 and text[4] == "-":
        datetime.strptime(text, "%Y-%m")
        return text
    if len(text) == 6 and text[4] == "T" and text[5] in "1234":
        return text
    return date.fromisoformat(text).isoformat()


def fetch_ine(ine: dict[str, Any], retrieved_at: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"nult": 240, "tip": "A"})
    url = f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{ine['table_id']}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "FutureOfWorkData/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudieron descargar los datos del INE: {exc}") from exc

    needle = ine["series_name_contains"].casefold()
    matches = [
        series for series in payload
        if needle in str(series.get("Nombre", "")).strip().casefold()
    ]
    if len(matches) != 1:
        names = [str(item.get("Nombre", "")).strip() for item in matches]
        raise RuntimeError(
            f"Se esperaba una única serie INE que contuviera {ine['series_name_contains']!r}; "
            f"encontradas: {len(matches)}. Coincidencias: {names}"
        )

    series = matches[0]
    rows = []
    for observation in series.get("Data", []):
        raw_date = observation.get("Fecha")
        raw_value = observation.get("Valor")
        if raw_date is None or raw_value is None:
            continue
        obs_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        rows.append({
            "series_id": ine["series_id"],
            "series_name": ine["label"],
            "source": "INE",
            "period": obs_date.date().isoformat(),
            "value": str(raw_value),
            "unit": ine["unit"],
            "frequency": ine["frequency"],
            "retrieved_at": retrieved_at,
        })
    if not rows:
        raise RuntimeError("La serie del INE no contiene observaciones con fecha y valor.")
    return rows


def read_manual_files(settings: dict[str, Any], retrieved_at: str) -> list[dict[str, str]]:
    manual = settings["manual"]
    rows: list[dict[str, str]] = []
    for path in sorted(MANUAL_DIR.glob("*.xlsx")):
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook["datos"] if "datos" in workbook.sheetnames else workbook.active
            values = sheet.iter_rows(values_only=True)
            header = next(values, None)
            if not header:
                raise ValueError(f"{path.name}: la hoja no tiene encabezados.")
            columns = {
                str(name).strip().casefold(): index
                for index, name in enumerate(header)
                if name is not None
            }
            if not {"period", "value"}.issubset(columns):
                raise ValueError(f"{path.name}: se requieren columnas period y value.")
            for line_number, cells in enumerate(values, start=2):
                if not cells or all(cell is None for cell in cells):
                    continue
                try:
                    period = normalize_period(cells[columns["period"]])
                    raw_value = cells[columns["value"]]
                    if raw_value is None or isinstance(raw_value, bool):
                        raise ValueError("value está vacío o no es numérico")
                    number = float(raw_value)
                    if not (number == number and abs(number) != float("inf")):
                        raise ValueError("value no es finito")
                    series_name = _cell(cells, columns, "series_name") or manual["default_label"]
                    unit = _cell(cells, columns, "unit") or manual["default_unit"]
                except (ValueError, TypeError, IndexError) as exc:
                    raise ValueError(f"{path.name}, fila {line_number}: {exc}") from exc
                rows.append({
                    "series_id": manual["default_series_id"],
                    "series_name": str(series_name),
                    "source": f"Excel:{path.name}",
                    "period": period,
                    "value": str(number),
                    "unit": str(unit),
                    "frequency": _frequency(period),
                    "retrieved_at": retrieved_at,
                })
        finally:
            workbook.close()
    return rows


def _cell(cells: tuple[Any, ...], columns: dict[str, int], name: str) -> Any:
    index = columns.get(name)
    return cells[index] if index is not None and index < len(cells) else None


def _frequency(period: str) -> str:
    if "-T" in period:
        return "Q"
    return "D" if len(period) == 10 else "M"


def merge_write(rows: list[dict[str, str]]) -> int:
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing[(row["series_id"], row["period"])] = row
    for row in rows:
        existing[(row["series_id"], row["period"])] = row

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda item: (item["series_id"], item["period"])))
    return len(rows)


def main() -> None:
    config = read_config()
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = fetch_ine(config["ine"], retrieved_at)
    rows.extend(read_manual_files(config, retrieved_at))
    updated = merge_write(rows)
    print(f"Observaciones recibidas: {updated}")
    print(f"Archivo actualizado: {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
