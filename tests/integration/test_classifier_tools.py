import json

from genomic_evidence_agent.tools.classifier import build_classifier_tools


def test_joined_query_requires_a_filter(catalog):
    assert "error" in catalog.query_joined_dataset()


def test_dataset_tools_are_the_two_queries(catalog):
    tools = {item.name: item for item in build_classifier_tools(catalog)}
    assert set(tools) == {"query_joined_dataset", "query_scored_vus"}
    payload = json.loads(tools["query_joined_dataset"].invoke({"variation_id": 7884}))
    assert payload["n_matches"] >= 1
    assert payload["records"][0]["gene"]
