"""In-process PubMed MCP server.

The search itself lives in ``tools/pubmed.py``. This module exposes that
function through FastMCP and adapts the resulting tool for the LangGraph agent.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from genomic_evidence_agent.config import Settings
from genomic_evidence_agent.tools.pubmed import DEFAULT_MAX_RESULTS, search_pubmed


def build_pubmed_server(settings: Settings) -> FastMCP:
    """MCP server with a single literature-search tool."""
    server = FastMCP("pubmed")

    @server.tool(name="search_pubmed")
    def search_pubmed_tool(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
        """Search PubMed and return PMID, title, authors, journal, date, and DOI.

        query uses PubMed syntax (gene symbols, variant names, Boolean operators).
        This returns article metadata only, so a later ranking step can reorder
        these hits. It does not download full text.
        """
        return search_pubmed(
            query,
            max_results=max_results,
            api_key=settings.ncbi_api_key,
            email=settings.ncbi_email,
        )

    return server


async def load_pubmed_tools(settings: Settings) -> list:
    """Discover the PubMed MCP tool and return it as a LangChain tool."""
    from langchain.mcp import MCPAdapter

    async with MCPAdapter(build_pubmed_server(settings)) as adapter:
        return await adapter.list_tools()
