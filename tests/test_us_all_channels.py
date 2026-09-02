from __future__ import annotations

from pathlib import Path

from agent.tools import calculate_rate
from data_pipeline.sqlite_loader import load_from_xls
from data_pipeline.xls_parser import XLSPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = PROJECT_ROOT / "20260713.xls"


def test_us_three_kg_normal_cargo_returns_all_matching_channels(tmp_path: Path, monkeypatch):
    pipeline = XLSPipeline(WORKBOOK)
    parsed_rates = pipeline.parse_all()
    expected_channels = {
        rate.channel_name
        for rate in parsed_rates
        if rate.channel_name
        and rate.countries
        and "美国" in rate.countries
        and rate.cargo_type == "普货"
        and rate.weight_min <= 3.0 <= rate.weight_max
    }
    assert len(expected_channels) >= 2

    db_path = tmp_path / "shipping.db"
    load_from_xls(WORKBOOK, db_path)
    monkeypatch.setenv("SHIPPING_DB_PATH", str(db_path))

    results = calculate_rate("美国", 3.0, "普货")
    channels = {item["channel_name"] for item in results}

    assert channels == expected_channels
