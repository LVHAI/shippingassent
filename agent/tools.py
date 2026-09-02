from __future__ import annotations

import math
import os
import sqlite3
from pathlib import Path
from typing import Any

from data_pipeline.sqlite_loader import DB_PATH


def _db_path() -> Path:
    return Path(os.getenv("SHIPPING_DB_PATH", str(DB_PATH)))


def _country_matches(countries: str | None, country: str) -> bool:
    if not countries or not country:
        return False
    return country.strip().lower() in countries.lower()


def _cargo_matches(channel_cargo: str | None, requested_cargo: str) -> bool:
    if not channel_cargo or not requested_cargo:
        return False
    channel = channel_cargo.strip()
    requested = requested_cargo.strip()
    if requested == "普货":
        return channel == "普货"
    return channel == requested


def _calculate_total(row: sqlite3.Row, weight: float) -> float | None:
    price_per_kg = row["price_per_kg"]
    if price_per_kg is not None:
        return weight * float(price_per_kg) + float(row["handling_fee"] or 0)

    first_weight = row["first_weight"]
    first_price = row["first_weight_price"]
    additional_weight = row["additional_weight"]
    additional_price = row["additional_weight_price"]
    if first_weight is None or first_price is None:
        return None
    if weight <= float(first_weight):
        return float(first_price)
    if additional_weight is None or additional_price is None or float(additional_weight) <= 0:
        return None
    units = math.ceil((weight - float(first_weight)) / float(additional_weight))
    return float(first_price) + units * float(additional_price)


def calculate_rate(country: str, weight: float, cargo_type: str) -> list[dict[str, Any]]:
    """Return deterministic matching shipping quotes sorted by total price."""
    if not country or weight <= 0 or not cargo_type:
        return []

    path = _db_path()
    if not path.is_file():
        return []

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM channels
            WHERE weight_max IS NOT NULL
              AND weight_max >= ?
              AND (
                    (weight_min IS NOT NULL AND weight_min <= ?)
                    OR first_weight IS NOT NULL
                  )
            """,
            (weight, weight),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        if not _country_matches(row["countries"], country):
            continue
        if not _cargo_matches(row["cargo_type"], cargo_type):
            continue
        # Price/kg rows must satisfy their explicit lower bound. First-weight
        # rows may be selected below weight_min and billed at the starting rate.
        if row["price_per_kg"] is not None and row["weight_min"] is not None and weight < float(row["weight_min"]):
            continue
        total = _calculate_total(row, weight)
        if total is None:
            continue
        results.append({
            "id": row["id"],
            "sheet_name": row["sheet_name"],
            "channel_name": row["channel_name"],
            "countries": row["countries"],
            "cargo_type": row["cargo_type"],
            "weight_min": row["weight_min"],
            "weight_max": row["weight_max"],
            "price_per_kg": row["price_per_kg"],
            "handling_fee": row["handling_fee"],
            "first_weight": row["first_weight"],
            "first_weight_price": row["first_weight_price"],
            "additional_weight": row["additional_weight"],
            "additional_weight_price": row["additional_weight_price"],
            "total_price": total,
            "transit_time": row["transit_time"],
            "carrier": row["carrier"],
            "size_requirements": row["size_requirements"],
        })

    results.sort(key=lambda item: (item["total_price"], item["channel_name"]))
    return results


__all__ = ["calculate_rate"]
