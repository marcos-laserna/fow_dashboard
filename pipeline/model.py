from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

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


def normalize_period(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}", text):
        datetime.strptime(text, "%Y-%m")
        return text
    m = (
        re.fullmatch(r"(\d{4})-?T([1-4])", text, re.I)
        or re.fullmatch(r"(\d{4})Q([1-4])", text, re.I)
        or re.fullmatch(r"(\d{4})-Q([1-4])", text, re.I)
    )
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    if re.fullmatch(r"\d{4}", text):
        return text
    return date.fromisoformat(text).isoformat()


def infer_frequency(period: str) -> str:
    p = normalize_period(period)
    return "Q" if "-Q" in p else "A" if len(p) == 4 else "D" if len(p) == 10 else "M"


def normalize_unit(text: Any) -> str:
    value = str(text or "")
    return re.sub(r"\?+ndice", "Índice", value, flags=re.I)
