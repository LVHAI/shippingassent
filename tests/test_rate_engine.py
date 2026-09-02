import math
import sqlite3

import pytest

from data_pipeline.xls_parser import ChannelRate
from data_pipeline.sqlite_loader import init_db, load_rates
from agent.tools import calculate_rate


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "shipping.db"
    init_db(path)
    rates = [
        ChannelRate(
            sheet_name="美国专线小包",
            channel_name="美国普货快线",
            countries="美国",
            cargo_type="普货",
            weight_min=0.05,
            weight_max=10,
            price_per_kg=20,
            handling_fee=5,
            size_requirements="55*40*35CM",
            transit_time="7-15天",
            carrier="USPS",
        ),
        ChannelRate(
            sheet_name="美国专线小包",
            channel_name="美国带电快线",
            countries="美国",
            cargo_type="带电",
            weight_min=0.05,
            weight_max=10,
            price_per_kg=10,
            handling_fee=5,
        ),
        ChannelRate(
            sheet_name="日本专线小包",
            channel_name="日本普货佐川",
            countries="日本",
            cargo_type="普货",
            weight_min=0.5,
            weight_max=2.5,
            first_weight=0.5,
            first_weight_price=77,
            additional_weight=0.5,
            additional_weight_price=21,
            carrier="佐川",
        ),
        ChannelRate(
            sheet_name="欧洲专线",
            channel_name="欧洲低价渠道",
            countries="欧洲,德国",
            cargo_type="普货",
            weight_min=1,
            weight_max=20,
            price_per_kg=8,
            handling_fee=2,
        ),
        ChannelRate(
            sheet_name="美国专线小包",
            channel_name="美国更低价渠道",
            countries="美国",
            cargo_type="普货",
            weight_min=1,
            weight_max=20,
            price_per_kg=15,
            handling_fee=1,
        ),
    ]
    load_rates(rates, path)
    monkeypatch.setenv("SHIPPING_DB_PATH", str(path))
    return path


def test_calculate_rate_price_per_kg_is_sorted_and_correct(db_path):
    results = calculate_rate("美国", 5.0, "普货")
    assert [item["channel_name"] for item in results] == ["美国更低价渠道", "美国普货快线"]
    assert results[0]["total_price"] == pytest.approx(76)
    assert results[1]["total_price"] == pytest.approx(105)


def test_normal_cargo_excludes_electric_channel(db_path):
    results = calculate_rate("美国", 5.0, "普货")
    assert all(item["cargo_type"] != "带电" for item in results)


def test_first_and_additional_weight_calculation(db_path):
    results = calculate_rate("日本", 0.8, "普货")
    assert len(results) == 1
    assert results[0]["total_price"] == pytest.approx(98)


def test_weight_below_starting_weight_uses_starting_weight(db_path):
    results = calculate_rate("日本", 0.2, "普货")
    assert len(results) == 1
    assert results[0]["total_price"] == pytest.approx(77)


def test_country_match_accepts_country_contained_in_channel_country_field(db_path):
    results = calculate_rate("德国", 5.0, "普货")
    assert [item["channel_name"] for item in results] == ["欧洲低价渠道"]


def test_weight_range_is_enforced(db_path):
    results = calculate_rate("日本", 3.0, "普货")
    assert results == []


def test_no_match_returns_empty_list(db_path):
    assert calculate_rate("法国", 5.0, "纯电池") == []


def test_loader_creates_channels_table_with_all_rate_fields(tmp_path):
    path = tmp_path / "shipping.db"
    init_db(path)
    columns = {row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(channels)")}
    expected = {
        "sheet_name", "channel_name", "product_category", "region", "countries",
        "cargo_type", "weight_min", "weight_max", "price_per_kg", "handling_fee",
        "first_weight", "first_weight_price", "additional_weight", "additional_weight_price",
        "product_id", "billing_rules", "size_requirements", "transit_time", "carrier",
        "service_type", "notes",
    }
    assert expected <= columns
