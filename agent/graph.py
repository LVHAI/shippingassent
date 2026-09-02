from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    ask_followup_node,
    calculate_rate_node,
    check_params_node,
    generate_response_node,
    parse_intent_node,
    search_rules_node,
)
from agent.state import ShippingState

_CHECKPOINTER = MemorySaver()


def _route_after_check(
    state: ShippingState,
) -> Literal["calculate_rate", "search_rules", "generate_response", "ask_followup"] | list[str]:
    """Route one intent to its execution path(s)."""
    if state.get("route") == "ask_followup":
        return "ask_followup"

    intent = state.get("intent_type", "chitchat")
    if intent == "rate_query":
        return "calculate_rate"
    if intent == "rule_query":
        return "search_rules"
    if intent == "mixed":
        return ["calculate_rate", "search_rules"]
    return "generate_response"


def build_graph(checkpointer: MemorySaver | None = None):
    """Build the complete shipping Agent workflow with conversational persistence."""
    graph = StateGraph(ShippingState)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("check_params", check_params_node)
    graph.add_node("calculate_rate", calculate_rate_node)
    graph.add_node("search_rules", search_rules_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("ask_followup", ask_followup_node)

    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "check_params")
    graph.add_conditional_edges(
        "check_params",
        _route_after_check,
        {
            "calculate_rate": "calculate_rate",
            "search_rules": "search_rules",
            "generate_response": "generate_response",
            "ask_followup": "ask_followup",
        },
    )
    graph.add_edge("calculate_rate", "generate_response")
    graph.add_edge("search_rules", "generate_response")
    graph.add_edge("generate_response", END)
    graph.add_edge("ask_followup", END)
    return graph.compile(checkpointer=checkpointer or _CHECKPOINTER)


def run_once(
    user_input: str,
    previous_state: ShippingState | None = None,
    conversation_id: str = "default",
) -> ShippingState:
    """Run one turn; the checkpointer retains the conversation by conversation_id."""
    config = {"configurable": {"thread_id": conversation_id}}
    if previous_state is not None and previous_state.get("route") == "ask_followup":
        # Keep compatibility with callers that pass an explicit previous state while
        # allowing the checkpointer to remain the source of truth for normal turns.
        state: ShippingState = {
            "user_input": user_input,
            "country": previous_state.get("country"),
            "weight": previous_state.get("weight"),
            "cargo_type": previous_state.get("cargo_type"),
        }
    else:
        state = {"user_input": user_input}
    return workflow.invoke(state, config)


workflow = build_graph()

__all__ = ["build_graph", "run_once", "workflow"]
