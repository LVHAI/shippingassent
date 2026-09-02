from __future__ import annotations

import sqlite3
from pathlib import Path


def test_app_exposes_three_pages():
    import app

    assert app.PAGE_NAMES == ["聊天", "数据导入", "渠道浏览"]


def test_run_agent_uses_conversation_id(monkeypatch):
    import app

    calls = []

    def fake_run_once(user_input, previous_state=None, conversation_id="default"):
        calls.append((user_input, previous_state, conversation_id))
        return {"response": "ok"}

    monkeypatch.setattr(app, "run_once", fake_run_once)
    result = app.run_agent("美国5kg普货多少钱", "conv-123")

    assert result["response"] == "ok"
    assert calls == [("美国5kg普货多少钱", None, "conv-123")]


def test_streamlit_app_loads_project_dotenv(monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(app, "load_dotenv", lambda *args, **kwargs: calls.append((args, kwargs)) or True)

    assert app.load_environment() is True
    assert calls == [((app.ROOT / ".env",), {})]


def test_import_uploaded_xls_rebuilds_sqlite_and_milvus(monkeypatch, tmp_path: Path):
    import app

    uploaded = tmp_path / "rates.xls"
    uploaded.write_bytes(b"xls")
    calls = []

    def fake_import(xls_path, db_path, milvus_path):
        calls.append((Path(xls_path), Path(db_path), Path(milvus_path)))
        return {"rate_count": 12, "rule_count": 7}

    monkeypatch.setattr(app, "import_xls_data", fake_import)
    result = app.import_uploaded_xls(uploaded, tmp_path / "shipping.db", tmp_path / "rules.db")

    assert result == {"rate_count": 12, "rule_count": 7}
    assert calls[0][0] == uploaded


def test_list_channels_groups_by_region_and_country(tmp_path: Path):
    import app

    db = tmp_path / "shipping.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE channels (id INTEGER, sheet_name TEXT, channel_name TEXT, region TEXT, countries TEXT, cargo_type TEXT)")
        conn.executemany(
            "INSERT INTO channels VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "美国渠道", "UPS", "北美", "美国,加拿大", "普货"),
                (2, "欧洲渠道", "DHL", "欧洲", "德国,法国", "普货"),
                (3, "美国渠道", "FedEx", "北美", "美国", "带电"),
            ],
        )

    rows = app.list_channels(db)
    grouped = app.group_channels(rows)

    assert len(rows) == 3
    assert rows[0]["region"] == "北美"
    assert rows[0]["countries"] == "美国,加拿大"
    assert [row["id"] for row in grouped["北美"]] == [1, 3]
    assert [row["id"] for row in grouped["欧洲"]] == [2]


def test_channel_details_returns_selected_channel(tmp_path: Path):
    import app

    db = tmp_path / "shipping.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE channels (id INTEGER, channel_name TEXT, countries TEXT, cargo_type TEXT, weight_min REAL, weight_max REAL, price_per_kg REAL, size_requirements TEXT, transit_time TEXT, carrier TEXT)")
        conn.execute("INSERT INTO channels VALUES (1, 'UPS', '美国', '普货', 0, 20, 30, '60cm', '5-8天', 'UPS')")

    detail = app.get_channel_detail(db, 1)

    assert detail["channel_name"] == "UPS"
    assert detail["carrier"] == "UPS"


def test_get_channel_rules_uses_milvus_metadata_filter(monkeypatch, tmp_path: Path):
    import app

    calls = []

    class FakeLoader:
        def __init__(self, uri):
            calls.append(("init", Path(uri)))

        def list_rules(self, sheet_name=None, channel_name=None, rule_category=None, limit=100):
            calls.append(("list", sheet_name, channel_name, rule_category, limit))
            return [{"text": "单票申报价值不能超过规定金额", "rule_category": "申报"}]

    monkeypatch.setattr(app, "MilvusRuleLoader", FakeLoader)
    rules = app.get_channel_rules(tmp_path / "rules.db", "美国专线小包", "ED美线免税小包-普货(AQ)")

    assert rules == [{"text": "单票申报价值不能超过规定金额", "rule_category": "申报"}]
    assert calls == [
        ("init", tmp_path / "rules.db"),
        ("list", "美国专线小包", "ED美线免税小包-普货(AQ)", None, 100),
    ]
