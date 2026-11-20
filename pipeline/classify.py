"""Group similar series: derive concept / variant / measure from the series name.

- concept: what the series measures, shared by its siblings
  ("Nacional. Índice general").
- variant: what distinguishes it inside the concept ("Variación anual",
  "Ajustado calendario (60289)", "España").
- measure: whether the source already applied a transformation:
  level | pct (vs previous period) | yoy (vs same period last year) | ytd.
  Only `level` series should be transformed again by the dashboards.
- adjustment: which published version of the series this is:
  nsa (original) | cal (calendar adjusted) | sa (seasonally and calendar
  adjusted) | trend. Taken from the name; never computed by us.
- base: the name with the adjustment wording (and INE table codes) removed.
  Series sharing group + base are versions of the same series, so the
  dashboards can switch between them.
"""

from __future__ import annotations

import re
import unicodedata

MEASURES = ("level", "pct", "yoy", "ytd")
ADJUSTMENTS = ("nsa", "cal", "sa", "trend")

# Most specific first: "ajustado calendario y estacionalidad" must win over
# "ajustado calendario". Matched against the accent-free, lower-case name.
_DATA = r"\b(?:datos |serie )?"  # INE often writes "Datos corregidos de ..."
_FIXED = r"(?:ajustad[oa]s?|corregid[oa]s?)"
_ADJUSTMENT_PATTERNS = (
    ("trend", _DATA + r"(?:de )?tendencia(?: ciclo)?\b"),
    (
        "sa",
        _DATA + _FIXED + r"(?: de)?(?: efectos)?(?: de)? calendario y"
        r"(?: de)? (?:estacionalidad|efectos estacionales)\b"
        r"|" + _DATA + _FIXED + r"(?: de)? (?:estacionalidad|efectos estacionales)"
        r"(?: y(?: de)?(?: efectos de)? calendario)?\b"
        r"|\b(?:serie )?desestacionalizad[oa]s?\b|\bcvec\b|\(sa\)|\bseasonally adjusted\b",
    ),
    (
        "cal",
        _DATA + _FIXED + r"(?: de)?(?: efectos)?(?: de)? calendario\b"
        r"|\(cal\)|\bcalendar adjusted\b",
    ),
    ("nsa", _DATA + r"original(?:es)?\b|\(nsa\)"),
)


def _plain(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )


def adjustment_of(name: str) -> str:
    plain = _plain(name)
    for code, pattern in _ADJUSTMENT_PATTERNS:
        if re.search(pattern, plain):
            return code
    return "nsa"


def base_of(name: str) -> str:
    """Accent-free name without adjustment wording, table codes or punctuation."""
    plain = _plain(name)
    for _, pattern in _ADJUSTMENT_PATTERNS:
        plain = re.sub(pattern, " ", plain)
    plain = re.sub(r"\(\d{3,}\)", " ", plain)  # INE table codes: "(60288)"
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


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
    return {
        "concept": concept.strip(),
        "variant": variant.strip(),
        "measure": measure,
        "adjustment": adjustment_of(name),
        "base": base_of(name),
    }
