"""Grade golden cases: retrieved evidence, tool choice, and answer fidelity."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

CASES_PATH = Path(__file__).with_name("golden_cases.csv")
RULES_PATH = Path(__file__).with_name("prompt_rules.txt")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_PMID = re.compile(r"\b\d{5,9}\b")
_INCOMPLETE = ("incomplete", "not all", "only the first", "of them")
_NUMBER_TOLERANCE = 0.01


def write_report(results: list[dict[str, Any]], *, prompt_ok: bool, path: Path | None = None) -> Path:
    """Write ``n_passed / n_total`` and one row per golden case."""
    from genomic_evidence_agent.config import repo_root

    destination = path or (repo_root() / "outputs" / "evals" / "report.md")
    destination.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for row in results if row["passed"])
    total = len(results)
    lines = [
        "# Golden eval",
        "",
        f"{passed} / {total} passed",
        "",
        "| Case | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for row in results:
        detail = "; ".join(row["errors"]).replace("|", "/")
        status = "pass" if row["passed"] else "fail"
        lines.append(f"| {row['id']} | {status} | {detail} |")
    lines.extend(["", f"Prompt rules: {'pass' if prompt_ok else 'fail'}", ""])
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def load_golden() -> dict[str, Any]:
    """Load the golden sheet.

    One row per case. Lists inside a cell are separated by ``;``. A call is
    ``tool key=value``. Evidence for that call starts with its index:
    ``0 n_matches=1 gene=ABCA4 Name="a name with spaces"``. ``all.gene`` applies
    to every returned row, and ``close.y_proba`` allows a small numeric gap.
    """
    rules = [line.strip() for line in RULES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    with CASES_PATH.open(encoding="utf-8", newline="") as handle:
        cases = [_case_from_row(row) for row in csv.DictReader(handle)]
    return {"prompt_must_include": rules, "cases": cases}


def _case_from_row(row: dict[str, str]) -> dict[str, Any]:
    calls = [_call(part) for part in _split_semi(row["calls"])]
    tools: dict[str, Any] = {"required": _split_semi(row["required_tools"])}
    if row["required_args"].strip():
        tools["required_args"] = [_required_args(part) for part in _split_semi(row["required_args"])]
    case: dict[str, Any] = {
        "id": row["id"].strip(),
        "question": row["question"].strip(),
        "tools": tools,
        "calls": calls,
        "evidence": [_evidence(part) for part in _split_semi(row["evidence"])],
        "answer": _answer(row),
        "reference_answer": row["reference_answer"].strip(),
        "unfaithful_answer": row["unfaithful_answer"].strip(),
    }
    return case


def _answer(row: dict[str, str]) -> dict[str, Any]:
    answer: dict[str, Any] = {}
    cites: dict[int, dict[str, list[str]]] = {}
    for part in _split_semi(row["cite_fields"]):
        call, fields = _cite(part)
        cites.setdefault(call, {})["record_fields"] = fields
    for part in _split_semi(row["cite_numbers"]):
        call, fields = _cite(part)
        cites.setdefault(call, {})["numbers"] = fields
    if cites:
        answer["cite"] = [{"call": call, **fields} for call, fields in sorted(cites.items())]
    mentions = _split_semi(row["must_mention"])
    if mentions:
        answer["must_mention"] = mentions
    forbidden = _split_semi(row["must_not_mention"])
    if forbidden:
        answer["must_not_mention"] = forbidden
    empty = [_empty_call(part) for part in _split_semi(row["empty_calls"])]
    if empty:
        answer["empty_calls"] = empty
    if row["say_incomplete"].strip().lower() in {"yes", "true", "1"}:
        answer["say_incomplete"] = True
    if row["forbid_pmid"].strip().lower() in {"yes", "true", "1"}:
        answer["forbid_pmid"] = True
    if row["format_call"].strip():
        answer["format_call"] = int(row["format_call"])
    return answer


def _call(text: str) -> dict[str, Any]:
    tool, args = _tool_and_args(text)
    return {"tool": tool, "args": args}


def _required_args(text: str) -> dict[str, Any]:
    tool, args = _tool_and_args(text)
    return {"tool": tool, "match": args}


def _tool_and_args(text: str) -> tuple[str, dict[str, Any]]:
    tokens = _tokens(text)
    args = {}
    for token in tokens[1:]:
        key, value = token.split("=", 1)
        args[key] = _typed(value)
    return tokens[0], args


def _evidence(text: str) -> dict[str, Any]:
    tokens = _tokens(text)
    spec: dict[str, Any] = {"call": int(tokens[0])}
    record: dict[str, Any] = {}
    all_records: dict[str, Any] = {}
    close_numbers: dict[str, float] = {}
    for token in tokens[1:]:
        key, raw = token.split("=", 1)
        value = _typed(raw)
        if key.startswith("all."):
            all_records[key.removeprefix("all.")] = value
        elif key.startswith("close."):
            close_numbers[key.removeprefix("close.")] = float(value)
        elif key in {"n_matches", "min_n_matches", "returned", "n_results"}:
            spec[key] = value
        else:
            record[key] = value
    if record:
        spec["record"] = record
    if all_records:
        spec["all_records"] = all_records
    if close_numbers:
        spec["close_numbers"] = close_numbers
    return spec


def _cite(text: str) -> tuple[int, list[str]]:
    call, fields = text.split(":", 1)
    return int(call), fields.split()


def _empty_call(text: str) -> dict[str, Any]:
    call, phrases = text.split("=", 1)
    return {"call": int(call), "phrases": [phrase.strip() for phrase in phrases.split("|") if phrase.strip()]}


def _split_semi(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
            current.append(char)
        elif char == ";" and not quoted:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
            continue
        if char.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)
    if quoted:
        raise ValueError(f"Unclosed quote in {text!r}")
    if current:
        tokens.append("".join(current))
    return tokens


def _typed(raw: str) -> Any:
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def grade_evidence(outputs: list[dict[str, Any]], case: dict[str, Any]) -> list[str]:
    """Check tool payloads against the evidence fields the case requires."""
    errors: list[str] = []
    for spec in case.get("evidence") or []:
        payload = outputs[spec["call"]]
        if "n_matches" in spec and payload.get("n_matches") != spec["n_matches"]:
            errors.append(f"{case['id']} call {spec['call']}: n_matches {payload.get('n_matches')} != {spec['n_matches']}")
        if "min_n_matches" in spec and int(payload.get("n_matches") or 0) < spec["min_n_matches"]:
            errors.append(f"{case['id']} call {spec['call']}: n_matches {payload.get('n_matches')} < {spec['min_n_matches']}")
        if "returned" in spec and payload.get("returned") != spec["returned"]:
            errors.append(f"{case['id']} call {spec['call']}: returned {payload.get('returned')} != {spec['returned']}")
        if "n_results" in spec and payload.get("n_results") != spec["n_results"]:
            errors.append(f"{case['id']} call {spec['call']}: n_results {payload.get('n_results')} != {spec['n_results']}")
        record = (payload.get("records") or [None])[0] or {}
        for field, expected in (spec.get("record") or {}).items():
            if record.get(field) != expected:
                errors.append(f"{case['id']} call {spec['call']}: {field} {record.get(field)!r} != {expected!r}")
        for field, expected in (spec.get("all_records") or {}).items():
            rows = payload.get("records") or []
            if not rows or any(row.get(field) != expected for row in rows):
                errors.append(f"{case['id']} call {spec['call']}: a row does not have {field}={expected!r}")
        for field, expected in (spec.get("close_numbers") or {}).items():
            actual = record.get(field)
            if actual is None or abs(float(actual) - float(expected)) > _NUMBER_TOLERANCE:
                errors.append(f"{case['id']} call {spec['call']}: {field} {actual} is not near {expected}")
    return errors


def grade_tools(calls: list[dict[str, Any]], case: dict[str, Any]) -> list[str]:
    """Check that the required tools were called and the required arguments appeared."""
    errors: list[str] = []
    rules = case.get("tools") or {}
    names = [call.get("tool") or call.get("name") for call in calls]
    for required in rules.get("required") or []:
        if required not in names:
            errors.append(f"{case['id']}: missing tool {required}")
    for forbidden in rules.get("forbidden") or []:
        if forbidden in names:
            errors.append(f"{case['id']}: unexpected tool {forbidden}")
    for spec in rules.get("required_args") or []:
        if not any(_args_match(call, spec) for call in calls):
            errors.append(f"{case['id']}: no {spec['tool']} call matched {spec['match']}")
    return errors


def grade_answer(answer: str, outputs: list[dict[str, Any]], case: dict[str, Any]) -> list[str]:
    """Check that the answer reports the retrieved evidence and does not invent the rest."""
    errors: list[str] = []
    rules = case.get("answer") or {}
    text = answer.lower()
    for phrase in rules.get("must_mention") or []:
        if phrase.lower() not in text:
            errors.append(f"{case['id']}: answer omits {phrase!r}")
    for phrase in rules.get("must_not_mention") or []:
        if phrase.lower() in text:
            errors.append(f"{case['id']}: answer includes {phrase!r}")
    for cite in rules.get("cite") or []:
        payload = outputs[cite["call"]]
        record = (payload.get("records") or [{}])[0]
        for field in cite.get("record_fields") or []:
            value = record.get(field)
            if value is None or str(value).lower() not in text:
                errors.append(f"{case['id']}: answer omits {field} {value!r}")
        for field in cite.get("numbers") or []:
            value = record.get(field)
            if value is None or not _mentions_number(answer, float(value)):
                errors.append(f"{case['id']}: answer omits {field} near {value}")
    for empty in rules.get("empty_calls") or []:
        payload = outputs[empty["call"]]
        count = payload.get("n_matches", payload.get("n_results"))
        if count != 0:
            errors.append(f"{case['id']}: call {empty['call']} was not empty")
            continue
        if not any(phrase.lower() in text for phrase in empty.get("phrases") or []):
            errors.append(f"{case['id']}: answer does not say call {empty['call']} was empty")
    if rules.get("say_incomplete") and not _says_incomplete(answer, outputs):
        errors.append(f"{case['id']}: answer does not say the page is incomplete")
    if rules.get("forbid_pmid"):
        invented = _pmid_tokens(answer) - _known_pmids(outputs)
        if invented:
            errors.append(f"{case['id']}: answer cites PMID {sorted(invented)} not in the evidence")
    return errors


def render_answer(template: str, outputs: list[dict[str, Any]], case: dict[str, Any]) -> str:
    """Fill {n_matches} and {returned} from the call the answer criteria name."""
    call = (case.get("answer") or {}).get("format_call", 0)
    payload = outputs[call] if outputs else {}
    return template.format(
        n_matches=payload.get("n_matches", ""),
        returned=payload.get("returned", ""),
    )


def _args_match(call: dict[str, Any], spec: dict[str, Any]) -> bool:
    if (call.get("tool") or call.get("name")) != spec["tool"]:
        return False
    args = call.get("args") or {}
    for key, expected in spec["match"].items():
        if key not in args:
            return False
        actual = args[key]
        if isinstance(expected, str) and isinstance(actual, str):
            if actual.casefold() != expected.casefold():
                return False
        elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if float(actual) != float(expected):
                return False
        elif actual != expected:
            return False
    return True


def _mentions_number(text: str, value: float) -> bool:
    return any(abs(float(match.group()) - value) <= _NUMBER_TOLERANCE for match in _NUMBER.finditer(text))


def _says_incomplete(answer: str, outputs: list[dict[str, Any]]) -> bool:
    text = answer.lower()
    paged = [payload for payload in outputs if int(payload.get("n_matches") or 0) > int(payload.get("returned") or 0)]
    if not paged:
        return True
    if not any(phrase in text for phrase in _INCOMPLETE):
        return False
    return any(str(payload["n_matches"]) in answer for payload in paged)


def _pmid_tokens(answer: str) -> set[str]:
    return set(_PMID.findall(answer))


def _known_pmids(outputs: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for payload in outputs:
        for article in payload.get("articles") or []:
            pmid = article.get("pmid")
            if pmid:
                found.add(str(pmid))
    return found
