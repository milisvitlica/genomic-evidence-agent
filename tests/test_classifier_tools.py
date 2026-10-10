import json

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
    payload = catalog.query_joined_dataset(variation_id=7884)
    assert payload["table"] == "clinvar_uniprot_joined.parquet"
    assert payload["n_matches"] >= 1
    record = payload["records"][0]
    assert record["VariationID"] == 7884
    assert record["gene"] == "ABCA4"
    assert record["label"] == "benign"
    assert record["Entry"] == "P78363"


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
