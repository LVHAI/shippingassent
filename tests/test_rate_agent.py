import agent.nodes as nodes


def test_check_params_node_routes_complete_state_to_ready():
    result = nodes.check_params_node({"missing_params": []})
    assert result == {"route": "ready"}


def test_check_params_node_routes_missing_state_to_followup():
    result = nodes.check_params_node({"missing_params": ["weight", "cargo_type"]})
    assert result == {"route": "ask_followup"}


def test_calculate_rate_node_writes_deterministic_quotes(monkeypatch):
    expected = [{"channel_name": "日本普货佐川", "total_price": 119.0, "transit_time": "4-7天"}]
    monkeypatch.setattr(nodes, "calculate_rate", lambda country, weight, cargo_type: expected)
    result = nodes.calculate_rate_node({
        "country": "日本",
        "weight": 2.0,
        "cargo_type": "普货",
    })
    assert result["rate_results"] == expected


def test_calculate_rate_node_returns_empty_when_no_match(monkeypatch):
    monkeypatch.setattr(nodes, "calculate_rate", lambda country, weight, cargo_type: [])
    result = nodes.calculate_rate_node({
        "country": "法国",
        "weight": 5.0,
        "cargo_type": "普货",
    })
    assert result["rate_results"] == []


def test_ask_followup_node_mentions_missing_weight_and_cargo_type():
    result = nodes.ask_followup_node({"missing_params": ["weight", "cargo_type"]})
    assert "重量" in result["response"]
    assert "货物类型" in result["response"]


def test_generate_response_node_preserves_exact_quote_data(monkeypatch):
    quotes = [{
        "channel_name": "美国普货快线",
        "total_price": 105.0,
        "transit_time": "7-15天",
    }]
    monkeypatch.setattr(nodes, "format_rate_response", lambda results: "美国普货快线：105元，7-15天")
    result = nodes.generate_response_node({"rate_results": quotes})
    assert result["response"] == "美国普货快线：105元，7-15天"
    assert result["rate_results"] == quotes


def test_generate_response_node_has_fixed_no_match_message(monkeypatch):
    monkeypatch.setattr(nodes, "format_rate_response", lambda results: "这段代码不应被调用")
    result = nodes.generate_response_node({"rate_results": []})
    assert result["response"] == "抱歉，未找到符合条件的渠道"


def test_graph_routes_missing_params_to_followup(monkeypatch):
    import agent.graph as graph

    monkeypatch.setattr(graph, "parse_intent_node", lambda state: {
        "intent_type": "rate_query",
        "country": "日本",
        "weight": None,
        "cargo_type": None,
        "missing_params": ["weight", "cargo_type"],
    })
    result = graph.run_once("寄到日本多少钱")
    assert "重量" in result["response"]
    assert "货物类型" in result["response"]


def test_graph_end_to_end_with_followup_data(monkeypatch):
    import agent.graph as graph

    calls = []

    def fake_parse(state):
        calls.append(state["user_input"])
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
            "country": "日本",
            "weight": 2.0,
            "cargo_type": "P服装",
            "missing_params": [],
        }

    expected = [{"channel_name": "日本普货佐川", "total_price": 119.0, "transit_time": "4-7天"}]
    monkeypatch.setattr(graph, "parse_intent_node", fake_parse)
    monkeypatch.setattr(graph, "calculate_rate_node", lambda state: {"rate_results": expected})
    monkeypatch.setattr(graph, "generate_response_node", lambda state: {
        "response": "日本普货佐川：119元，4-7天",
        "rate_results": state["rate_results"],
    })

    first = graph.run_once("寄到日本多少钱")
    second = graph.run_once("2kg衣服", first)
    assert "重量" in first["response"]
    assert "日本普货佐川" in second["response"]
    assert second["rate_results"] == expected
    assert calls == ["寄到日本多少钱", "2kg衣服"]
