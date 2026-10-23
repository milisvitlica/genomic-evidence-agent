import asyncio
import json

from genomic_evidence_agent.config import Settings
from genomic_evidence_agent.mcp.pubmed_server import connect_pubmed_mcp


def test_pubmed_mcp_exposes_search_and_article_details():
    settings = Settings(pubmed_mcp_enabled=True, ncbi_api_key=None, ncbi_email=None)

    async def run() -> None:
        connection = await connect_pubmed_mcp(settings)
        try:
            by_name = {tool.name: tool for tool in connection.tools}
            assert list(by_name) == ["search_pubmed", "get_article_details"]
            search_schema = _schema(by_name["search_pubmed"])
            details_schema = _schema(by_name["get_article_details"])
            assert "query" in json.dumps(search_schema)
            assert "pmid" in json.dumps(details_schema)
            details = await by_name["get_article_details"].ainvoke({"pmid": " "})
            assert "Provide a PubMed PMID." in json.dumps(details)
        finally:
            await connection.aclose()

    asyncio.run(run())


def _schema(tool) -> object:
    schema = tool.args_schema
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    return schema
