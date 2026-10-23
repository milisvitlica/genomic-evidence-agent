"""Golden questions graded for evidence, tool choice, and answer fidelity.

Retrieval uses the classifier tables and a mocked PubMed response. It does not
call the model.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from genomic_evidence_agent.agent.prompts import SYSTEM_PROMPT
from genomic_evidence_agent.tools.pubmed import search_pubmed
from grading import grade_answer, grade_evidence, grade_tools, load_golden, render_answer, write_report

GOLDEN = load_golden()
CASES = GOLDEN["cases"]


def test_golden_report(request):
    prompt_missing = [rule for rule in GOLDEN["prompt_must_include"] if rule not in SYSTEM_PROMPT]
    results = []
    for case in CASES:
        errors: list[str] = []
        outputs = _execute(case, request)
        errors.extend(grade_evidence(outputs, case))
        errors.extend(grade_tools(case["calls"], case))
        reference = render_answer(case["reference_answer"], outputs, case)
        errors.extend(grade_answer(reference, outputs, case))
        if grade_answer(case["unfaithful_answer"], outputs, case) == []:
            errors.append(f"{case['id']}: unfaithful answer was accepted")
        results.append({"id": case["id"], "passed": not errors, "errors": errors})
    path = write_report(results, prompt_ok=not prompt_missing)
    failed = [row["id"] for row in results if not row["passed"]]
    assert failed == [] and prompt_missing == [], path.read_text(encoding="utf-8")


def test_prompt_still_states_the_rules_the_cases_rely_on():
    missing = [rule for rule in GOLDEN["prompt_must_include"] if rule not in SYSTEM_PROMPT]
    assert missing == []


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_scripted_calls_satisfy_the_tool_rules(case):
    assert grade_tools(case["calls"], case) == []


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_golden_retrieval_and_answer_checks(case, request):
    outputs = _execute(case, request)
    assert grade_evidence(outputs, case) == []
    reference = render_answer(case["reference_answer"], outputs, case)
    assert grade_answer(reference, outputs, case) == [], reference
    assert grade_answer(case["unfaithful_answer"], outputs, case) != []


def test_a_short_brca2_page_does_not_count_as_the_full_tool_plan():
    case = _case("brca2-pathogenic-page")
    short = [{"tool": "query_joined_dataset", "args": {"gene": "BRCA2", "label": "pathogenic", "limit": 10}}]
    assert grade_tools(short, case) != []


def _case(case_id: str) -> dict[str, Any]:
    return next(case for case in CASES if case["id"] == case_id)


def _execute(case: dict[str, Any], request: pytest.FixtureRequest) -> list[dict[str, Any]]:
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
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"esearchresult": {"idlist": []}})

    return httpx.Client(transport=httpx.MockTransport(handler))
