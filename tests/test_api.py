from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from genomic_evidence_agent.agent.trace import trace_messages
from genomic_evidence_agent.api.app import create_app, message_text
from genomic_evidence_agent.config import get_settings


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
    events = trace_messages(messages)
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
    assert events == [
        {
            "type": "tool_call",
            "name": "query_joined_dataset",
            "args": {"variation_id": 7884},
            "content": None,
        },
        {
            "type": "tool_result",
            "name": "query_joined_dataset",
            "args": None,
            "content": '{"n_matches": 1, "records": [{"gene": "ABCA4"}]}',
        },
    ]


def test_message_text_flattens_blocks():
    assert message_text("plain") == "plain"
    assert message_text([{"type": "text", "text": "hello"}]) == "hello"


def test_health_lists_three_tools():
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["tools"] == ["query_joined_dataset", "query_scored_vus", "search_pubmed"]
    assert body["pubmed_mcp"]["transport"] == "in-process"
    assert body["pubmed_mcp"]["error"] is None
    tables = body["tables"]
    assert tables["clinvar_uniprot_joined.parquet"]["exists"] is True
    assert tables["vus_inference_predictions.parquet"]["exists"] is True
