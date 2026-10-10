"""HTTP API for the evidence agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from genomic_evidence_agent.agent.graph import EvidenceAgent, build_evidence_agent
from genomic_evidence_agent.api.schemas import EvidenceRequest, EvidenceResponse, HealthResponse
from genomic_evidence_agent.config import get_settings


def message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(part for part in parts if part)
    return str(content)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = await build_evidence_agent()
        yield

    app = FastAPI(
        title="Genomic Evidence Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        runtime: EvidenceAgent = app.state.runtime
        return HealthResponse(
            status="ok",
            model=runtime.model,
            classifier_root=str(runtime.catalog.root),
            tables=runtime.catalog.table_status(),
            tools=runtime.tool_names,
            pubmed_mcp={
                "enabled": get_settings().pubmed_mcp_enabled,
                "transport": "in-process",
                "error": runtime.pubmed_error,
            },
        )

    @app.post("/evidence", response_model=EvidenceResponse)
    async def evidence(body: EvidenceRequest) -> EvidenceResponse:
        runtime: EvidenceAgent = app.state.runtime
        thread_id = body.thread_id or str(uuid4())
        try:
            result = await runtime.graph.ainvoke(
                {"messages": [{"role": "user", "content": body.question}]},
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": 24},
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc
        messages = result.get("messages") or []
        if not messages:
            raise HTTPException(status_code=502, detail="Agent returned no messages.")
        return EvidenceResponse(answer=message_text(messages[-1].content), thread_id=thread_id)

    return app


app = create_app()
