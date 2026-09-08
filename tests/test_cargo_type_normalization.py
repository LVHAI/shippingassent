from agent.tools import normalize_cargo_type


def test_replica_sensitive_aliases_normalize_to_p():
    for value in ("P", "P货", "P服装", "仿牌", "敏货", "仿牌/敏货"):
        assert normalize_cargo_type(value) == "P"
