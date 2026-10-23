import asyncio
import json

from genomic_evidence_agent.config import Settings
from genomic_evidence_agent.mcp.pubmed_server import load_pubmed_tools


def test_pubmed_mcp_exposes_one_search_tool():
    settings = Settings(pubmed_mcp_enabled=True, ncbi_api_key=None, ncbi_email=None)
    tools = asyncio.run(load_pubmed_tools(settings))
    assert [tool.name for tool in tools] == ["search_pubmed"]
    schema = tools[0].args_schema
    if hasattr(schema, "model_json_schema"):
        schema = schema.model_json_schema()
    assert "query" in json.dumps(schema)
