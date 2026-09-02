import pytest

from agent.tools import _cargo_matches, normalize_cargo_type


def test_sensitive_cargo_is_distinct_from_clothing():
    assert normalize_cargo_type("敏货") == "P"
    assert normalize_cargo_type("服装") == "P服装"
    assert not _cargo_matches("P", "敏货", "TM美国专线Y2-服装")
    assert _cargo_matches("P", "服装", "TM美国专线Y2-服装")


@pytest.mark.parametrize("channel_name", [
    "TM美国专线Y2-服装",
    "TM美国专线Y2_服装",
    "TM美国专线Y2 服装",
])
def test_clothing_channel_does_not_match_sensitive_p(channel_name):
    assert not _cargo_matches("P", "P", channel_name)
