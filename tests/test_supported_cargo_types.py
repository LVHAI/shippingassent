import json

from data_pipeline.xls_parser import XLSPipeline
from agent.tools import _cargo_matches, normalize_cargo_type


def test_parse_multiple_supported_cargo_types():
    text = "可接普货、P服装、包包、鞋子（不接带电、带磁、液体）"

    assert XLSPipeline._parse_supported_cargo_types(text) == ["普货", "P服装", "包包", "鞋子"]


def test_parse_p_special_cargo_capability():
    text = "接P膏体化妆品、弱磁、内电产品"

    assert XLSPipeline._parse_supported_cargo_types(text) == ["P", "膏体", "弱磁", "带电"]


def test_p_and_p_clothing_are_distinct_capabilities():
    assert _cargo_matches("P", "P")
    assert not _cargo_matches("P服装", "P")
    assert _cargo_matches("P服装", "P服装")


def test_cargo_synonyms_keep_bags_and_shoes_distinct_from_clothing():
    assert normalize_cargo_type("服装") == "P服装"
    assert normalize_cargo_type("鞋子") == "鞋子"
    assert normalize_cargo_type("包包") == "包包"


def test_supported_cargo_types_are_json_serializable():
    values = XLSPipeline._parse_supported_cargo_types("可接普货、P服装、包包、鞋子")
    assert json.loads(json.dumps(values, ensure_ascii=False)) == values
