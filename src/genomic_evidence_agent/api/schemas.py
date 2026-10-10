from pydantic import BaseModel, Field


class EvidenceRequest(BaseModel):
    question: str = Field(min_length=1, description="Natural-language question about a variant, gene, or paper.")
    thread_id: str | None = Field(
        default=None,
        description="Reuse a thread to keep the conversation. Omitted starts a new thread.",
    )


class EvidenceResponse(BaseModel):
    answer: str
    thread_id: str


class HealthResponse(BaseModel):
    status: str
    model: str
    classifier_root: str
    tables: dict[str, dict]
    tools: list[str]
    pubmed_mcp: dict[str, str | bool | None]
