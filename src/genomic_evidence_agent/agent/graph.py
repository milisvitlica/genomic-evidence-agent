"""Compile the evidence agent as a LangGraph graph.

The graph has four tools: two local dataset queries, plus PubMed search and
article details from the stdio MCP server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from genomic_evidence_agent.agent.prompts import SYSTEM_PROMPT
from genomic_evidence_agent.config import Settings, get_settings
from genomic_evidence_agent.mcp.pubmed_server import PubmedMcp, connect_pubmed_mcp
from genomic_evidence_agent.tools.classifier import ClassifierCatalog, build_classifier_tools

logger = logging.getLogger(__name__)


@dataclass
class EvidenceAgent:
    graph: CompiledStateGraph
    catalog: ClassifierCatalog
    tool_names: list[str]
    pubmed_error: str | None
    model: str
    pubmed_mcp: PubmedMcp | None = None

    async def aclose(self) -> None:
        """Stop the PubMed stdio process, if this agent started one."""
        if self.pubmed_mcp is not None:
            await self.pubmed_mcp.aclose()
            self.pubmed_mcp = None


async def build_evidence_agent(settings: Settings | None = None) -> EvidenceAgent:
    """Attach the two classifier queries and, when enabled, the PubMed MCP tools."""
    from langchain.agents import create_agent

    settings = settings or get_settings()
    catalog = ClassifierCatalog(settings.classifier_root)
    tools = build_classifier_tools(catalog)
    pubmed_error: str | None = None
    pubmed_mcp: PubmedMcp | None = None
    if settings.pubmed_mcp_enabled:
        try:
            pubmed_mcp = await connect_pubmed_mcp(settings)
            tools.extend(pubmed_mcp.tools)
        except Exception as exc:
            pubmed_error = f"{type(exc).__name__}: {exc}"
            logger.warning("PubMed MCP tools were not loaded: %s", pubmed_error)

    try:
        graph = create_agent(
            settings.model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=MemorySaver(),
        )
    except Exception:
        if pubmed_mcp is not None:
            await pubmed_mcp.aclose()
        raise
    return EvidenceAgent(
        graph=graph,
        catalog=catalog,
        tool_names=[tool.name for tool in tools],
        pubmed_error=pubmed_error,
        model=settings.model,
        pubmed_mcp=pubmed_mcp,
    )
