from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.logging_config import get_logger
from agent.nodes import (
    ask_followup_node,
    calculate_rate_node,
    check_params_node,
    generate_response_node,
    parse_intent_node,
    search_rules_node,
)
from agent.state import ShippingState


logger = get_logger("graph")
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


def _initial_state(user_input: str, previous_state: ShippingState | None) -> ShippingState:
    if previous_state is not None and previous_state.get("route") == "ask_followup":
        return {
            "user_input": user_input,
            "route": "ask_followup",
            "country": previous_state.get("country"),
            "weight": previous_state.get("weight"),
            "cargo_type": previous_state.get("cargo_type"),
        }
    # A completed turn must not leak its parsed parameters into an independent query.
    # Explicit nulls are required because LangGraph merges partial state with the checkpoint.
    return {
        "user_input": user_input,
        "country": None,
        "weight": None,
        "cargo_type": None,
        "route": None,
    }


def run_stream(
    user_input: str,
    previous_state: ShippingState | None = None,
    conversation_id: str = "default",
) -> Iterator[dict]:
    """Stream standardized node updates while retaining LangGraph checkpoint state."""
    state = _initial_state(user_input, previous_state)
    config = {"configurable": {"thread_id": conversation_id}}
    logger.info("workflow.start thread_id=%s input_chars=%d", conversation_id, len(user_input))
    started = time.perf_counter()
    try:
        for update in workflow.stream(state, config, stream_mode="updates"):
            if not isinstance(update, dict):
                logger.warning("workflow.unexpected_update type=%s", type(update).__name__)
                continue
            for node, data in update.items():
                logger.info("workflow.stream node=%s keys=%s", node, sorted(data) if isinstance(data, dict) else [])
                event = {"event": "node_update", "node": node, "data": data if isinstance(data, dict) else {"value": data}}
                yield event
        logger.info("workflow.end thread_id=%s elapsed_ms=%.1f", conversation_id, (time.perf_counter() - started) * 1000)
    except Exception:
        logger.exception("workflow.failed thread_id=%s elapsed_ms=%.1f", conversation_id, (time.perf_counter() - started) * 1000)
        raise


def run_once(
    user_input: str,
    previous_state: ShippingState | None = None,
    conversation_id: str = "default",
) -> ShippingState:
    """Run one turn; the checkpointer retains the conversation by conversation_id."""
    config = {"configurable": {"thread_id": conversation_id}}
    state = _initial_state(user_input, previous_state)
    logger.info("workflow.invoke.start thread_id=%s input_chars=%d", conversation_id, len(user_input))
    started = time.perf_counter()
    try:
        result = workflow.invoke(state, config)
        logger.info("workflow.invoke.end thread_id=%s elapsed_ms=%.1f response_chars=%d", conversation_id, (time.perf_counter() - started) * 1000, len(str(result.get("response", ""))))
        return result
    except Exception:
        logger.exception("workflow.invoke.failed thread_id=%s elapsed_ms=%.1f", conversation_id, (time.perf_counter() - started) * 1000)
        raise


workflow = build_graph()

__all__ = ["build_graph", "run_once", "run_stream", "workflow"]
