import pytest

from agent.tools import CARGO_TYPE_SYNONYMS, normalize_cargo_type


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("普通商品", "普货"),
        ("没特殊要求", "普货"),
        ("一般货物", "普货"),
        ("衣服", "P服装"),
        ("服装", "P服装"),
        ("鞋子", "鞋子"),
        ("包包", "包包"),
        ("电子产品", "带电"),
        ("手机", "带电"),
        ("带电池", "带电"),
        ("笔记本", "带电"),
        ("化妆品", "膏体"),
        ("面霜", "膏体"),
        ("护肤品", "膏体"),
        ("香水", "液体"),
        ("酒精液体", "液体"),
        ("纯电池", "纯电池"),
        ("充电宝", "纯电池"),
        ("粉末", "粉末"),
        ("粉状物", "粉末"),
    ],
)
def test_high_frequency_cargo_synonyms(user_input, expected):
    assert normalize_cargo_type(user_input) == expected


def test_matching_ignores_case_and_surrounding_whitespace():
    assert normalize_cargo_type(" 普通商品 ") == "普货"
    assert normalize_cargo_type(" 手 机 ") == " 手 机 "


def test_unmatched_input_is_returned_unchanged():
    value = "医疗器械"
    assert normalize_cargo_type(value) == value


def test_empty_input_is_returned_unchanged():
    assert normalize_cargo_type("") == ""
    assert normalize_cargo_type("   ") == "   "


def test_synonym_mapping_is_extendable():
    assert isinstance(CARGO_TYPE_SYNONYMS, dict)
    assert "普通商品" in CARGO_TYPE_SYNONYMS
