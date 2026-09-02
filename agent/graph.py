from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    ask_followup_node,
    calculate_rate_node,
    check_params_node,
    generate_response_node,
    parse_intent_node,
)
from agent.state import ShippingState


def _route_after_check(state: ShippingState) -> Literal["calculate_rate", "ask_followup"]:
    return "calculate_rate" if state.get("route") == "ready" else "ask_followup"


def build_graph():
    """Build and compile the Task 06 LangGraph workflow."""
    graph = StateGraph(ShippingState)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("check_params", check_params_node)
    graph.add_node("calculate_rate", calculate_rate_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("ask_followup", ask_followup_node)

    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "check_params")
    graph.add_conditional_edges(
        "check_params",
        _route_after_check,
        {"calculate_rate": "calculate_rate", "ask_followup": "ask_followup"},
    )
    graph.add_edge("calculate_rate", "generate_response")
    graph.add_edge("generate_response", END)
    graph.add_edge("ask_followup", END)
    return graph.compile()


def run_once(user_input: str, previous_state: ShippingState | None = None) -> ShippingState:
    """Run one conversational turn, retaining parameters only after a follow-up."""
    state: ShippingState = {"user_input": user_input}
    if previous_state and previous_state.get("route") == "ask_followup":
        state.update({
            key: value
            for key, value in previous_state.items()
            if key in {"country", "weight", "cargo_type"}
        })
    return build_graph().invoke(state)


workflow = build_graph()

__all__ = ["build_graph", "run_once", "workflow"]
