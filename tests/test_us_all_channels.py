from __future__ import annotations

from pathlib import Path

from agent.tools import calculate_rate
from data_pipeline.sqlite_loader import load_from_xls


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = PROJECT_ROOT / "20260713.xls"


def test_us_three_kg_normal_cargo_returns_all_matching_channels(tmp_path: Path):
    db_path = tmp_path / "shipping.db"
    load_from_xls(WORKBOOK, db_path)

    results = calculate_rate("美国", 3.0, "普货")
    channels = {item["channel_name"] for item in results}

    assert {"欧美标准专线", "TM美国专线Y2", "美国专线小包"}.issubset(channels)
