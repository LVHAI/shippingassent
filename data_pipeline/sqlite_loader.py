from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from data_pipeline.xls_parser import ChannelRate


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "shipping.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_name TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    product_category TEXT,
    region TEXT,
    countries TEXT,
    cargo_type TEXT,
    weight_min REAL,
    weight_max REAL,
    price_per_kg REAL,
    handling_fee REAL,
    first_weight REAL,
    first_weight_price REAL,
    additional_weight REAL,
    additional_weight_price REAL,
    product_id INTEGER,
    billing_rules TEXT,
    size_requirements TEXT,
    transit_time TEXT,
    carrier TEXT,
    service_type TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_channels_country ON channels(countries);
CREATE INDEX IF NOT EXISTS idx_channels_cargo_weight
    ON channels(cargo_type, weight_min, weight_max);
"""

INSERT_SQL = """
INSERT INTO channels (
    sheet_name, channel_name, product_category, region, countries, cargo_type,
    weight_min, weight_max, price_per_kg, handling_fee, first_weight,
    first_weight_price, additional_weight, additional_weight_price, product_id,
    billing_rules, size_requirements, transit_time, carrier, service_type, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def init_db(db_path: str | Path = DB_PATH) -> Path:
    """Create the SQLite database and its rate table if they do not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


def _row_from_rate(rate: ChannelRate) -> tuple:
    return (
        rate.sheet_name,
        rate.channel_name or rate.sheet_name,
        None,
        None,
        rate.countries,
        rate.cargo_type,
        rate.weight_min,
        rate.weight_max,
        rate.price_per_kg,
        rate.handling_fee,
        rate.first_weight,
        rate.first_weight_price,
        rate.additional_weight,
        rate.additional_weight_price,
        None,
        None,
        rate.size_requirements,
        rate.transit_time,
        rate.carrier,
        None,
        None,
    )


def load_rates(rates: Iterable[ChannelRate], db_path: str | Path = DB_PATH) -> int:
    """Replace all existing rates with *rates* in one transaction."""
    path = init_db(db_path)
    rows = [_row_from_rate(rate) for rate in rates]
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM channels")
        conn.executemany(INSERT_SQL, rows)
    return len(rows)


def load_from_xls(xls_path: str | Path, db_path: str | Path = DB_PATH) -> int:
    """Parse an XLS workbook and rebuild the SQLite rate table."""
    from data_pipeline.xls_parser import XLSPipeline

    pipeline = XLSPipeline(xls_path)
    return load_rates(pipeline.parse_all(), db_path)


def export_json_rows(db_path: str | Path = DB_PATH) -> list[dict]:
    """Return database rows as JSON-compatible dictionaries for diagnostics."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM channels")]


__all__ = ["DB_PATH", "SCHEMA", "init_db", "load_rates", "load_from_xls"]
