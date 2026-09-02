import logging


def test_parse_intent_logs_exception(caplog):
    from agent.intent_parser import parse_intent

    def failing_llm(_):
        raise RuntimeError("dashscope unavailable")

    with caplog.at_level(logging.ERROR):
        result = parse_intent("美国2kg普货多少钱", llm_call=failing_llm)

    assert result["intent_type"] == "chitchat"
    assert "intent.parse.failed" in caplog.text
    assert "dashscope unavailable" in caplog.text


def test_run_stream_emits_standardized_node_events(monkeypatch):
    from agent.graph import run_stream

    class FakeWorkflow:
        def stream(self, state, config, stream_mode):
            assert state == {"user_input": "美国2kg普货多少钱"}
            assert config == {"configurable": {"thread_id": "conv-1"}}
            assert stream_mode == "updates"
            yield {"parse_intent": {"intent_type": "rate_query"}}
            yield {"generate_response": {"response": "DHL：100元"}}

    import agent.graph as graph
    monkeypatch.setattr(graph, "workflow", FakeWorkflow())

    events = list(run_stream("美国2kg普货多少钱", conversation_id="conv-1"))

    assert events == [
        {"event": "node_update", "node": "parse_intent", "data": {"intent_type": "rate_query"}},
        {"event": "node_update", "node": "generate_response", "data": {"response": "DHL：100元"}},
    ]


def test_run_agent_streaming_keeps_final_response(monkeypatch):
    import app

    monkeypatch.setattr(
        app,
        "run_stream",
        lambda user_input, conversation_id: iter([
            {"event": "node_update", "node": "parse_intent", "data": {"intent_type": "rate_query"}},
            {"event": "node_update", "node": "generate_response", "data": {"response": "DHL：100元"}},
        ]),
    )

    events = list(app.run_agent_stream("美国2kg普货多少钱", "conv-1"))

    assert events[-1]["data"]["response"] == "DHL：100元"
