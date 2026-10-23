"""PubMed MCP server.

The PubMed functions live in ``tools/pubmed.py``. This module exposes them
through FastMCP. ``python -m genomic_evidence_agent.mcp`` serves them over
stdio, and the evidence agent launches that same command.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport

from genomic_evidence_agent.config import Settings, repo_root
from genomic_evidence_agent.tools.pubmed import DEFAULT_MAX_RESULTS, get_article_details, search_pubmed


def build_pubmed_server(settings: Settings) -> FastMCP:
    """MCP server with PubMed search and one-article details."""
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

    @server.tool(name="get_article_details")
    def get_article_details_tool(pmid: str) -> dict[str, Any]:
        """Retrieve PubMed metadata and the abstract for one PMID.

        Use this after search_pubmed when a hit needs its abstract. pmid is the
        PubMed identifier. This does not download the full text.
        """
        return get_article_details(
            pmid,
            api_key=settings.ncbi_api_key,
            email=settings.ncbi_email,
        )

    return server


def pubmed_stdio_transport(settings: Settings) -> StdioTransport:
    """Stdio command any client can run: ``python -m genomic_evidence_agent.mcp``."""
    src = str(repo_root() / "src")
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = existing.split(os.pathsep) if existing else []
    if src not in parts:
        env["PYTHONPATH"] = os.pathsep.join([src, *parts]) if parts else src
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"
    if settings.ncbi_api_key:
        env["NCBI_API_KEY"] = settings.ncbi_api_key
    if settings.ncbi_email:
        env["NCBI_EMAIL"] = settings.ncbi_email
    return StdioTransport(
        command=sys.executable,
        args=["-m", "genomic_evidence_agent.mcp"],
        env=env,
        cwd=str(repo_root()),
        keep_alive=False,
    )


@dataclass
class PubmedMcp:
    """One stdio session. Hold it for the agent lifetime, then call ``aclose``."""

    _adapter: Any
    tools: list

    async def aclose(self) -> None:
        await self._adapter.__aexit__(None, None, None)


async def connect_pubmed_mcp(settings: Settings) -> PubmedMcp:
    """Start the PubMed stdio server and keep its session open."""
    from langchain.mcp import MCPAdapter

    adapter = MCPAdapter(Client(pubmed_stdio_transport(settings)))
    await adapter.__aenter__()
    try:
        tools = await adapter.list_tools()
    except Exception:
        await adapter.__aexit__(*sys.exc_info())
        raise
    return PubmedMcp(adapter, tools)
