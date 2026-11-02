import json

from genomic_evidence_agent.tools.classifier import build_classifier_tools


def test_joined_query_requires_a_filter(catalog):
    """The joined query returns an error when no filter is given."""
    assert "error" in catalog.query_joined_dataset()


def test_dataset_tools_are_the_two_queries(catalog):
    """The agent gets exactly the two dataset tools, and the joined tool returns JSON for a lookup."""
    tools = {item.name: item for item in build_classifier_tools(catalog)}
    assert set(tools) == {"query_joined_dataset", "query_scored_vus"}
    payload = json.loads(tools["query_joined_dataset"].invoke({"variation_id": 7884}))
    assert payload["n_matches"] >= 1
    assert payload["records"][0]["gene"]
