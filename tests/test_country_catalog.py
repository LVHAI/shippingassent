from pathlib import Path

import pytest

from data_pipeline.xls_parser import XLSPipeline


ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "20260713.xls"


@pytest.fixture(scope="module")
def pipeline():
    return XLSPipeline(XLS_PATH)


def test_country_catalog_contains_countries_from_xls_reference(pipeline):
    expected = {
        "以色列",
        "土耳其",
        "荷兰",
        "印度",
        "沙特阿拉伯",
        "阿联酋",
        "哈萨克斯坦",
        "意大利",
        "德国",
        "法国",
        "西班牙",
        "葡萄牙",
    }
    assert expected <= set(pipeline.country_catalog)


def test_country_inference_uses_xls_catalog_for_unlisted_country(pipeline):
    assert pipeline._infer_country("土耳其专线小包", None) == "土耳其"
    assert pipeline._infer_country("荷兰专线小包", None) == "荷兰"
    assert pipeline._infer_country("沙特阿拉伯专线小包", None) == "沙特阿拉伯"


def test_country_inference_supports_english_country_alias(pipeline):
    assert pipeline._infer_country("Israel专线小包", None) == "以色列"
    assert pipeline._infer_country("Turkey专线小包", None) == "土耳其"
