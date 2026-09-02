from __future__ import annotations

import sqlite3

from agent.tools import calculate_rate


def test_calculate_rate_matches_country_with_first_weight_without_weight_max(tmp_path, monkeypatch):
    db_path = tmp_path / "shipping.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE channels (
                id INTEGER PRIMARY KEY,
                sheet_name TEXT, channel_name TEXT, product_category TEXT,
                region TEXT, countries TEXT, cargo_type TEXT,
                weight_min REAL, weight_max REAL, price_per_kg REAL,
                handling_fee REAL, first_weight REAL, first_weight_price REAL,
                additional_weight REAL, additional_weight_price REAL,
                product_id INTEGER, billing_rules TEXT, size_requirements TEXT,
                transit_time TEXT, carrier TEXT, service_type TEXT, notes TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO channels (
                sheet_name, channel_name, countries, cargo_type,
                weight_min, weight_max, first_weight, first_weight_price,
                additional_weight, additional_weight_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "以色列专线", "以色列DHL", "以色列", "普货",
                0.5, None, 0.5, 30, 0.5, 10,
            ),
        )

    monkeypatch.setenv("SHIPPING_DB_PATH", str(db_path))

    results = calculate_rate("以色列", 5, "普货")

    assert len(results) == 1
    assert results[0]["channel_name"] == "以色列DHL"
    assert results[0]["total_price"] == 120
