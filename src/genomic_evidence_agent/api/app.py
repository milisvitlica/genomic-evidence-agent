"""HTTP API for the evidence agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse

from genomic_evidence_agent.agent.graph import EvidenceAgent, build_evidence_agent
from genomic_evidence_agent.agent.trace import ToolTiming, log_rejected, log_trace, trace_messages
from genomic_evidence_agent.api.schemas import (
    EvidenceRequest,
    EvidenceResponse,
    HealthResponse,
    SaveExampleRequest,
    SaveExampleResponse,
)
from genomic_evidence_agent.tools.examples import save_conversation
from genomic_evidence_agent.config import get_settings

PAGE = Path(__file__).resolve().parent / "static" / "index.html"


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
        try:
            yield
        finally:
            await app.state.runtime.aclose()

    app = FastAPI(
        title="Genomic Evidence Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def log_invalid_request(request: Request, exc: RequestValidationError):
        if request.url.path == "/evidence":
            errors = exc.errors()
            first = errors[0] if errors else {}
            detail = str((first.get("ctx") or {}).get("error") or first.get("msg") or "Request validation failed.")
            log_rejected(detail, body=exc.body)
        return await request_validation_exception_handler(request, exc)

    @app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(PAGE)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        runtime: EvidenceAgent = app.state.runtime
        return HealthResponse(
            status="ok",
            model=runtime.model,
            tables=runtime.catalog.table_status(),
            tools=runtime.tool_names,
            pubmed_mcp={
                "enabled": get_settings().pubmed_mcp_enabled,
                "transport": "stdio",
                "error": runtime.pubmed_error,
            },
        )

    @app.post("/examples", response_model=SaveExampleResponse)
    async def save_example(body: SaveExampleRequest) -> SaveExampleResponse:
        runtime: EvidenceAgent = app.state.runtime
        snapshot = await runtime.graph.aget_state({"configurable": {"thread_id": body.thread_id}})
        messages = (snapshot.values or {}).get("messages") or []
        try:
            path = save_conversation(messages)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SaveExampleResponse(path=path)

    @app.post("/evidence", response_model=EvidenceResponse)
    async def evidence(body: EvidenceRequest) -> EvidenceResponse:
        runtime: EvidenceAgent = app.state.runtime
        thread_id = body.thread_id or str(uuid4())
        timing = ToolTiming()
        try:
            result = await runtime.graph.ainvoke(
                {"messages": [{"role": "user", "content": body.question}]},
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 24,
                    "callbacks": [timing],
                },
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc
        messages = result.get("messages") or []
        if not messages:
            raise HTTPException(status_code=502, detail="Agent returned no messages.")
        trace = trace_messages(messages, timing=timing)
        answer = message_text(messages[-1].content)
        log_trace(body.question, trace, answer=answer)
        return EvidenceResponse(
            answer=answer,
            thread_id=thread_id,
            trace=trace,
        )

    return app


app = create_app()
