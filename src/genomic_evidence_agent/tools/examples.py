"""Save the current conversation as an example markdown file.

The question, the tool evidence, and the final answer are taken from the chat.
The page writes the file under docs/examples/saved_examples, which Git ignores.
An existing file is left unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from genomic_evidence_agent.config import repo_root

SAVE_TOOL = "save_example"
PAGE_LIMITATIONS = (
    "Saved from the page. Review missing evidence, ambiguous matches, "
    "and prediction caveats before using this as a published example."
)
RECORD_FIELDS = (
    "VariationID",
    "Name",
    "gene",
    "ClinicalSignificance",
    "label",
    "ReviewStatus",
    "NumberSubmitters",
    "Entry",
    "Entry Name",
    "match_type",
    "pred_label",
    "y_proba",
    "threshold",
    "y_pred",
)
ARTICLE_FIELDS = ("pmid", "title", "journal", "pubdate", "doi", "authors")


def saved_examples_dir() -> Path:
    """Folder for chats saved from the page. Git ignores it."""
    return repo_root() / "docs" / "examples" / "saved_examples"


def save_conversation(messages: list[Any], directory: Path | None = None) -> str:
    """Write the chat to a new example file. The caller, not the agent, decides to save."""
    destination = directory or saved_examples_dir()
    turns = conversation_turns(messages)
    if not turns:
        raise ValueError("There is no answered question in this chat yet.")
    question = turns[0]["question"] or "conversation"
    title = question if len(question) <= 80 else question[:77].rstrip() + "…"
    path = available_example_path(destination, question)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_example(title, PAGE_LIMITATIONS, turns), encoding="utf-8")
    if _is_inside(path, repo_root()):
        return f"Saved {path.relative_to(repo_root())}"
    return f"Saved {path}"


def available_example_path(directory: Path, filename: str) -> Path:
    """Pick a free filename inside directory, adding -2, -3, … when needed."""
    path = example_path(directory, filename)
    if not path.exists():
        return path
    for number in range(2, 100):
        candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
        if _is_inside(candidate, directory.resolve()) and not candidate.exists():
            return candidate
    raise ValueError(f"{path.name} already exists. Choose another filename.")


def write_example(
    directory: Path,
    *,
    title: str,
    filename: str,
    limitations: str,
    messages: list[Any],
) -> str:
    """Write one example file. Raise ValueError when the chat or the name is unusable."""
    heading = title.strip()
    caveat = limitations.strip()
    if not heading:
        raise ValueError("Provide a title for the example.")
    if not caveat:
        raise ValueError("Provide limitations for the example.")
    turns = conversation_turns(messages)
    if not turns:
        raise ValueError("There is no answered question in this chat yet.")
    path = example_path(directory, filename)
    if path.exists():
        raise ValueError(f"{path.name} already exists. Choose another filename.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_example(heading, caveat, turns), encoding="utf-8")
    return f"Saved {path.relative_to(repo_root())}" if _is_inside(path, repo_root()) else f"Saved {path}"


def example_path(directory: Path, filename: str) -> Path:
    """Return a path inside directory. The name cannot escape that directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:48].strip("-")
    if slug.startswith("saved-"):
        slug = slug[len("saved-") :]
    if not slug:
        raise ValueError("Provide a short filename, such as variation-7884.")
    path = (directory / f"saved-{slug}.md").resolve()
    if not _is_inside(path, directory.resolve()):
        raise ValueError("The filename must stay inside the examples directory.")
    return path


def conversation_turns(messages: list[Any]) -> list[dict[str, Any]]:
    """Group the chat into question, tool evidence, and final answer."""
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending: list[dict[str, Any]] = []
    for message in messages:
        role = _role(message)
        if role == "user":
            if current is not None:
                turns.append(current)
            current = {"question": _text(message).strip(), "calls": [], "answer": ""}
            continue
        if current is None:
            continue
        if role == "assistant":
            calls = [call for call in _tool_calls(message) if call.get("name") != SAVE_TOOL]
            for call in calls:
                item = {"name": call.get("name") or "tool", "args": call.get("args") or {}, "content": None}
                current["calls"].append(item)
                pending.append(item)
            text = _text(message).strip()
            if text and not calls:
                current["answer"] = text
            continue
        if role == "tool" and _name(message) != SAVE_TOOL:
            content = _text(message)
            if pending:
                pending.pop(0)["content"] = content
            else:
                current["calls"].append({"name": _name(message) or "tool", "args": {}, "content": content})
    if current is not None:
        turns.append(current)
    return [turn for turn in turns if turn["answer"] or turn["calls"]]


def render_example(title: str, limitations: str, turns: list[dict[str, Any]]) -> str:
    """Render the question, evidence, answer, and limitations sections."""
    parts = [f"# {title}", ""]
    several = len(turns) > 1
    for index, turn in enumerate(turns, start=1):
        if several:
            parts.extend([f"## Turn {index}", ""])
        parts.extend(
            [
                f"**Question:** {turn['question']}",
                "",
                "**Evidence returned:**",
                "",
                _evidence(turn["calls"]),
                "",
                "**Final answer:**",
                "",
                turn["answer"] or "The conversation has no final answer for this question yet.",
                "",
            ]
        )
    parts.extend(["**Limitations:**", "", limitations, ""])
    return "\n".join(parts)


def _evidence(calls: list[dict[str, Any]]) -> str:
    if not calls:
        return "No tool call was returned."
    blocks: list[str] = []
    for call in calls:
        blocks.append(f"Tool `{call['name']}` with `{json.dumps(call['args'], ensure_ascii=False, default=str)}`")
        blocks.append("")
        blocks.append(_payload(call.get("content")))
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _payload(content: str | None) -> str:
    if not content:
        return "No tool result was returned."
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return f"```\n{content}\n```"
    if not isinstance(data, dict):
        return f"```json\n{json.dumps(data, indent=2, ensure_ascii=False, default=str)}\n```"
    lines: list[str] = []
    if data.get("error"):
        lines.append(str(data["error"]))
    if "n_matches" in data:
        lines.append(
            f"{data.get('table', 'table')}: n_matches {data.get('n_matches')}, returned {data.get('returned')}."
        )
    if "n_results" in data:
        lines.append(f"PubMed query `{data.get('query')}`: n_results {data.get('n_results')}.")
    for record in data.get("records") or []:
        if isinstance(record, dict):
            selected = {key: record.get(key) for key in RECORD_FIELDS if record.get(key) is not None}
            lines.append(f"```json\n{json.dumps(selected, indent=2, ensure_ascii=False, default=str)}\n```")
    for article in data.get("articles") or []:
        if isinstance(article, dict):
            selected = {key: article.get(key) for key in ARTICLE_FIELDS if article.get(key) is not None}
            lines.append(f"```json\n{json.dumps(selected, indent=2, ensure_ascii=False, default=str)}\n```")
    if not lines:
        lines.append(f"```json\n{json.dumps(data, indent=2, ensure_ascii=False, default=str)}\n```")
    return "\n\n".join(lines)


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _role(message: Any) -> str:
    kind = getattr(message, "type", None)
    if kind in {"human", "user"}:
        return "user"
    if kind in {"ai", "assistant"}:
        return "assistant"
    if kind == "tool":
        return "tool"
    if isinstance(message, dict):
        role = message.get("role") or message.get("type")
        if role in {"human", "user"}:
            return "user"
        if role in {"ai", "assistant"}:
            return "assistant"
        if role == "tool":
            return "tool"
    return ""


def _text(message: Any) -> str:
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
        return "\n".join(parts)
    return "" if content is None else str(content)


def _name(message: Any) -> str | None:
    name = getattr(message, "name", None)
    if name is None and isinstance(message, dict):
        name = message.get("name")
    return str(name) if name else None


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None)
    if calls is None and isinstance(message, dict):
        calls = message.get("tool_calls")
    normalized: list[dict[str, Any]] = []
    for call in calls or []:
        if isinstance(call, dict):
            normalized.append(call)
        else:
            normalized.append({"name": getattr(call, "name", None), "args": getattr(call, "args", None) or {}})
    return normalized
