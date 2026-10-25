import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")


@pytest.fixture(scope="module")
def catalog():
    from genomic_evidence_agent.config import get_settings
    from genomic_evidence_agent.tools.classifier import ClassifierCatalog

    settings = get_settings()
    joined = settings.joined_dataset
    scored = settings.scored_vus
    if not joined.is_file():
        pytest.skip(f"joined dataset not found at {joined}")
    return ClassifierCatalog(joined, scored)
