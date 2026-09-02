from agent.intent_parser import parse_intent


def test_parse_intent_converts_weight_units():
    result = parse_intent(
        "寄500g到美国",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"500g","cargo_type":"普货"}',
    )
    assert result["weight"] == 0.5


def test_parse_intent_converts_jin_to_kg():
    result = parse_intent(
        "寄2斤到美国",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"2斤","cargo_type":"普货"}',
    )
    assert result["weight"] == 1.0


def test_parse_intent_keeps_kg():
    result = parse_intent(
        "美国5kg普货多少钱",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"5kg","cargo_type":"普货"}',
    )
    assert result["weight"] == 5.0


def test_parse_intent_rejects_malformed_json_as_safe_fallback():
    result = parse_intent("hello", llm_call=lambda _: "not-json")
    assert result == {
        "intent_type": "chitchat",
        "country": None,
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    }


def test_parse_intent_provider_exception_is_safe_fallback():
    def broken(_: str):
        raise RuntimeError("provider unavailable")

    result = parse_intent("你好", llm_call=broken)
    assert result["intent_type"] == "chitchat"
    assert result["missing_params"] == []
