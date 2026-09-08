from pathlib import Path

import pandas as pd

from data_pipeline.milvus_loader import DashScopeEmbeddingClient, MilvusRuleLoader
from data_pipeline.xls_parser import ChannelRule, XLSPipeline

ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "20260713.xls"


def _pipeline(monkeypatch, sheets):
    pipeline = object.__new__(XLSPipeline)
    pipeline._excel = object()
    pipeline.sheet_names = list(sheets)

    def read_excel(_excel, sheet_name, header=None):
        return sheets[sheet_name].copy()

    monkeypatch.setattr(pd, "read_excel", read_excel)
    return pipeline


def test_channel_rule_model_contains_normalized_rule_fields():
    rule = ChannelRule(sheet_name="美国专线小包", channel_name="美国专线小包", rule_category="申报", content="申报价值不得超过规定金额")
    assert rule.sheet_name == "美国专线小包"
    assert rule.channel_name == "美国专线小包"
    assert rule.rule_category == "申报"
    assert rule.content == "申报价值不得超过规定金额"


def test_extract_rules_from_rate_sheet_reads_rows_after_rate_table(monkeypatch):
    raw = pd.DataFrame([
        ["美国专线小包"],
        ["渠道", "重量段", "运费/KG", "处理费"],
        ["ED美线免税小包-普货(AQ)", "0.05-0.1KG", 96, 25],
        [None, "0.1-0.2KG", 96, 25],
        [None, None, None, None],
        ["申报要求", "单票申报价值不能超过规定金额", None, None],
        ["赔偿标准", "丢失按规定赔偿", None, None],
    ])
    pipeline = _pipeline(monkeypatch, {"美国专线小包": raw})
    rules = pipeline.extract_rules_from_rate_sheet("美国专线小包")
    assert len(rules) == 2
    assert all(isinstance(rule, ChannelRule) for rule in rules)
    assert rules[0].channel_name == "ED美线免税小包-普货(AQ)"
    assert rules[0].rule_category == "申报"
    assert "申报价值" in rules[0].content
    assert rules[1].rule_category == "赔偿"


def test_extract_standalone_rules_classifies_and_filters_headers(monkeypatch):
    raw = pd.DataFrame([
        ["规则类别", "规则内容"],
        ["赔付标准", "包裹丢失按照货值进行赔偿"],
        ["", ""],
        ["航空禁运物品", "锂电池及危险品禁止运输"],
        ["", ""],
    ])
    pipeline = _pipeline(monkeypatch, {"易德赔付标准": raw})
    rules = pipeline.extract_rules_from_standalone_sheet("易德赔付标准")
    assert len(rules) == 2
    assert {rule.rule_category for rule in rules} == {"赔偿", "禁运"}
    assert all(rule.channel_name is None for rule in rules)
    assert all(rule.content not in {"规则类别", "规则内容"} for rule in rules)


def test_rule_category_supports_all_required_categories():
    cases = {
        "赔偿": "丢失按照规定赔偿", "禁运": "航空禁运物品禁止运输", "尺寸": "单件尺寸不得超过限制", "退件": "退件产生额外费用",
        "申报": "申报价值需要如实填写", "安检": "货物需要通过安检", "时效": "参考时效为7-15天", "其他": "请提前确认相关要求",
    }
    for expected, content in cases.items():
        assert XLSPipeline._classify_rule_category(content) == expected


def test_dashscope_embedding_client_batches_inputs_at_provider_limit(monkeypatch):
    calls = []

    class FakeEmbedding:
        @staticmethod
        def call(**kwargs):
            calls.append(kwargs["input"])
            return {"status_code": 200, "output": {"embeddings": [{"embedding": [0.0] * 1024} for _ in kwargs["input"]]}}

    class FakeDashScope:
        TextEmbedding = FakeEmbedding

    monkeypatch.setitem(__import__("sys").modules, "dashscope", FakeDashScope())
    client = DashScopeEmbeddingClient(api_key="test")

    vectors = client.embed([f"rule-{i}" for i in range(21)])

    assert len(vectors) == 21
    assert [len(batch) for batch in calls] == [20, 1]
    assert calls[0] == [f"rule-{i}" for i in range(20)]
    assert calls[1] == ["rule-20"]


def test_dashscope_embedding_client_respects_current_provider_limit_of_ten(monkeypatch):
    calls = []

    class FakeEmbedding:
        @staticmethod
        def call(**kwargs):
            calls.append(kwargs["input"])
            return {"status_code": 200, "output": {"embeddings": [{"embedding": [0.0] * 1024} for _ in kwargs["input"]]}}

    class FakeDashScope:
        TextEmbedding = FakeEmbedding

    monkeypatch.setitem(__import__("sys").modules, "dashscope", FakeDashScope())
    client = DashScopeEmbeddingClient(api_key="test")

    vectors = client.embed([f"rule-{i}" for i in range(21)])

    assert len(vectors) == 21
    assert all(len(batch) <= 10 for batch in calls)
    assert [len(batch) for batch in calls] == [10, 10, 1]


def test_real_workbook_extracts_rules_from_required_sheets():
    pipeline = XLSPipeline(XLS_PATH)
    rate_rules = []
    for sheet_name in ("美国专线小包", "日本专线小包"):
        rate_rules.extend(pipeline.extract_rules_from_rate_sheet(sheet_name))
    standalone_rules = []
    for sheet_name in ("易德赔付标准", "退费额外费要求", "航空禁运物品"):
        if sheet_name in pipeline.sheet_names:
            standalone_rules.extend(pipeline.extract_rules_from_standalone_sheet(sheet_name))
    assert rate_rules, "required rate-sheet rules were not extracted"
    assert standalone_rules, "required standalone rules were not extracted"
    assert all(rule.content.strip() for rule in rate_rules + standalone_rules)
    assert {rule.rule_category for rule in rate_rules + standalone_rules} <= set(XLSPipeline.RULE_CATEGORIES) | {"其他"}
