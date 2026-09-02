from agent.nodes import format_rate_response


def _rate(channel: str, total: float, weight_min: float, weight_max: float | None):
    return {
        "channel_name": channel,
        "total_price": total,
        "transit_time": "10-15天",
        "weight_min": weight_min,
        "weight_max": weight_max,
    }


def test_format_rate_response_keeps_all_channels_and_weight_bands():
    results = [
        _rate("欧美标准专线", 362, 1, 3),
        _rate("美国专线小包", 348, 1, 3),
        _rate("美国专线小包", 348, 3, 6),
        _rate("TM美国专线Y2", 330, 1, 3),
    ]

    text = format_rate_response(results, llm_call=lambda prompt: "")

    assert "欧美标准专线" in text
    assert "美国专线小包" in text
    assert "TM美国专线Y2" in text
    assert "1-3kg" in text
    assert "3-6kg" in text
