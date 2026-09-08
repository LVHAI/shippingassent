from pathlib import Path

from data_pipeline.xls_parser import XLSPipeline


ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "20260713.xls"


def test_infer_country_supports_israel():
    assert XLSPipeline._infer_country("以色列专线小包", None) == "以色列"


def test_israel_sheet_rates_have_country():
    pipeline = XLSPipeline(XLS_PATH)
    rows = pipeline.parse_sheet("以色列专线小包")

    assert rows
    assert any(row.countries == "以色列" for row in rows)
