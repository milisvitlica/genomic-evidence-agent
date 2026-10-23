import json
from pathlib import Path

import pandas as pd
import pytest

from genomic_evidence_agent.config import default_classifier_root
from genomic_evidence_agent.tools.classifier import (
    ClassifierCatalog,
    _jsonable,
    build_classifier_tools,
)


def test_jsonable_nulls():
    assert _jsonable(pd.NA) is None
    assert _jsonable(float("nan")) is None
    assert _jsonable(1) == 1


@pytest.fixture(scope="module")
def catalog() -> ClassifierCatalog:
    root = default_classifier_root()
    table = root / "data" / "processed" / "clinvar_uniprot_joined.parquet"
    if not table.is_file():
        pytest.skip(f"classifier table not found at {table}")
    return ClassifierCatalog(root)


def test_joined_lookup_by_id(catalog: ClassifierCatalog):
    expected = json.loads(
        (Path(__file__).parent / "fixtures" / "variant_lookup_expected.json").read_text(encoding="utf-8")
    )
    payload = catalog.query_joined_dataset(variation_id=expected["variation_id"])
    assert payload["table"] == expected["table"]
    assert payload["n_matches"] >= 1
    record = payload["records"][0]
    assert record["VariationID"] == expected["variation_id"]
    assert record["gene"] == expected["gene"]
    assert record["Name"] == expected["name"]
    assert record["label"] == expected["label"]
    assert record["Entry"] == expected["entry"]


def test_joined_gene_filter_is_capped(catalog: ClassifierCatalog):
    payload = catalog.query_joined_dataset(gene="BRCA2", label="pathogenic", limit=3)
    assert payload["n_matches"] > 3
    assert payload["returned"] == 3
    assert all(row["gene"] == "BRCA2" for row in payload["records"])
    assert all(row["label"] == "pathogenic" for row in payload["records"])


def test_joined_query_requires_a_filter(catalog: ClassifierCatalog):
    assert "error" in catalog.query_joined_dataset()


def test_scored_vus_lookup(catalog: ClassifierCatalog):
    payload = catalog.query_scored_vus(variation_id=292)
    assert payload["table"] == "vus_inference_predictions.parquet"
    record = payload["records"][0]
    assert record["VariationID"] == 292
    assert record["pred_label"] in {"pathogenic", "benign"}
    assert record["y_proba"] is not None

    missing = catalog.query_scored_vus(variation_id=7884)
    assert missing["n_matches"] == 0


def test_dataset_tools_are_the_two_queries(catalog: ClassifierCatalog):
    tools = {item.name: item for item in build_classifier_tools(catalog)}
    assert set(tools) == {"query_joined_dataset", "query_scored_vus"}
    payload = json.loads(tools["query_joined_dataset"].invoke({"variation_id": 7884}))
    assert payload["records"][0]["gene"] == "ABCA4"
