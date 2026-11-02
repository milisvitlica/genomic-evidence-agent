from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """One tool call or tool result recorded while the agent answered."""
    type: str
    timestamp: str
    name: str | None = None
    args: dict[str, Any] | None = None
    content: str | None = None


class EvidenceRequest(BaseModel):
    """Body of ``POST /evidence``: the question and an optional thread to continue."""
    question: str = Field(min_length=1, description="Natural-language question about a variant, gene, or paper.")
    thread_id: str | None = Field(
        default=None,
        description="Reuse a thread to keep the conversation. Omitted starts a new thread.",
    )


class EvidenceResponse(BaseModel):
    """Reply of ``POST /evidence``: the answer, its thread id, and the tool trace."""
    answer: str
    thread_id: str
    trace: list[TraceEvent] = Field(default_factory=list)


class SaveExampleRequest(BaseModel):
    """Body of ``POST /examples``: the thread to save as an example file."""
    thread_id: str = Field(min_length=1, description="Conversation to write as an example file.")


class SaveExampleResponse(BaseModel):
    """Reply of ``POST /examples``: where the file was written."""
    path: str


class HealthResponse(BaseModel):
    """Reply of ``GET /health``: model, table status, tool names, and PubMed MCP status."""
    status: str
    model: str
    tables: dict[str, dict]
    tools: list[str]
    pubmed_mcp: dict[str, str | bool | None]
