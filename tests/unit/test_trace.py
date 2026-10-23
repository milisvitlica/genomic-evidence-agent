from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from genomic_evidence_agent.agent.trace import ToolTiming, log_rejected, log_trace, trace_messages
from genomic_evidence_agent.api.app import message_text


def test_trace_messages_records_calls_and_results():
    messages = [
        HumanMessage(content="What is VariationID 7884?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "query_joined_dataset",
                    "args": {"variation_id": 7884},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content='{"n_matches": 1, "records": [{"gene": "ABCA4"}]}',
            name="query_joined_dataset",
            tool_call_id="call-1",
        ),
        AIMessage(content="ABCA4, labeled benign."),
    ]
    events = trace_messages(messages, clock=lambda: "2026-10-11T16:35:00.000+00:00")
    wrapped = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_pubmed", "args": {"query": "ABCA4"}, "id": "call-2", "type": "tool_call"}],
        ),
        ToolMessage(
            content=[{"type": "text", "text": '{"n_results": 1}'}],
            name="search_pubmed",
            tool_call_id="call-2",
        ),
    ]
    pubmed = trace_messages(wrapped)
    assert pubmed[1]["content"] == '{"n_results": 1}'
    timing = ToolTiming()
    timing.started.append("2026-10-11T16:35:01.000+00:00")
    timing.ended.append("2026-10-11T16:35:01.250+00:00")
    timed = trace_messages(messages, timing=timing)
    assert timed[0]["timestamp"] == "2026-10-11T16:35:01.000+00:00"
    assert timed[1]["timestamp"] == "2026-10-11T16:35:01.250+00:00"
    assert events == [
        {
            "type": "tool_call",
            "timestamp": "2026-10-11T16:35:00.000+00:00",
            "name": "query_joined_dataset",
            "args": {"variation_id": 7884},
            "content": None,
        },
        {
            "type": "tool_result",
            "timestamp": "2026-10-11T16:35:00.000+00:00",
            "name": "query_joined_dataset",
            "args": None,
            "content": '{"n_matches": 1, "records": [{"gene": "ABCA4"}]}',
        },
    ]


def test_log_trace_appends_calls_to_the_trace_file(tmp_path):
    destination = tmp_path / "trace-examples.log"
    log_trace(
        "What is VariationID 7884?",
        [
            {
                "type": "tool_call",
                "timestamp": "2026-10-11T16:35:01.000+00:00",
                "name": "query_joined_dataset",
                "args": {"variation_id": 7884},
                "content": None,
            },
            {
                "type": "tool_result",
                "timestamp": "2026-10-11T16:35:01.250+00:00",
                "name": "query_joined_dataset",
                "args": None,
                "content": '{"n_matches": 1}',
            },
        ],
        answer="ABCA4, labeled benign.",
        path=destination,
    )
    log_rejected("Invalid control character at", body='{"question": "be\nnign"}', path=destination)
    text = destination.read_text(encoding="utf-8")
    assert "CALL query_joined_dataset" in text
    assert "RESPONSE query_joined_dataset" in text
    assert "ANSWER ABCA4, labeled benign." in text
    assert "rejected" in text
    assert "Invalid control character at" in text


def test_message_text_flattens_blocks():
    assert message_text("plain") == "plain"
    assert message_text([{"type": "text", "text": "hello"}]) == "hello"
