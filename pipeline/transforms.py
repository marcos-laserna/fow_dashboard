from __future__ import annotations
from .model import normalize_period, infer_frequency


def level(series):
    return [(p, v) for p, v in series]


def diff(series):
    return [
        (
            p,
            None
            if i == 0 or v is None or series[i - 1][1] is None
            else v - series[i - 1][1],
        )
        for i, (p, v) in enumerate(series)
    ]


def pct_change(series):
    out = []
    for i, (p, v) in enumerate(series):
        prev = series[i - 1][1] if i else None
        out.append(
            (p, None if v is None or prev in (None, 0) else (v / prev - 1) * 100)
        )
    return out


def _ordinal(p):
    p = normalize_period(p)
    f = infer_frequency(p)
    if f == "M":
        return int(p[:4]) * 12 + int(p[5:]) - 1
    if f == "Q":
        return int(p[:4]) * 4 + int(p[-1]) - 1
    if f == "A":
        return int(p)
    return None


def pct_yoy(series):
    if not series:
        return []
    lag = {"M": 12, "Q": 4, "A": 1}.get(infer_frequency(series[0][0]))
    lookup = {_ordinal(p): v for p, v in series}
    return [
        (
            p,
            None
            if lag is None or v is None or lookup.get(_ordinal(p) - lag) in (None, 0)
            else (v / lookup[_ordinal(p) - lag] - 1) * 100,
        )
        for p, v in series
    ]


def rebase(series, base_period):
    base = next(
        (v for p, v in series if normalize_period(p) == normalize_period(base_period)),
        None,
    )
    return [
        (p, None if base in (None, 0) or v is None else v / base * 100)
        for p, v in series
    ]
