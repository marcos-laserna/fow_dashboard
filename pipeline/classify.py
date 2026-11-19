"""Group similar series: derive concept / variant / measure from the series name.

- concept: what the series measures, shared by its siblings
  ("Nacional. Índice general").
- variant: what distinguishes it inside the concept ("Variación anual",
  "Ajustado calendario (60289)", "España").
- measure: whether the source already applied a transformation:
  level | pct (vs previous period) | yoy (vs same period last year) | ytd.
  Only `level` series should be transformed again by the dashboards.
"""

from __future__ import annotations

import re
import unicodedata

MEASURES = ("level", "pct", "yoy", "ytd")


def _plain(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )


def measure_of(variant: str) -> str:
    v = _plain(variant)
    if "lo que va de ano" in v:
        return "ytd"
    if "variacion mensual" in v or "tasa mensual" in v:
        return "pct"
    if "variacion anual" in v or "tasa anual" in v:
        return "yoy"
    return "level"


def classify(name: str) -> dict[str, str]:
    name = name.strip().rstrip(".").strip()
    # INE: "<concept>. <Índice | Variación mensual | ...>"
    head, sep, tail = name.rpartition(". ")
    if sep and re.match(r"(?i)^(índice|indice|variaci[oó]n)", tail):
        concept, variant = head, tail
    elif " · " in name:  # "IASS · Ajustado calendario (60289)"
        concept, variant = name.split(" · ", 1)
    elif " — " in name:  # "Tasa de paro (SA) — España"
        concept, variant = name.split(" — ", 1)
    else:
        concept, variant = name, ""
    measure = measure_of(variant) if variant else measure_of(concept)
    return {"concept": concept.strip(), "variant": variant.strip(), "measure": measure}
