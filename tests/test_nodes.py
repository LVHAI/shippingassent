import agent.nodes as nodes


def test_parse_intent_node_normalizes_cargo_and_returns_state_update(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "衣服",
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "美国5kg衣服多少钱"})
    assert result == {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "P服装",
        "missing_params": [],
    }


def test_parse_intent_node_marks_missing_rate_parameters(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rate_query",
        "country": "巴西",
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "寄到巴西要多少钱"})
    assert result["missing_params"] == ["weight", "cargo_type"]


def test_parse_intent_node_preserves_empty_missing_params_for_rule_query(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rule_query",
        "country": None,
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "赔偿标准是什么"})
    assert result["missing_params"] == []
