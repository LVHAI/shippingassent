from __future__ import annotations

from typing import Any

from agent.intent_parser import parse_intent
from agent.state import ShippingState
from agent.tools import normalize_cargo_type


def parse_intent_node(state: ShippingState) -> dict[str, Any]:
    """Parse user input and return only the fields changed by this node."""
    result = parse_intent(state.get("user_input", ""))
    cargo_type = result.get("cargo_type")
    if cargo_type:
        cargo_type = normalize_cargo_type(cargo_type)

    intent_type = result.get("intent_type", "chitchat")
    if intent_type in {"rate_query", "mixed"}:
        missing_params: list[str] = []
        if not result.get("country"):
            missing_params.append("country")
        if result.get("weight") is None:
            missing_params.append("weight")
        if not cargo_type:
            missing_params.append("cargo_type")
    else:
        missing_params = []

    return {
        "intent_type": intent_type,
        "country": result.get("country"),
        "weight": result.get("weight"),
        "cargo_type": cargo_type,
        "missing_params": missing_params,
    }


__all__ = ["parse_intent_node"]
