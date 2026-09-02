from agent.nodes import generate_response_node


def test_rule_response_contains_rule_and_source():
    result = generate_response_node(
        {
            "intent_type": "rule_query",
            "rule_results": [
                {
                    "text": "超长件需提前确认",
                    "rule_category": "尺寸",
                    "sheet_name": "美国专线",
                }
            ],
        }
    )
    assert "超长件需提前确认" in result["response"]
    assert "美国专线" in result["response"]


def test_mixed_response_contains_quote_and_rule():
    result = generate_response_node(
        {
            "intent_type": "mixed",
            "rate_results": [
                {"channel_name": "美国专线", "total_price": 25.0, "transit_time": "7-10天"}
            ],
            "rule_results": [
                {"text": "单边不超过60cm", "rule_category": "尺寸", "sheet_name": "美国专线"}
            ],
        }
    )
    assert "美国专线" in result["response"]
    assert "25元" in result["response"]
    assert "单边不超过60cm" in result["response"]
