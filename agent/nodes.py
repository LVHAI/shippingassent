from __future__ import annotations

import json
import os
from typing import Any, Callable

from agent.intent_parser import parse_intent
from agent.state import ShippingState
from agent.tools import calculate_rate, normalize_cargo_type, search_rules


FOLLOWUP_LABELS = {
    "country": "目的国家",
    "weight": "货物重量（KG）",
    "cargo_type": "货物类型",
}


def parse_intent_node(state: ShippingState) -> dict[str, Any]:
    """Parse user input and retain previously collected follow-up parameters."""
    result = parse_intent(state.get("user_input", ""))
    cargo_type = result.get("cargo_type")
    if cargo_type:
        cargo_type = normalize_cargo_type(cargo_type)

    intent_type = result.get("intent_type", "chitchat")
    country = result.get("country") or state.get("country")
    weight = result.get("weight") if result.get("weight") is not None else state.get("weight")
    cargo_type = cargo_type or state.get("cargo_type")

    if intent_type in {"rate_query", "mixed"}:
        missing_params: list[str] = []
        if not country:
            missing_params.append("country")
        if weight is None:
            missing_params.append("weight")
        if not cargo_type:
            missing_params.append("cargo_type")
    else:
        missing_params = []

    return {
        "intent_type": intent_type,
        "country": country,
        "weight": weight,
        "cargo_type": cargo_type,
        "missing_params": missing_params,
    }


def check_params_node(state: ShippingState) -> dict[str, Any]:
    """Mark the state ready only when rate parameters are complete."""
    if state.get("intent_type") in {"rate_query", "mixed"} and state.get("missing_params"):
        return {"route": "ask_followup"}
    return {"route": "ready"}


def calculate_rate_node(state: ShippingState) -> dict[str, Any]:
    """Calculate quotes deterministically; never use an LLM for price calculation."""
    country = state.get("country")
    weight = state.get("weight")
    cargo_type = state.get("cargo_type")
    if not country or weight is None or not cargo_type:
        return {"rate_results": []}
    return {"rate_results": calculate_rate(country, weight, cargo_type)}


def search_rules_node(state: ShippingState) -> dict[str, Any]:
    """Retrieve shipping rules semantically and store the results in graph state."""
    query = state.get("user_input", "").strip()
    if not query:
        return {"rule_results": []}
    return {"rule_results": search_rules(query=query, top_k=5)}


def _dashscope_format(prompt: str) -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    from dashscope import Generation

    response = Generation.call(
        api_key=api_key,
        model="qwen3.7-max",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是运费助手回复格式化器。只根据给定的报价和规则数据组织自然语言。"
                    "不得修改报价数字、渠道、时效或规则原文；没有依据的数据不得补充。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        result_format="message",
    )
    output = getattr(response, "output", None)
    if output is not None:
        choices = getattr(output, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if content is not None:
                return str(content)
        text = getattr(output, "text", None)
        if text is not None:
            return str(text)
    if isinstance(response, dict):
        output = response.get("output", response)
        choices = output.get("choices", []) if isinstance(output, dict) else []
        if choices:
            message = choices[0].get("message", choices[0])
            return str(message.get("content", "")) if isinstance(message, dict) else str(message)
    return ""


def _deterministic_rate_lines(rate_results: list[dict[str, Any]]) -> str:
    lines = []
    for item in rate_results:
        price = item["total_price"]
        price_text = f"{price:.2f}".rstrip("0").rstrip(".")
        transit = item.get("transit_time") or "未提供"
        lines.append(f"{item['channel_name']}：{price_text}元，时效{transit}")
    return "\n".join(lines)


def _deterministic_rule_lines(rule_results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in rule_results:
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        category = item.get("rule_category") or item.get("category") or "规则"
        sheet = item.get("sheet_name") or "未知来源"
        lines.append(f"【{category}】{text}\n来源：{sheet}")
    return "\n\n".join(lines)


def _llm_response_is_faithful(text: str, rate_results: list[dict[str, Any]]) -> bool:
    if not text.strip():
        return False
    for item in rate_results:
        price = float(item["total_price"])
        price_forms = {str(item["total_price"]), f"{price:.2f}", f"{price:.0f}"}
        if item["channel_name"] not in text or not any(form in text for form in price_forms):
            return False
        transit = item.get("transit_time")
        if transit and transit not in text:
            return False
    return True


def format_rate_response(
    rate_results: list[dict[str, Any]],
    llm_call: Callable[[str], str] | None = None,
) -> str:
    """Format quotes with an LLM while falling back to exact deterministic data."""
    if not rate_results:
        return "抱歉，未找到符合条件的渠道"

    prompt = (
        "请将下面的确定性报价整理成简洁中文回复。报价中的渠道名、价格和时效必须原样保留，"
        "不得自行推算或改写数值。\n\n报价数据：\n"
        + json.dumps(rate_results, ensure_ascii=False)
    )
    try:
        text = llm_call(prompt) if llm_call is not None else _dashscope_format(prompt)
        if _llm_response_is_faithful(text, rate_results):
            return text.strip()
    except Exception:
        pass
    return _deterministic_rate_lines(rate_results)


def _chitchat_response() -> str:
    return "你好！我是运费助手，可以帮你查询运费、时效和物流规则。"


def generate_response_node(state: ShippingState) -> dict[str, Any]:
    """Generate a response from deterministic data, optionally using an LLM formatter."""
    rate_results = state.get("rate_results", [])
    rule_results = state.get("rule_results", [])
    intent_type = state.get("intent_type", "chitchat")

    if intent_type == "chitchat":
        return {"response": _chitchat_response(), "rate_results": rate_results, "rule_results": rule_results}

    if intent_type == "rule_query":
        response = _deterministic_rule_lines(rule_results) or "抱歉，暂未找到相关物流规则。"
        return {"response": response, "rate_results": rate_results, "rule_results": rule_results}

    if intent_type == "mixed":
        rate_text = format_rate_response(rate_results) if rate_results else "抱歉，未找到符合条件的渠道"
        rule_text = _deterministic_rule_lines(rule_results) or "暂未找到相关规则。"
        return {
            "response": f"报价：\n{rate_text}\n\n规则：\n{rule_text}",
            "rate_results": rate_results,
            "rule_results": rule_results,
        }

    return {"response": format_rate_response(rate_results), "rate_results": rate_results, "rule_results": rule_results}


def ask_followup_node(state: ShippingState) -> dict[str, Any]:
    """Ask only for the parameters still missing from the current conversation."""
    missing = state.get("missing_params", [])
    labels = [FOLLOWUP_LABELS[item] for item in missing if item in FOLLOWUP_LABELS]
    if len(labels) == 1:
        message = f"请告诉我{labels[0]}。"
    elif labels:
        message = "请告诉我" + "和".join(labels) + "。"
    else:
        message = "请告诉我您的目的国家、货物重量和货物类型。"
    return {"response": message}


__all__ = [
    "ask_followup_node",
    "calculate_rate_node",
    "check_params_node",
    "format_rate_response",
    "generate_response_node",
    "parse_intent_node",
    "search_rules_node",
]
