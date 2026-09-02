from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any


MODEL_NAME = "qwen3.7-max"
VALID_INTENTS = {"rate_query", "rule_query", "mixed", "chitchat"}

SAFE_FALLBACK: dict[str, Any] = {
    "intent_type": "chitchat",
    "country": None,
    "weight": None,
    "cargo_type": None,
    "missing_params": [],
}

SYSTEM_PROMPT = """你是运费助手的意图提取器。只输出一个 JSON 对象，不要 Markdown、解释或额外文本。
字段必须为：intent_type、country、weight、cargo_type、missing_params。
intent_type 只能是 rate_query、rule_query、mixed、chitchat。
国家提取用户明确提到的目的国家；没有则为 null。
weight 必须统一为 KG 的数字；g/克除以1000，斤乘以0.5；没有则为 null。
cargo_type 提取用户明确描述的货物类型；没有则为 null。
missing_params 仅针对 rate_query 或 mixed，按 country、weight、cargo_type 顺序列出缺失字段；rule_query 和 chitchat 必须为空数组。

示例：
用户：美国5kg普货多少钱
输出：{"intent_type":"rate_query","country":"美国","weight":5.0,"cargo_type":"普货","missing_params":[]}
用户：寄到巴西要多少钱
输出：{"intent_type":"rate_query","country":"巴西","weight":null,"cargo_type":null,"missing_params":["weight","cargo_type"]}
用户：赔偿标准是什么
输出：{"intent_type":"rule_query","country":null,"weight":null,"cargo_type":null,"missing_params":[]}
用户：你好
输出：{"intent_type":"chitchat","country":null,"weight":null,"cargo_type":null,"missing_params":[]}
"""


def _safe_fallback() -> dict[str, Any]:
    return dict(SAFE_FALLBACK)


def _extract_response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        output = response.get("output", response)
        if isinstance(output, dict):
            choices = output.get("choices")
            if choices:
                first = choices[0]
                message = first.get("message", first) if isinstance(first, dict) else first
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, list):
                        return "".join(
                            item.get("text", "") if isinstance(item, dict) else str(item)
                            for item in content
                        )
                    return str(content or "")
            return str(output.get("text", ""))
    output = getattr(response, "output", None)
    if output is not None:
        choices = getattr(output, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if content is not None:
                if isinstance(content, list):
                    return "".join(getattr(item, "text", str(item)) for item in content)
                return str(content)
        text = getattr(output, "text", None)
        if text is not None:
            return str(text)
    return ""


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("intent response must be a JSON object")
    return value


def normalize_weight(value: Any) -> float | None:
    """Convert common Chinese weight expressions to kilograms."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().lower().replace("公斤", "kg")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError(f"invalid weight: {value}")
    number = float(match.group())
    if "斤" in text:
        return number * 0.5
    if "g" in text or "克" in text:
        return number / 1000
    return number


def _finalize(raw: dict[str, Any]) -> dict[str, Any]:
    intent = raw.get("intent_type")
    if intent not in VALID_INTENTS:
        raise ValueError("invalid intent_type")

    country = raw.get("country") or None
    cargo_type = raw.get("cargo_type") or None
    weight = normalize_weight(raw.get("weight"))

    if intent in {"rate_query", "mixed"}:
        missing = []
        if not country:
            missing.append("country")
        if weight is None:
            missing.append("weight")
        if not cargo_type:
            missing.append("cargo_type")
    else:
        missing = []

    return {
        "intent_type": intent,
        "country": str(country).strip() if country else None,
        "weight": weight,
        "cargo_type": str(cargo_type).strip() if cargo_type else None,
        "missing_params": missing,
    }


def _dashscope_call(prompt: str) -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    from dashscope import Generation

    response = Generation.call(
        api_key=api_key,
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        result_format="message",
    )
    return _extract_response_text(response)


def parse_intent(user_input: str, llm_call: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """Extract structured shipping intent, returning a safe fallback on failure."""
    if not isinstance(user_input, str) or not user_input.strip():
        return _safe_fallback()
    try:
        response = llm_call(user_input) if llm_call is not None else _dashscope_call(user_input)
        return _finalize(_parse_json(_extract_response_text(response)))
    except Exception:
        return _safe_fallback()


__all__ = ["MODEL_NAME", "normalize_weight", "parse_intent"]
