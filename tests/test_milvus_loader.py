from pathlib import Path

import pytest

from data_pipeline.milvus_loader import MilvusRuleLoader


class FakeEmbedding:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(i)] * 1024 for i, _ in enumerate(texts)]


def test_collection_schema_contains_required_rule_fields(tmp_path):
    loader = MilvusRuleLoader(uri=tmp_path / "rules.db")
    loader.create_collection()

    fields = {field.name: field for field in loader.client.describe_collection(loader.collection_name)["fields"]}
    assert {"id", "embedding", "text", "sheet_name", "channel_name", "rule_category", "metadata"} <= fields.keys()
    assert fields["embedding"].params["dim"] == 1024


def test_load_rules_embeds_and_inserts_channel_rules(tmp_path):
    loader = MilvusRuleLoader(uri=tmp_path / "rules.db", embedding_client=FakeEmbedding())
    loader.create_collection()

    rules = [
        {
            "sheet_name": "美国专线小包",
            "channel_name": "美国专线小包",
            "rule_category": "尺寸",
            "content": "最大尺寸55*40*35CM",
        },
        {
            "sheet_name": "易德赔付标准",
            "channel_name": None,
            "rule_category": "赔偿",
            "content": "丢失按规定赔偿",
        },
    ]

    count = loader.load_rules(rules)

    assert count == 2
    assert loader.client.get(loader.collection_name, ids=[0, 1])


def test_search_rules_supports_metadata_filters(tmp_path):
    embedding = FakeEmbedding()
    loader = MilvusRuleLoader(uri=tmp_path / "rules.db", embedding_client=embedding)
    loader.create_collection()
    loader.load_rules([
        {"sheet_name": "美国专线小包", "channel_name": "美国", "rule_category": "尺寸", "content": "美国尺寸限制"},
        {"sheet_name": "易德赔付标准", "channel_name": None, "rule_category": "赔偿", "content": "赔偿标准"},
    ])

    results = loader.search("尺寸限制", top_k=3, sheet_name="美国专线小包")

    assert results
    assert all(item["sheet_name"] == "美国专线小包" for item in results)
    assert results[0]["text"] == "美国尺寸限制"


def test_embedding_failure_has_actionable_error(tmp_path):
    class BrokenEmbedding:
        def embed(self, texts):
            raise RuntimeError("DashScope unavailable")

    loader = MilvusRuleLoader(uri=tmp_path / "rules.db", embedding_client=BrokenEmbedding())
    with pytest.raises(RuntimeError, match="DashScope unavailable"):
        loader.embed_texts(["赔偿标准"])


def test_search_rules_tool_delegates_to_loader(monkeypatch):
    from agent import tools

    class FakeLoader:
        def search(self, query, top_k=3, sheet_name=None, rule_category=None):
            return [{"text": query, "sheet_name": sheet_name, "rule_category": rule_category}]

    monkeypatch.setattr(tools, "_get_rule_loader", lambda: FakeLoader())

    result = tools.search_rules("什么东西不能寄", top_k=2, rule_category="禁运")

    assert result == [{"text": "什么东西不能寄", "sheet_name": None, "rule_category": "禁运"}]
