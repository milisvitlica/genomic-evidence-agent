from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    type: str
    timestamp: str
    name: str | None = None
    args: dict[str, Any] | None = None
    content: str | None = None


class EvidenceRequest(BaseModel):
    question: str = Field(min_length=1, description="Natural-language question about a variant, gene, or paper.")
    thread_id: str | None = Field(
        default=None,
        description="Reuse a thread to keep the conversation. Omitted starts a new thread.",
    )


class EvidenceResponse(BaseModel):
    answer: str
    thread_id: str
    trace: list[TraceEvent] = Field(default_factory=list)


class SaveExampleRequest(BaseModel):
    thread_id: str = Field(min_length=1, description="Conversation to write as an example file.")


class SaveExampleResponse(BaseModel):
    path: str


class HealthResponse(BaseModel):
    status: str
    model: str
    tables: dict[str, dict]
    tools: list[str]
    pubmed_mcp: dict[str, str | bool | None]
