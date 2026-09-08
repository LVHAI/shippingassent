from agent.intent_parser import normalize_weight, parse_intent


def test_normalize_weight():
    assert normalize_weight("5kg") == 5.0
    assert normalize_weight("500g") == 0.5
    assert normalize_weight("4斤") == 2.0


def test_parse_intent_normalizes_llm_json():
    result = parse_intent(
        "美国5kg普货多少钱",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"5kg","cargo_type":"普货"}',
    )
    assert result == {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "普货",
        "missing_params": [],
    }


def test_parse_intent_supports_followup_intent():
    result = parse_intent(
        "2kg衣服",
        llm_call=lambda _: '{"intent_type":"followup","country":null,"weight":"2kg","cargo_type":"衣服"}',
    )
    assert result["intent_type"] == "followup"
    assert result["weight"] == 2.0
    assert result["cargo_type"] == "衣服"
