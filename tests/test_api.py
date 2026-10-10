from fastapi.testclient import TestClient

from genomic_evidence_agent.api.app import create_app, message_text
from genomic_evidence_agent.config import get_settings


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
