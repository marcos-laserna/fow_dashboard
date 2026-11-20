import csv
import pytest
from openpyxl import Workbook
from pipeline.model import normalize_period, infer_frequency, normalize_unit
from pipeline.sources.ine import fetch_catalog_table
from pipeline.sources.eurostat import parse_jsonstat
from pipeline.sources.manual import read_manual_files
from pipeline.store import merge_write
from pipeline.transforms import pct_yoy, pct_change, rebase


def test_periods_and_unit():
    assert normalize_period("2024T2") == "2024-Q2"
    assert normalize_period("2024Q3") == "2024-Q3"
    assert normalize_period("2024-02") == "2024-02"
    assert normalize_period("2024") == "2024"
    assert infer_frequency("2024-Q2") == "Q"
    assert normalize_unit("?ndice") == "Índice"


def test_ine_timestamp_and_fallback():
    spec = {
        "table_id": "1",
        "family": "x",
        "series": [{"series_id": "ID", "label": "Nombre Serie", "unit": "?ndice"}],
    }
    payload = [
        {
            "COD": "wrong",
            "Nombre": "Nombre Serie",
            "Data": [
                {"Fecha": 1704067200000, "Valor": 2},
                {"Fecha": 1704153600, "Valor": ".."},
            ],
        }
    ]
    rows = fetch_catalog_table(spec, "now", True, lambda *a: payload)
    assert rows[0]["period"] == "2024-01" and rows[0]["unit"] == "Índice"


def test_jsonstat_sparse_and_list():
    spec = {"series_id": "x", "label": "X", "unit": "%", "frequency": "M"}
    payload = {
        "id": ["time"],
        "size": [2],
        "dimension": {"time": {"category": {"index": {"2024-01": 0, "2024M02": 1}}}},
        "value": {"0": 1.2, "1": None},
    }
    assert parse_jsonstat(payload, spec, "t")[0]["period"] == "2024-01"
    payload["value"] = [1, 2]
    assert parse_jsonstat(payload, spec, "t")[1]["period"] == "2024-02"
    for label, expected in [("2024-Q1", "2024-Q1"), ("2024", "2024")]:
        p = {
            "id": ["time"],
            "size": [1],
            "dimension": {"time": {"category": {"index": [label]}}},
            "value": [3],
        }
        assert parse_jsonstat(p, spec, "t")[0]["period"] == expected
    p = {
        "id": ["geo", "time"],
        "size": [2, 1],
        "dimension": {
            "geo": {"category": {"index": ["ES", "EA"]}},
            "time": {"category": {"index": ["2024"]}},
        },
        "value": [1, 2],
    }
    with pytest.raises(ValueError, match="combinación"):
        parse_jsonstat(p, spec, "t")


def _xlsx(path, rows):
    w = Workbook()
    s = w.active
    s.title = "datos"
    for row in rows:
        s.append(row)
    w.save(path)


def test_manual_long_wide_and_error(tmp_path):
    _xlsx(
        tmp_path / "long.xlsx",
        [["period", "value", "series_name"], ["2024-01", 1, "A"], ["2024-02", 2, "B"]],
    )
    _xlsx(tmp_path / "wide.xlsx", [["period", "North", "South"], ["2024-Q1", 3, 4]])
    _xlsx(tmp_path / "~$ignore.xlsx", [["junk"], ["bad"]])
    settings = {"manual": {"default_label": "Default", "default_unit": ""}}
    rows = read_manual_files(settings, "now", tmp_path)
    assert len(rows) == 4 and len({r["series_id"] for r in rows}) == 4
    _xlsx(tmp_path / "bad.xlsx", [["period", "value"], ["bad", 4]])
    with pytest.raises(ValueError, match="bad.xlsx, fila 2"):
        read_manual_files(settings, "now", tmp_path)


def test_store_rebuild_catalog(tmp_path):
    obs = tmp_path / "observations.csv"
    cat = tmp_path / "catalog.csv"
    with obs.open("w", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "series_id",
                "series_name",
                "source",
                "period",
                "value",
                "unit",
                "frequency",
                "retrieved_at",
            ],
        )
        w.writeheader()
        for sid, source in [("manual_series", "Excel:gone.xlsx"), ("old", "INE")]:
            w.writerow(
                dict(
                    series_id=sid,
                    series_name=sid,
                    source=source,
                    period="2020-01",
                    value="1",
                    unit="?ndice",
                    frequency="M",
                    retrieved_at="x",
                )
            )
    rows = [
        dict(
            series_id="XL_A_S",
            series_name="S",
            source="Excel:a.xlsx",
            period=p,
            value=v,
            unit="",
            frequency="M",
            retrieved_at="now",
        )
        for p, v in [("2024-01", "1"), ("2024-02", "2")]
    ]
    merge_write(rows, obs, cat, {"XL_A_S": "manual"}, cat)
    data = list(csv.DictReader(obs.open(encoding="utf-8")))
    assert {x["series_id"] for x in data} == {"old", "XL_A_S"} and next(
        x for x in data if x["series_id"] == "old"
    )["unit"] == "Índice"
    c = {x["series_id"]: x for x in csv.DictReader(cat.open(encoding="utf-8"))}["XL_A_S"]
    assert (c["first_period"], c["last_period"], c["n_obs"], c["group"]) == (
        "2024-01",
        "2024-02",
        "2",
        "manual",
    )


def test_transforms_calendar_gaps_and_zero():
    assert pct_yoy([("2023-01", 1), ("2024-01", 2), ("2024-03", 3)]) == [
        ("2023-01", None),
        ("2024-01", 100.0),
        ("2024-03", None),
    ]
    assert pct_yoy([("2023-Q1", 1), ("2024-Q1", 2)])[1][1] == 100
    assert pct_yoy([("2023", 1), ("2024", 2)])[1][1] == 100
    assert pct_change([("2024-01", 0), ("2024-02", 1)])[1][1] is None
    assert rebase([("2024-01", 2)], "2023-01") == [("2024-01", None)]


def test_ine_series_monthly_period():
    from pipeline.sources.ine import fetch_ine

    spec = {
        "table_id": "1",
        "series_name_contains": "madrid",
        "series_id": "R",
        "label": "R",
        "unit": "?ndice",
        "frequency": "M",
    }
    payload = [
        {
            "Nombre": "Madrid",
            "Data": [{"Fecha": "2024-03-01T00:00:00.000+01:00", "Valor": 5}],
        }
    ]
    assert fetch_ine(spec, "now", lambda *a: payload)[0]["period"] == "2024-03"


def test_store_migrates_legacy_daily_monthly_periods(tmp_path):
    obs = tmp_path / "observations.csv"
    cat = tmp_path / "catalog.csv"
    with obs.open("w", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "series_id",
                "series_name",
                "source",
                "period",
                "value",
                "unit",
                "frequency",
                "retrieved_at",
            ],
        )
        w.writeheader()
        w.writerow(
            dict(
                series_id="R",
                series_name="R",
                source="INE",
                period="2024-03-01",
                value="5",
                unit="",
                frequency="M",
                retrieved_at="x",
            )
        )
    merge_write(
        [
            dict(
                series_id="R",
                series_name="R",
                source="INE",
                period="2024-03",
                value="6",
                unit="",
                frequency="M",
                retrieved_at="y",
            )
        ],
        obs,
        cat,
    )
    data = list(csv.DictReader(obs.open(encoding="utf-8")))
    assert [(r["period"], r["value"]) for r in data] == [("2024-03", "6")]


def test_run_aborts_without_writing_when_excel_fails(tmp_path, monkeypatch):
    import pipeline.run as run

    (tmp_path / "data" / "manual").mkdir(parents=True)
    (tmp_path / "data" / "series.json").write_text('{"sources": [], "manual": {}}')
    _xlsx(tmp_path / "data" / "manual" / "bad.xlsx", [["period", "value"], ["bad", 1]])
    monkeypatch.setattr(run, "ROOT", tmp_path)
    assert run.main() == 1
    assert not (tmp_path / "data" / "processed" / "observations.csv").exists()


def test_classify_groups_siblings_and_flags_transformed():
    from pipeline.classify import classify

    a = classify("Nacional. Índice general. Índice.")
    b = classify("Nacional. Índice general. Variación anual.")
    c = classify(
        "Total Nacional. Cifra de negocio. General. Variación de la media en lo que va de año."
    )
    assert a["concept"] == b["concept"] == "Nacional. Índice general"
    assert (a["measure"], b["measure"], c["measure"]) == ("level", "yoy", "ytd")
    assert classify("Nacional. Vivienda. Variación mensual.")["measure"] == "pct"
    assert classify("IASS · Original (60288)") == {
        "concept": "IASS",
        "variant": "Original (60288)",
        "measure": "level",
        "adjustment": "nsa",
        "base": "iass",
    }
    assert classify("Tasa de paro (SA) — España")["concept"] == "Tasa de paro (SA)"
    assert classify("SIMULADA - serie Excel")["variant"] == ""


def test_classify_links_published_versions_of_a_series():
    from pipeline.classify import classify

    names = {
        "IASS · Original (60288)": "nsa",
        "IASS · Ajustado calendario (60289)": "cal",
        "IASS · Ajustado calendario y estacionalidad (60290)": "sa",
    }
    got = {n: classify(n) for n in names}
    assert {n: c["adjustment"] for n, c in got.items()} == names
    assert {c["base"] for c in got.values()} == {"iass"}
    # INE wording in catalog tables
    a = classify("Total Nacional. General. Datos corregidos de efectos estacionales y de calendario. Índice.")
    b = classify("Total Nacional. General. Datos corregidos de efectos de calendario. Índice.")
    c = classify("Total Nacional. General. Datos originales. Índice.")
    d = classify("Total Nacional. General. Tendencia. Índice.")
    assert [x["adjustment"] for x in (a, b, c, d)] == ["sa", "cal", "nsa", "trend"]
    assert len({x["base"] for x in (a, b, c, d)}) == 1
    # Rates keep their own family: an annual rate is not a version of the index.
    assert classify("Total Nacional. General. Datos originales. Variación anual.")["base"] != c["base"]
    assert classify("Tasa de paro (SA) — España")["adjustment"] == "sa"
    assert classify("Nacional. Índice general. Índice.")["adjustment"] == "nsa"


def test_store_writes_adjustment_columns(tmp_path):
    obs, cat = tmp_path / "o.csv", tmp_path / "c.csv"
    rows = [
        dict(series_id=sid, series_name=name, source="INE", period="2024-01",
             value="1", unit="", frequency="M", retrieved_at="now")
        for sid, name in [("raw", "IPI · Original (60272)"),
                          ("sa", "IPI · Ajustado calendario y estacionalidad (60280)")]
    ]
    merge_write(rows, obs, cat, {"raw": "ipi", "sa": "ipi"}, cat, {"raw": {"adjustment": "trend"}})
    c = {x["series_id"]: x for x in csv.DictReader(cat.open(encoding="utf-8"))}
    assert (c["sa"]["adjustment"], c["sa"]["base"]) == ("sa", "ipi")
    assert c["raw"]["adjustment"] == "trend"  # config override wins
