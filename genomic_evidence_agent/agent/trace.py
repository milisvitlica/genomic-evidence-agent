"""Extract tool calls and tool results from a LangGraph message list."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("genomic_evidence_agent.trace")

# genomic_evidence_agent/agent/trace.py -> repository root is parents[2].
TRACE_LOG = Path(__file__).resolve().parents[2] / "logs" / "trace.log"
_WRITE_LOCK = threading.Lock()


def utc_now() -> str:
    """ISO-8601 timestamp with milliseconds in UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ToolTiming(BaseCallbackHandler):
    """Record when each tool starts and when it returns."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.ended: list[str] = []

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.started.append(utc_now())

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.ended.append(utc_now())


def trace_messages(
    messages: list[Any],
    *,
    clock: Any = None,
    timing: ToolTiming | None = None,
) -> list[dict[str, Any]]:
    """Return one event per tool call and one event per tool result.

    The final model reply is the HTTP answer, so it is not copied into the trace.
    ``timing`` supplies the tool start and end times captured during the run.
    """
    stamp = clock or utc_now
    call_times = list(timing.started) if timing is not None else []
    result_times = list(timing.ended) if timing is not None else []
    call_index = 0
    result_index = 0
    events: list[dict[str, Any]] = []
    for message in messages:
        calls = _tool_calls(message)
        for call in calls:
            events.append(
                {
                    "type": "tool_call",
                    "timestamp": _take(call_times, call_index, stamp),
                    "name": call.get("name"),
                    "args": call.get("args") or {},
                    "content": None,
                }
            )
            call_index += 1
        if calls:
            continue
        if _is_tool_result(message):
            events.append(
                {
                    "type": "tool_result",
                    "timestamp": _take(result_times, result_index, stamp),
                    "name": _name(message),
                    "args": None,
                    "content": _content(message),
                }
            )
            result_index += 1
    return events


def log_trace(
    question: str,
    events: list[dict[str, Any]],
    *,
    answer: str = "",
    path: Path | None = None,
) -> None:
    """Append the question, each tool round-trip, and the answer to the trace log."""
    recorded_at = utc_now()
    lines = [f"\n=== {recorded_at} {question}\n"]
    logger.info("%s question: %s", recorded_at, question)
    for event in events:
        if event["type"] == "tool_call":
            line = f"{event.get('timestamp')} CALL {event.get('name')} {json.dumps(event.get('args'), default=str)}\n"
            logger.info("%s call %s %s", event.get("timestamp"), event.get("name"), json.dumps(event.get("args"), default=str))
        else:
            line = f"{event.get('timestamp')} RESPONSE {event.get('name')} {event.get('content')}\n"
            logger.info("%s response %s %s", event.get("timestamp"), event.get("name"), event.get("content"))
        lines.append(line)
    if answer:
        lines.append(f"ANSWER {answer}\n")
    _append("".join(lines), path)


def log_rejected(detail: str, *, body: Any = None, path: Path | None = None) -> None:
    """Append a request that never reached the agent, such as invalid JSON."""
    rendered = body if isinstance(body, str) else json.dumps(body, default=str)
    logger.info("%s rejected: %s", utc_now(), detail)
    _append(f"\n=== {utc_now()} rejected\nERROR {detail}\nBODY {rendered}\n", path)


def _append(text: str, path: Path | None) -> None:
    destination = path or TRACE_LOG
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()


def _take(times: list[str], index: int, clock: Any) -> str:
    if index < len(times):
        return times[index]
    return clock()


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None)
    if calls is None and isinstance(message, dict):
        calls = message.get("tool_calls")
    if not calls:
        return []
    normalized: list[dict[str, Any]] = []
    for call in calls:
        if isinstance(call, dict):
            normalized.append(call)
        else:
            normalized.append(
                {
                    "name": getattr(call, "name", None),
                    "args": getattr(call, "args", None) or {},
                }
            )
    return normalized


def _is_tool_result(message: Any) -> bool:
    kind = getattr(message, "type", None)
    if kind == "tool":
        return True
    if isinstance(message, dict) and message.get("role") == "tool":
        return True
    return False


def _name(message: Any) -> str | None:
    name = getattr(message, "name", None)
    if name is None and isinstance(message, dict):
        name = message.get("name")
    return str(name) if name else None


def _content(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
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
        if parts:
            return "\n".join(parts)
    return json.dumps(content, default=str)
