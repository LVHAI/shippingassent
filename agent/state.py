from __future__ import annotations

from typing import Any, TypedDict


class ShippingState(TypedDict, total=False):
    """Extensible state shared by the shipping-assistant workflow."""

    user_input: str
    intent_type: str
    country: str | None
    weight: float | None
    cargo_type: str | None
    cargo_types: list[str] | None
    missing_params: list[str]
    route: str | None
    rate_results: list[dict[str, Any]]
    rule_results: list[dict[str, Any]]
    response: str
