from __future__ import annotations

import math
import os
import sqlite3
from pathlib import Path
from typing import Any

from data_pipeline.milvus_loader import MilvusRuleLoader
from data_pipeline.sqlite_loader import DB_PATH

CARGO_TYPE_SYNONYMS: dict[str, str] = {
    "普通商品": "普货", "没特殊要求": "普货", "一般货物": "普货",
    "衣服": "P服装", "服装": "P服装", "鞋子": "P服装", "包包": "P服装",
    "电子产品": "带电", "手机": "带电", "带电池": "带电", "笔记本": "带电",
    "化妆品": "膏体", "面霜": "膏体", "护肤品": "膏体", "香水": "液体",
    "酒精液体": "液体", "纯电池": "纯电池", "充电宝": "纯电池", "粉末": "粉末", "粉状物": "粉末",
}

_rule_loader: MilvusRuleLoader | None = None

def normalize_cargo_type(user_input: str) -> str:
    normalized = user_input.strip().casefold()
    for synonym, cargo_type in CARGO_TYPE_SYNONYMS.items():
        if synonym.casefold() == normalized:
            return cargo_type
    return user_input

def _db_path() -> Path:
    return Path(os.getenv("SHIPPING_DB_PATH", str(DB_PATH)))

def _get_rule_loader() -> MilvusRuleLoader:
    global _rule_loader
    if _rule_loader is None:
        _rule_loader = MilvusRuleLoader()
    return _rule_loader

def search_rules(query: str, top_k: int = 3, sheet_name: str | None = None, rule_category: str | None = None) -> list[dict[str, Any]]:
    if not query or top_k <= 0:
        return []
    return _get_rule_loader().search(query=query, top_k=top_k, sheet_name=sheet_name, rule_category=rule_category)

def _country_matches(countries: str | None, country: str) -> bool:
    return bool(countries and country and country.strip().lower() in countries.lower())

def _cargo_matches(channel_cargo: str | None, requested_cargo: str) -> bool:
    if not channel_cargo or not requested_cargo:
        return False
    channel, requested = channel_cargo.strip(), requested_cargo.strip()
    return channel == requested if requested != "普货" else channel == "普货"

def _calculate_total(row: sqlite3.Row, weight: float) -> float | None:
    price_per_kg = row["price_per_kg"]
    if price_per_kg is not None:
        return weight * float(price_per_kg) + float(row["handling_fee"] or 0)
    first_weight, first_price = row["first_weight"], row["first_weight_price"]
    additional_weight, additional_price = row["additional_weight"], row["additional_weight_price"]
    if first_weight is None or first_price is None:
        return None
    if weight <= float(first_weight):
        return float(first_price)
    if additional_weight is None or additional_price is None or float(additional_weight) <= 0:
        return None
    units = math.ceil((weight - float(first_weight)) / float(additional_weight))
    return float(first_price) + units * float(additional_price)

def calculate_rate(country: str, weight: float, cargo_type: str) -> list[dict[str, Any]]:
    if not country or weight <= 0 or not cargo_type:
        return []
    path = _db_path()
    if not path.is_file():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""SELECT * FROM channels WHERE weight_max IS NOT NULL AND weight_max >= ? AND ((weight_min IS NOT NULL AND weight_min <= ?) OR first_weight IS NOT NULL)""", (weight, weight)).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        if not _country_matches(row["countries"], country) or not _cargo_matches(row["cargo_type"], cargo_type):
            continue
        if row["price_per_kg"] is not None and row["weight_min"] is not None and weight < float(row["weight_min"]):
            continue
        total = _calculate_total(row, weight)
        if total is None:
            continue
        results.append({"id": row["id"], "sheet_name": row["sheet_name"], "channel_name": row["channel_name"], "countries": row["countries"], "cargo_type": row["cargo_type"], "weight_min": row["weight_min"], "weight_max": row["weight_max"], "price_per_kg": row["price_per_kg"], "handling_fee": row["handling_fee"], "first_weight": row["first_weight"], "first_weight_price": row["first_weight_price"], "additional_weight": row["additional_weight"], "additional_weight_price": row["additional_weight_price"], "total_price": total, "transit_time": row["transit_time"], "carrier": row["carrier"], "size_requirements": row["size_requirements"]})
    results.sort(key=lambda item: (item["total_price"], item["channel_name"]))
    return results

__all__ = ["CARGO_TYPE_SYNONYMS", "normalize_cargo_type", "calculate_rate", "search_rules"]
