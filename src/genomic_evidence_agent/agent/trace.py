"""Extract tool calls and tool results from a LangGraph message list."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("genomic_evidence_agent.trace")


def trace_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Return one event per tool call and one event per tool result.

    The final model reply is the HTTP answer, so it is not copied into the trace.
    """
    events: list[dict[str, Any]] = []
    for message in messages:
        for call in _tool_calls(message):
            events.append(
                {
                    "type": "tool_call",
                    "name": call.get("name"),
                    "args": call.get("args") or {},
                    "content": None,
                }
            )
        if _tool_calls(message):
            continue
        if _is_tool_result(message):
            events.append(
                {
                    "type": "tool_result",
                    "name": _name(message),
                    "args": None,
                    "content": _content(message),
                }
            )
    return events


def log_trace(question: str, events: list[dict[str, Any]]) -> None:
    """Write the question and each tool round-trip to the process log."""
    logger.info("question: %s", question)
    for event in events:
        if event["type"] == "tool_call":
            logger.info("call %s %s", event.get("name"), json.dumps(event.get("args"), default=str))
        else:
            logger.info("response %s %s", event.get("name"), event.get("content"))


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
