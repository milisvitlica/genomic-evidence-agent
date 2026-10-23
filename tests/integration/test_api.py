from fastapi.testclient import TestClient

from genomic_evidence_agent.api.app import create_app
from genomic_evidence_agent.config import get_settings


def test_invalid_evidence_json_is_appended(tmp_path, monkeypatch):
    destination = tmp_path / "trace-examples.log"
    monkeypatch.setattr("genomic_evidence_agent.agent.trace.TRACE_LOG", destination)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.post(
            "/evidence",
            content='{"question": "be\nnign"}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    text = destination.read_text(encoding="utf-8")
    assert "rejected" in text
    assert "Invalid control character" in text


def test_home_page_is_served():
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Genomic evidence" in response.text
    assert 'id="ask"' in response.text
    assert 'id="save-example"' in response.text


def test_health_lists_tools():
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["tools"] == [
        "query_joined_dataset",
        "query_scored_vus",
        "search_pubmed",
        "get_article_details",
    ]
    assert body["pubmed_mcp"]["transport"] == "stdio"
    assert body["pubmed_mcp"]["error"] is None
    tables = body["tables"]
    assert tables["clinvar_uniprot_joined.parquet"]["exists"] is True
    assert tables["vus_inference_predictions.parquet"]["exists"] is True
