"""Representative questions checked against expected evidence fields.

These read the classifier tables. They skip when the sibling checkout is absent.
"""

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_variant_7884_matches_expected_record(catalog):
    expected = json.loads((FIXTURES / "variant_lookup_expected.json").read_text(encoding="utf-8"))
    payload = catalog.query_joined_dataset(variation_id=expected["variation_id"])
    assert payload["table"] == expected["table"]
    assert payload["n_matches"] >= 1
    record = payload["records"][0]
    assert record["VariationID"] == expected["variation_id"]
    assert record["gene"] == expected["gene"]
    assert record["Name"] == expected["name"]
    assert record["label"] == expected["label"]
    assert record["Entry"] == expected["entry"]


def test_brca2_pathogenic_page_is_capped(catalog):
    payload = catalog.query_joined_dataset(gene="BRCA2", label="pathogenic", limit=3)
    assert payload["n_matches"] > 3
    assert payload["returned"] == 3
    assert all(row["gene"] == "BRCA2" for row in payload["records"])
    assert all(row["label"] == "pathogenic" for row in payload["records"])


def test_scored_vus_292_has_a_stored_prediction(catalog):
    payload = catalog.query_scored_vus(variation_id=292)
    assert payload["table"] == "vus_inference_predictions.parquet"
    record = payload["records"][0]
    assert record["VariationID"] == 292
    assert record["pred_label"] in {"pathogenic", "benign"}
    assert record["y_proba"] is not None


def test_labeled_variant_7884_is_absent_from_scored_vus(catalog):
    missing = catalog.query_scored_vus(variation_id=7884)
    assert missing["n_matches"] == 0
