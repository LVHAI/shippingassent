from __future__ import annotations

import agent.graph as graph_module
from agent.state import ShippingState


def _state(**overrides):
    state: ShippingState = {
        "user_input": "test",
        "intent_type": "chitchat",
        "country": None,
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    }
    state.update(overrides)
    return state


def test_rule_query_routes_to_search_rules_and_response(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        graph_module,
        "parse_intent_node",
        lambda state: {"intent_type": "rule_query", "missing_params": []},
    )
    monkeypatch.setattr(
        graph_module,
        "search_rules_node",
        lambda state: calls.append("search") or {"rule_results": [{"text": "赔偿标准"}]},
    )
    monkeypatch.setattr(
        graph_module,
        "generate_response_node",
        lambda state: calls.append("response") or {"response": "规则说明"},
    )

    result = graph_module.build_graph().invoke(_state())

    assert calls == ["search", "response"]
    assert result["response"] == "规则说明"


def test_mixed_query_runs_rate_and_rule_paths(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        graph_module,
        "parse_intent_node",
        lambda state: {
            "intent_type": "mixed",
            "country": "美国",
            "weight": 5.0,
            "cargo_type": "普货",
            "missing_params": [],
        },
    )
    monkeypatch.setattr(
        graph_module,
        "calculate_rate_node",
        lambda state: calls.append("rate") or {"rate_results": [{"total_price": 10}]},
    )
    monkeypatch.setattr(
        graph_module,
        "search_rules_node",
        lambda state: calls.append("rules") or {"rule_results": [{"text": "尺寸限制"}]},
    )
    monkeypatch.setattr(
        graph_module,
        "generate_response_node",
        lambda state: calls.append("response") or {"response": "报价+规则"},
    )

    result = graph_module.build_graph().invoke(_state())

    assert set(calls[:2]) == {"rate", "rules"}
    assert calls[-1] == "response"
    assert result["response"] == "报价+规则"


def test_followup_state_is_persisted_between_turns(monkeypatch):
    inputs: list[ShippingState] = []

    def fake_parse(state):
        inputs.append(state.copy())
        if state["user_input"] == "寄到日本多少钱":
            return {
                "intent_type": "rate_query",
                "country": "日本",
                "weight": None,
                "cargo_type": None,
                "missing_params": ["weight", "cargo_type"],
            }
        return {
            "intent_type": "rate_query",
            "country": state.get("country"),
            "weight": 2.0,
            "cargo_type": "衣服",
            "missing_params": [],
        }

    monkeypatch.setattr(graph_module, "parse_intent_node", fake_parse)
    monkeypatch.setattr(
        graph_module,
        "calculate_rate_node",
        lambda state: {"rate_results": [{"total_price": 20}]},
    )
    monkeypatch.setattr(
        graph_module,
        "generate_response_node",
        lambda state: {"response": "报价"},
    )

    workflow = graph_module.build_graph()
    config = {"configurable": {"thread_id": "conversation-1"}}
    first = workflow.invoke({"user_input": "寄到日本多少钱"}, config)
    second = workflow.invoke({"user_input": "2kg衣服"}, config)

    assert first["route"] == "ask_followup"
    assert second["country"] == "日本"
    assert second["weight"] == 2.0
    assert second["cargo_type"] == "衣服"
    assert second["response"] == "报价"


def test_chitchat_generates_response_without_rate_or_rule(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        graph_module,
        "parse_intent_node",
        lambda state: {"intent_type": "chitchat", "missing_params": []},
    )
    monkeypatch.setattr(
        graph_module,
        "generate_response_node",
        lambda state: calls.append("response") or {"response": "你好"},
    )
    monkeypatch.setattr(
        graph_module,
        "calculate_rate_node",
        lambda state: calls.append("rate") or {"rate_results": []},
    )
    monkeypatch.setattr(
        graph_module,
        "search_rules_node",
        lambda state: calls.append("rules") or {"rule_results": []},
    )

    result = graph_module.build_graph().invoke(_state())

    assert calls == ["response"]
    assert result["response"] == "你好"
