from data_pipeline.sqlite_loader import load_rates
from data_pipeline.xls_parser import ChannelRate
from agent.tools import calculate_rate


def test_query_uses_exact_supported_cargo_membership(tmp_path, monkeypatch):
    db = tmp_path / "shipping.db"
    load_rates(
        [
            ChannelRate(
                sheet_name="test",
                channel_name="P服装渠道",
                countries="美国",
                cargo_type="P服装",
                supported_cargo_types=("普货", "P服装", "包包", "鞋子"),
                weight_min=1,
                weight_max=6,
                price_per_kg=10,
                handling_fee=5,
            ),
            ChannelRate(
                sheet_name="test",
                channel_name="P敏货渠道",
                countries="美国",
                cargo_type="P",
                supported_cargo_types=("普货", "P"),
                weight_min=1,
                weight_max=6,
                price_per_kg=11,
                handling_fee=5,
            ),
        ],
        db,
    )
    monkeypatch.setenv("SHIPPING_DB_PATH", str(db))

    sensitive = calculate_rate("美国", 3, "敏货")
    clothing = calculate_rate("美国", 3, "服装")
    shoes = calculate_rate("美国", 3, "鞋子")
    bags = calculate_rate("美国", 3, "包包")

    assert [row["channel_name"] for row in sensitive] == ["P敏货渠道"]
    assert [row["channel_name"] for row in clothing] == ["P服装渠道"]
    assert [row["channel_name"] for row in shoes] == ["P服装渠道"]
    assert [row["channel_name"] for row in bags] == ["P服装渠道"]
