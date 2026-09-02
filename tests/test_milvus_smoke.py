from agent.tools import search_rules


def test_search_rules_empty_query_is_safe():
    assert search_rules("") == []
