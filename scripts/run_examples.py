"""Run the fixed example questions and save the raw responses locally.

Start the API first, then from the repository root:

    python scripts/run_examples.py

Each case is written to ``outputs/examples/<id>.json`` and a review draft
``outputs/examples/<id>.md``. Those files stay out of Git. Read them, then copy
the cases you want into ``docs/examples/`` in the question, evidence, answer,
and limitations form. Fill in limitations yourself. This script does not edit
``docs/examples/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "examples"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TEXT_LIMIT = 400


@dataclass(frozen=True)
class Turn:
    question: str
    continue_thread: bool = False


@dataclass(frozen=True)
class Case:
    id: str
    turns: tuple[Turn, ...]


CASES: tuple[Case, ...] = (
    Case("01-variation-7884", (Turn("What does the joined classifier table say about ClinVar VariationID 7884?"),)),
    Case("02-brca2-pathogenic", (Turn("List 3 pathogenic BRCA2 variants from the joined dataset."),)),
    Case(
        "03-abca4-uniprot",
        (Turn("What UniProt entry is joined to NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)?"),),
    ),
    Case("04-vus-292", (Turn("What score does the scored VUS table give VariationID 292?"),)),
    Case("05-brca1-highest-score", (Turn("Which scored VUS for gene BRCA1 has the highest y_proba?"),)),
    Case("06-vus-7884-missing", (Turn("Is ClinVar VariationID 7884 in the scored VUS table?"),)),
    Case("07-pubmed-abca4", (Turn("Find PubMed articles about ABCA4 Val2050Leu."),)),
    Case("08-pubmed-aipl1", (Turn("Find PubMed articles about AIPL1 Leber congenital amaurosis."),)),
    Case(
        "09-label-and-paper",
        (Turn("What is the ClinVar label for VariationID 7884, and find one PubMed paper on ABCA4 Val2050Leu?"),),
    ),
    Case("10-cftr-pathogenic", (Turn("Show a few pathogenic CFTR variants from the joined dataset."),)),
    Case(
        "11-thread-7884",
        (
            Turn("What ClinVar label does VariationID 7884 have? One short sentence."),
            Turn("What variation id did I just ask about? Reply with only the id.", continue_thread=True),
            Turn("What variation id did I just ask about? Reply with only the id."),
        ),
    ),
    Case(
        "12-her2-then-clinvar",
        (
            Turn("What do we know about HER+ cancer type"),
            Turn("Anything in ClinVar on this?", continue_thread=True),
        ),
    ),
)


def shorten(value: Any, limit: int = TEXT_LIMIT) -> Any:
    """Shorten long strings so the review draft stays readable."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip() + "…"
    if isinstance(value, list):
        return [shorten(item, limit) for item in value]
    if isinstance(value, dict):
        return {key: shorten(item, limit) for key, item in value.items()}
    return value


def parse_content(content: str | None) -> Any:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def select_cases(only: str | None) -> list[Case]:
    if not only:
        return list(CASES)
    wanted = {item.strip() for item in only.split(",") if item.strip()}
    selected = [case for case in CASES if case.id in wanted or any(case.id.startswith(item) for item in wanted)]
    unknown = wanted - {case.id for case in selected}
    unknown -= {item for item in wanted if any(case.id.startswith(item) for case in selected)}
    if unknown:
        known = ", ".join(case.id for case in CASES)
        raise SystemExit(f"Unknown example id: {', '.join(sorted(unknown))}. Known ids: {known}")
    return selected


def post_evidence(client: httpx.Client, base_url: str, question: str, thread_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"question": question}
    if thread_id:
        payload["thread_id"] = thread_id
    response = client.post(f"{base_url.rstrip('/')}/evidence", json=payload)
    body: Any
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = response.text
    if response.status_code != 200:
        return {"ok": False, "status_code": response.status_code, "body": body}
    return {"ok": True, "status_code": response.status_code, "body": body}


def run_case(client: httpx.Client, base_url: str, case: Case) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    thread_id: str | None = None
    for turn in case.turns:
        used_thread = thread_id if turn.continue_thread else None
        result = post_evidence(client, base_url, turn.question, used_thread)
        record: dict[str, Any] = {
            "question": turn.question,
            "continue_thread": turn.continue_thread,
            "request_thread_id": used_thread,
            **result,
        }
        turns.append(record)
        if result.get("ok"):
            thread_id = result["body"].get("thread_id")
        elif turn.continue_thread:
            thread_id = None
    return {"id": case.id, "turns": turns}


def evidence_block(trace: list[dict[str, Any]]) -> str:
    calls = [event for event in trace if event.get("type") == "tool_call"]
    results = [event for event in trace if event.get("type") == "tool_result"]
    if not calls and not results:
        return "No tool call was returned."
    lines: list[str] = []
    for index, result in enumerate(results):
        call = calls[index] if index < len(calls) else {}
        name = result.get("name") or call.get("name") or "tool"
        args = call.get("args") or {}
        payload = shorten(parse_content(result.get("content")))
        lines.append(f"Tool `{name}` with `{json.dumps(args, ensure_ascii=False)}`")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        lines.append("```")
        lines.append("")
    if len(calls) > len(results):
        for call in calls[len(results) :]:
            lines.append(
                f"Tool `{call.get('name')}` was called with `{json.dumps(call.get('args') or {}, ensure_ascii=False)}` and returned no result in the trace."
            )
            lines.append("")
    return "\n".join(lines).rstrip()


def render_markdown(case_result: dict[str, Any]) -> str:
    parts = [
        f"# {case_result['id']}",
        "",
        "Local run for review. Copy a sanitized version into `docs/examples/` and write the limitations there. Do not commit this file.",
        "",
    ]
    for number, turn in enumerate(case_result["turns"], start=1):
        if len(case_result["turns"]) > 1:
            relation = "same thread" if turn.get("continue_thread") else "new thread"
            parts.extend([f"## Turn {number} ({relation})", ""])
        parts.extend([f"**Question:** {turn['question']}", ""])
        if not turn.get("ok"):
            parts.extend(
                [
                    "**Evidence returned:** The request failed.",
                    "",
                    "**Final answer:**",
                    "",
                    "```json",
                    json.dumps({"status_code": turn.get("status_code"), "body": turn.get("body")}, indent=2, default=str),
                    "```",
                    "",
                    "**Limitations:**",
                    "",
                    "",
                ]
            )
            continue
        body = turn["body"]
        parts.extend(
            [
                f"**Evidence returned:** thread `{body.get('thread_id')}`.",
                "",
                evidence_block(body.get("trace") or []),
                "",
                "**Final answer:**",
                "",
                str(body.get("answer") or "").rstrip(),
                "",
                "**Limitations:**",
                "",
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def write_case(output_dir: Path, case_result: dict[str, Any]) -> None:
    case_id = case_result["id"]
    (output_dir / f"{case_id}.json").write_text(
        json.dumps(case_result, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    (output_dir / f"{case_id}.md").write_text(render_markdown(case_result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed example questions against a local evidence API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API origin. Default: %(default)s")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for the raw runs. Default: %(default)s")
    parser.add_argument("--only", help="Comma-separated case ids, or unique prefixes such as 07,12.")
    parser.add_argument("--timeout", type=float, default=180, help="Seconds to wait for one /evidence response.")
    args = parser.parse_args(argv)

    cases = select_cases(args.only)
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    timeout = httpx.Timeout(args.timeout, connect=10.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            health = client.get(f"{args.base_url.rstrip('/')}/health")
            health.raise_for_status()
            for case in cases:
                print(f"running {case.id}", flush=True)
                result = run_case(client, args.base_url, case)
                write_case(output_dir, result)
                if any(not turn.get("ok") for turn in result["turns"]):
                    failures += 1
                    print(f"  failed {case.id}", flush=True)
    except httpx.HTTPError as exc:
        print(f"Could not reach {args.base_url}: {exc}", file=sys.stderr)
        print("Start the API, then rerun this script.", file=sys.stderr)
        return 1

    print(f"Wrote {len(cases)} cases to {output_dir}")
    print("Review the markdown drafts, then copy selected cases into docs/examples/.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
