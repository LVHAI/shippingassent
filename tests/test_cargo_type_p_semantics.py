from pathlib import Path

from data_pipeline.xls_parser import XLSPipeline


ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "20260713.xls"


def test_xls_p_means_replica_or_sensitive_cargo():
    assert XLSPipeline._infer_cargo_type("美国专线小包-P", None) == "P"
    assert XLSPipeline._infer_cargo_type("美国专线小包-P仿牌", None) == "P"
    assert XLSPipeline._infer_cargo_type("以色列专线-P敏感货", None) == "P"


def test_p_is_not_clothing():
    assert XLSPipeline._infer_cargo_type("专线-P", "P") == "P"
    assert XLSPipeline._infer_cargo_type("专线-P服装", None) == "P"


def test_plain_cargo_remains_plain_cargo():
    assert XLSPipeline._infer_cargo_type("美国专线小包-普货", None) == "普货"
    assert XLSPipeline._infer_cargo_type("日本专线小包-P普货", None) == "普货"
