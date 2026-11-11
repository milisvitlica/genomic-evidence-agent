"""Golden questions graded for evidence, tool choice, and answer fidelity.

Offline tests (no model call): check that the system prompt still states the rules the
cases rely on, run each case's scripted tool calls against the classifier tables and a
mocked PubMed response, and check the grader accepts a good answer and rejects a bad one.

The last test asks the real agent each question once, grades the tools it chose and its
answer, and writes outputs/evals/report.md. It is skipped unless EVAL_AGENT=1.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from genomic_evidence_agent.agent.prompts import SYSTEM_PROMPT
from genomic_evidence_agent.tools.pubmed import search_pubmed
from grading import (
    CASES_PATH,
    grade_answer,
    grade_evidence,
    grade_tools,
    load_golden,
    map_agent_outputs,
    render_answer,
    write_agent_report,
)

_SECRET = re.compile(r"sk-[A-Za-z0-9_\-\*\.]+")

GOLDEN = load_golden()
CASES = GOLDEN["cases"]


def test_prompt_still_states_the_rules_the_cases_rely_on():
    """The system prompt contains every rule the golden cases rely on."""
    missing = [rule for rule in GOLDEN["prompt_must_include"] if rule not in SYSTEM_PROMPT]
    assert missing == []


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_scripted_calls_satisfy_the_tool_rules(case):
    """Each case's scripted tool calls meet its tool requirements."""
    assert grade_tools(case["calls"], case) == []


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_golden_retrieval_and_answer_checks(case, request):
    """Retrieval matches the expected evidence, the reference answer passes, and the unfaithful answer fails."""
    outputs = _execute(case, request)
    assert grade_evidence(outputs, case) == []
    reference = render_answer(case["reference_answer"], outputs, case)
    assert grade_answer(reference, outputs, case) == [], reference
    assert grade_answer(case["unfaithful_answer"], outputs, case) != []


def test_a_short_brca2_page_does_not_count_as_the_full_tool_plan():
    """One page of 10 BRCA2 results must not satisfy the case's required tool plan."""
    case = _case("brca2-pathogenic-page")
    short = [{"tool": "query_joined_dataset", "args": {"gene": "BRCA2", "label": "pathogenic", "limit": 10}}]
    assert grade_tools(short, case) != []


def test_live_agent_matches_golden_cases():
    """Ask the real agent each golden question once and grade the tools it chose and its answer.

    Needs EVAL_AGENT=1 and a real OPENAI_API_KEY in .env. It calls the model and PubMed,
    so the result can vary between runs. EVAL_CASES=id1,id2 limits the cases. The result
    is written to outputs/evals/report.md.
    """
    if os.environ.get("EVAL_AGENT") != "1":
        pytest.skip("Set EVAL_AGENT=1 to ask the real agent the golden questions.")
    if os.environ.get("OPENAI_API_KEY", "") in {"", "test-key"}:
        pytest.skip("OPENAI_API_KEY is not set to a real key.")
    wanted = {name.strip() for name in os.environ.get("EVAL_CASES", "").split(",") if name.strip()}
    cases = [case for case in CASES if not wanted or case["id"] in wanted]
    assert cases, f"EVAL_CASES matched no golden case: {sorted(wanted)}"

    started = datetime.now().astimezone()
    results = asyncio.run(_ask_agent(cases))
    path = write_agent_report(results, meta=_run_details(started, len(cases)))
    passed = sum(1 for row in results if row["passed"])
    print(f"\nagent eval: {passed} / {len(results)} passed -> {path}")
    failed = [row for row in results if not row["passed"]]
    assert not failed, path.read_text(encoding="utf-8")


def _run_details(started: datetime, n_cases: int) -> dict[str, str]:
    """When and what was evaluated, so two reports can be compared."""
    from genomic_evidence_agent.config import get_settings, repo_root

    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:8]

    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=repo_root(), capture_output=True, text=True, timeout=10, check=True
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    commit = git("rev-parse", "--short", "HEAD")
    if commit and git("status", "--porcelain", "--untracked-files=no"):
        commit += " (uncommitted changes)"
    finished = datetime.now().astimezone()
    return {
        "Run started": started.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        "Duration": f"{(finished - started).total_seconds():.0f} s",
        "Model": get_settings().model,
        "Cases": f"{n_cases} of {len(CASES)} (one answer per case)",
        "System prompt hash": digest(SYSTEM_PROMPT.encode("utf-8")),
        "Golden cases hash": digest(CASES_PATH.read_bytes()),
        "Git commit": commit or "not available",
    }


async def _ask_agent(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from genomic_evidence_agent.agent.graph import build_evidence_agent

    agent = await build_evidence_agent()
    try:
        return [await _ask_one(agent, case) for case in cases]
    finally:
        await agent.aclose()


async def _ask_one(agent: Any, case: dict[str, Any]) -> dict[str, Any]:
    from genomic_evidence_agent.api.app import message_text

    try:
        result = await agent.graph.ainvoke(
            {"messages": [{"role": "user", "content": case["question"]}]},
            config={"configurable": {"thread_id": f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"}, "recursion_limit": 24},
        )
    except Exception as exc:  # noqa: BLE001 - a failed run is a failed case
        detail = _SECRET.sub("sk-***", f"{type(exc).__name__}: {exc}")[:300]
        return {"id": case["id"], "passed": False, "errors": [f"{case['id']}: agent failed: {detail}"], "calls": [], "answer": ""}

    messages = result.get("messages") or []
    calls = _tool_calls(messages, message_text)
    answer = message_text(messages[-1].content) if messages else ""
    errors = grade_tools(calls, case)
    outputs, missing = map_agent_outputs(case["calls"], calls, case["id"])
    errors.extend(missing)
    errors.extend(error for error in grade_answer(answer, outputs, case) if error not in errors)
    return {"id": case["id"], "passed": not errors, "errors": errors, "calls": calls, "answer": answer}


def _tool_calls(messages: list[Any], message_text: Any) -> list[dict[str, Any]]:
    """Each tool call the agent made, with the parsed result the tool returned."""
    results: dict[str, str] = {}
    for message in messages:
        if getattr(message, "type", None) == "tool":
            results[getattr(message, "tool_call_id", "")] = message_text(message.content)
    calls: list[dict[str, Any]] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            calls.append(
                {
                    "tool": call.get("name"),
                    "args": call.get("args") or {},
                    "output": _parse(results.get(call.get("id", ""), "")),
                }
            )
    return calls


def _parse(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _case(case_id: str) -> dict[str, Any]:
    """Look up a golden case by id."""
    return next(case for case in CASES if case["id"] == case_id)


def _execute(case: dict[str, Any], request: pytest.FixtureRequest) -> list[dict[str, Any]]:
    """Run a case's scripted calls against the real tables or a mocked PubMed and return the payloads."""
    catalog = None
    if any(call["tool"].startswith("query_") for call in case["calls"]):
        catalog = request.getfixturevalue("catalog")
    outputs: list[dict[str, Any]] = []
    for call in case["calls"]:
        tool = call["tool"]
        args = call["args"]
        if tool == "query_joined_dataset":
            outputs.append(catalog.query_joined_dataset(**args))
        elif tool == "query_scored_vus":
            outputs.append(catalog.query_scored_vus(**args))
        elif tool == "search_pubmed":
            client = _empty_pubmed()
            try:
                outputs.append(search_pubmed(**args, client=client))
            finally:
                client.close()
        else:
            raise AssertionError(f"no executor for {tool}")
    return outputs


def _empty_pubmed() -> httpx.Client:
    """Return an HTTP client whose PubMed search always finds no articles."""
    def handler(request: httpx.Request) -> httpx.Response:
        """Answer every request with an empty PubMed search result."""
        return httpx.Response(200, json={"esearchresult": {"idlist": []}})

    return httpx.Client(transport=httpx.MockTransport(handler))
