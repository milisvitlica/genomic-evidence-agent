import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from genomic_evidence_agent.tools.examples import (
    conversation_turns,
    example_path,
    save_conversation,
    write_example,
)


def _chat():
    evidence = {
        "table": "clinvar_uniprot_joined.parquet",
        "n_matches": 1,
        "returned": 1,
        "records": [
            {
                "VariationID": 7884,
                "gene": "ABCA4",
                "Name": "NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)",
                "label": "benign",
                "ClinicalSignificance": "Likely benign",
                "PhenotypeList": "x" * 800,
            }
        ],
    }
    return [
        HumanMessage(content="What does the joined table say about VariationID 7884?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "query_joined_dataset",
                    "args": {"variation_id": 7884},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content=json.dumps(evidence), name="query_joined_dataset", tool_call_id="call-1"),
        AIMessage(content="VariationID 7884 is ABCA4, labeled benign."),
        HumanMessage(content="Save this chat as an example."),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "save_example",
                    "args": {"title": "Variation 7884", "filename": "variation-7884", "limitations": "placeholder"},
                    "id": "call-2",
                    "type": "tool_call",
                }
            ],
        ),
    ]


def test_conversation_turns_skip_the_save_request():
    turns = conversation_turns(_chat())
    assert len(turns) == 1
    assert turns[0]["question"].startswith("What does the joined table say")
    assert turns[0]["calls"][0]["name"] == "query_joined_dataset"
    assert "PhenotypeList" in turns[0]["calls"][0]["content"]
    assert turns[0]["answer"] == "VariationID 7884 is ABCA4, labeled benign."


def test_write_example_keeps_selected_fields_and_limitations(tmp_path):
    path_message = write_example(
        tmp_path,
        title="Variation 7884",
        filename="variation-7884",
        limitations="ClinicalSignificance is Likely benign. The collapsed label is benign.",
        messages=_chat(),
    )
    written = tmp_path / "saved-variation-7884.md"
    assert written.name in path_message
    text = written.read_text(encoding="utf-8")
    assert text.startswith("# Variation 7884")
    assert "**Question:** What does the joined table say about VariationID 7884?" in text
    assert '"VariationID": 7884' in text
    assert "PhenotypeList" not in text
    assert "**Final answer:**" in text
    assert "VariationID 7884 is ABCA4, labeled benign." in text
    assert "**Limitations:**" in text
    assert "Likely benign" in text


def test_write_example_does_not_replace_an_existing_file(tmp_path):
    kwargs = {
        "title": "Variation 7884",
        "filename": "variation-7884",
        "limitations": "One caveat.",
        "messages": _chat(),
    }
    write_example(tmp_path, **kwargs)
    with pytest.raises(ValueError, match="already exists"):
        write_example(tmp_path, **kwargs)


def test_example_path_stays_inside_the_directory(tmp_path):
    path = example_path(tmp_path, "../../etc/passwd")
    assert path.parent == tmp_path.resolve()
    assert path.name == "saved-etc-passwd.md"
    with pytest.raises(ValueError, match="short filename"):
        example_path(tmp_path, "...")


def test_save_conversation_writes_without_asking_the_model(tmp_path):
    first = save_conversation(_chat(), tmp_path)
    second = save_conversation(_chat(), tmp_path)
    assert "saved-what-does-the-joined-table-say-about" in first
    assert first != second
    text = next(tmp_path.glob("saved-what-does-the-joined-table-say-about-variationid*.md")).read_text(encoding="utf-8")
    assert "**Question:** What does the joined table say about VariationID 7884?" in text
    assert "Saved from the page." in text
    assert "save_example" not in text
