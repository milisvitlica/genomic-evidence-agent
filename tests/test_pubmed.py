import asyncio
import json

import httpx

from genomic_evidence_agent.config import Settings
from genomic_evidence_agent.mcp.pubmed import load_pubmed_tools, parse_pubmed_summary, search_pubmed


def test_parse_pubmed_summary_keeps_pmid_order():
    payload = {
        "result": {
            "uids": ["2", "1"],
            "1": {
                "title": "First paper",
                "source": "Nat Genet",
                "pubdate": "2020 Jan",
                "authors": [{"name": "Ada A"}, {"name": "Bea B"}],
                "articleids": [{"idtype": "doi", "value": "10.1/first"}],
            },
            "2": {
                "title": "Second paper",
                "source": "Science",
                "pubdate": "2021",
                "authors": [],
                "articleids": [],
            },
        }
    }
    articles = parse_pubmed_summary(payload, ["2", "1"])
    assert [article["pmid"] for article in articles] == ["2", "1"]
    assert articles[1]["doi"] == "10.1/first"
    assert articles[1]["authors"] == ["Ada A", "Bea B"]


def test_search_pubmed_uses_esearch_then_esummary():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/esearch.fcgi"):
            assert request.url.params["term"] == "BRCA1"
            assert request.url.params["api_key"] == "secret"
            return httpx.Response(200, json={"esearchresult": {"idlist": ["42"]}})
        body = {
            "result": {
                "42": {
                    "title": "BRCA1 study",
                    "source": "Nature",
                    "pubdate": "2024",
                    "authors": [{"name": "Lee L"}],
                    "articleids": [{"idtype": "pubmed", "value": "42"}],
                }
            }
        }
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = search_pubmed("BRCA1", max_results=3, api_key="secret", client=client)
    assert payload["n_results"] == 1
    assert payload["articles"][0]["pmid"] == "42"
    assert payload["articles"][0]["title"] == "BRCA1 study"


def test_pubmed_mcp_exposes_one_search_tool():
    settings = Settings(pubmed_mcp_enabled=True, ncbi_api_key=None, ncbi_email=None)
    tools = asyncio.run(load_pubmed_tools(settings))
    assert [tool.name for tool in tools] == ["search_pubmed"]
    schema = tools[0].args_schema
    if hasattr(schema, "model_json_schema"):
        schema = schema.model_json_schema()
    assert "query" in json.dumps(schema)
