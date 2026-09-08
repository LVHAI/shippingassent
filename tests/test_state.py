from typing import get_type_hints

from agent.state import ShippingState


def test_shipping_state_exposes_intent_fields():
    fields = get_type_hints(ShippingState)
    assert set(fields) >= {
        "user_input",
        "intent_type",
        "country",
        "weight",
        "cargo_type",
        "missing_params",
    }
