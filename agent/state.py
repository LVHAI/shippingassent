from __future__ import annotations

from typing import TypedDict


class ShippingState(TypedDict, total=False):
    """Extensible state shared by the shipping-assistant workflow."""

    user_input: str
    intent_type: str
    country: str | None
    weight: float | None
    cargo_type: str | None
    missing_params: list[str]
