from pathlib import Path

import pytest

from data_pipeline.xls_parser import XLSPipeline


ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "20260713.xls"


@pytest.fixture(scope="module")
def pipeline():
    return XLSPipeline(XLS_PATH)


def test_parser_exposes_five_representative_sheets(pipeline):
    expected = {
        "美国专线小包",
        "日本专线小包",
        "欧美标准专线",
        "巴西专线小包DDU",
        "香港DHL代理价",
    }
    assert expected.issubset(set(pipeline.sheet_names))


def test_us_rate_is_normalized(pipeline):
    rows = pipeline.parse_sheet("美国专线小包")
    row = next(r for r in rows if r.channel_name == "ED美线免税小包-普货(AQ)" and r.weight_min == 0.05)
    assert row.sheet_name == "美国专线小包"
    assert row.cargo_type == "普货"
    assert row.weight_max == 0.1
    assert row.price_per_kg == 96
    assert row.handling_fee == 25
    assert "55*40*35CM" in row.size_requirements
    assert row.transit_time == "7-15天"
    assert "USPS" in row.carrier


def test_japan_first_weight_rate_is_normalized(pipeline):
    rows = pipeline.parse_sheet("日本专线小包")
    row = next(r for r in rows if r.channel_name == "日本专线小包-P普货(佐川)")
    assert row.cargo_type == "普货"
    assert row.weight_min == 0.5
    assert row.weight_max == 2.5
    assert row.first_weight == 0.5
    assert row.first_weight_price == 77
    assert row.additional_weight == 0.5
    assert row.additional_weight_price == 21
    assert row.carrier == "佐川"
    assert row.transit_time == "4-7天"


def test_europe_sheet_keeps_country_and_rate(pipeline):
    rows = pipeline.parse_sheet("欧美标准专线")
    row = next(r for r in rows if r.countries == "希腊" and r.weight_min == 0)
    assert row.channel_name == "欧美标准专线"
    assert row.cargo_type == "普货"
    assert row.weight_max == 2
    assert row.price_per_kg == 94
    assert row.handling_fee == 19
    assert row.carrier == "DEDHL\nDPD"
    assert row.transit_time == "10-15天"


def test_brazil_rate_is_normalized(pipeline):
    rows = pipeline.parse_sheet("巴西专线小包DDU")
    row = next(r for r in rows if r.channel_name.startswith("巴西专线-普货") and r.weight_min == 0)
    assert row.cargo_type == "普货"
    assert row.weight_max == 0.2
    assert row.price_per_kg == 84
    assert row.handling_fee == 35
    assert row.carrier == "巴西邮政correios"


def test_hong_kong_dhl_expands_zone_rates_and_preserves_unavailable(pipeline):
    rows = pipeline.parse_sheet("香港DHL代理价")
    macau = next(r for r in rows if r.countries == "澳门" and r.weight_min == 0.5)
    unavailable = next(r for r in rows if r.countries == "阿富汗" and r.weight_min == 0.5)
    assert macau.price_per_kg == 179.9
    assert unavailable.price_per_kg is None


def test_parse_all_contains_all_representative_sheets(pipeline):
    rows = pipeline.parse_all()
    sheet_names = {row.sheet_name for row in rows}
    assert {"美国专线小包", "日本专线小包", "欧美标准专线", "巴西专线小包DDU", "香港DHL代理价"} <= sheet_names
