import agent.nodes as nodes
from data_pipeline.sqlite_loader import init_db, load_rates
from data_pipeline.xls_parser import ChannelRate


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


def test_generate_response_node_has_fixed_no_match_message():
    result = nodes.generate_response_node({"rate_results": []})
    assert result["response"] == "抱歉，未找到符合条件的渠道"


def test_format_rate_response_rejects_llm_modified_price():
    quotes = [{"channel_name": "美国普货快线", "total_price": 105.0, "transit_time": "7-15天"}]
    result = nodes.format_rate_response(quotes, llm_call=lambda prompt: "美国普货快线：99元，时效7-15天")
    assert result == "美国普货快线：105元，时效7-15天"


def test_format_rate_response_accepts_faithful_llm_response():
    quotes = [{"channel_name": "美国普货快线", "total_price": 105.0, "transit_time": "7-15天"}]
    result = nodes.format_rate_response(quotes, llm_call=lambda prompt: "推荐美国普货快线，价格105元，时效7-15天。")
    assert result == "推荐美国普货快线，价格105元，时效7-15天。"


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


def test_initial_state_clears_completed_turn_fields():
    import agent.graph as graph

    state = graph._initial_state(
        "寄美国，3公斤",
        {
            "route": "ready",
            "country": "美国",
            "weight": 3.0,
            "cargo_type": "P",
        },
    )
    assert state == {
        "user_input": "寄美国，3公斤",
        "country": None,
        "weight": None,
        "cargo_type": None,
    }


def test_initial_state_preserves_context_for_followup():
    import agent.graph as graph

    state = graph._initial_state(
        "3公斤普货",
        {
            "route": "ask_followup",
            "country": "美国",
            "weight": None,
            "cargo_type": None,
        },
    )
    assert state == {
        "user_input": "3公斤普货",
        "route": "ask_followup",
        "country": "美国",
        "weight": None,
        "cargo_type": None,
    }


def test_graph_real_rate_engine_returns_quote_for_us_5kg(tmp_path, monkeypatch):
    db = tmp_path / "shipping.db"
    init_db(db)
    load_rates([ChannelRate(
        sheet_name="美国专线小包",
        channel_name="美国普货快线",
        countries="美国",
        cargo_type="普货",
        weight_min=0.05,
        weight_max=10,
        price_per_kg=20,
        handling_fee=5,
        transit_time="7-15天",
    )], db)
    monkeypatch.setenv("SHIPPING_DB_PATH", str(db))
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "普货",
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "美国5kg普货多少钱"})
    result.update(nodes.check_params_node(result))
    result.update(nodes.calculate_rate_node(result))
    assert result["rate_results"][0]["channel_name"] == "美国普货快线"
    assert result["rate_results"][0]["total_price"] == 105
    assert result["rate_results"][0]["transit_time"] == "7-15天"


def test_graph_real_rate_engine_returns_apology_when_no_match(tmp_path, monkeypatch):
    db = tmp_path / "shipping.db"
    init_db(db)
    monkeypatch.setenv("SHIPPING_DB_PATH", str(db))
    result = nodes.generate_response_node({"rate_results": []})
    assert result["response"] == "抱歉，未找到符合条件的渠道"
