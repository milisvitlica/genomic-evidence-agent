"""Compile the evidence agent as a LangGraph graph.

The graph has three tools: two local dataset queries, and PubMed search loaded
from an in-process MCP server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from genomic_evidence_agent.agent.prompts import SYSTEM_PROMPT
from genomic_evidence_agent.config import Settings, get_settings
from genomic_evidence_agent.mcp.pubmed import load_pubmed_tools
from genomic_evidence_agent.tools.classifier import ClassifierCatalog, build_classifier_tools

logger = logging.getLogger(__name__)


@dataclass
class EvidenceAgent:
    graph: CompiledStateGraph
    catalog: ClassifierCatalog
    tool_names: list[str]
    pubmed_error: str | None
    model: str


async def build_evidence_agent(settings: Settings | None = None) -> EvidenceAgent:
    """Attach the two classifier queries and, when enabled, the PubMed MCP tool."""
    from langchain.agents import create_agent

    settings = settings or get_settings()
    catalog = ClassifierCatalog(settings.classifier_root)
    tools = build_classifier_tools(catalog)
    pubmed_error: str | None = None
    if settings.pubmed_mcp_enabled:
        try:
            tools.extend(await load_pubmed_tools(settings))
        except Exception as exc:
            pubmed_error = f"{type(exc).__name__}: {exc}"
            logger.warning("PubMed MCP tool was not loaded: %s", pubmed_error)

    graph = create_agent(
        settings.model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )
    return EvidenceAgent(
        graph=graph,
        catalog=catalog,
        tool_names=[tool.name for tool in tools],
        pubmed_error=pubmed_error,
        model=settings.model,
    )
