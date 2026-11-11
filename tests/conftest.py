import os

import pytest

# Tests never call the model, so a placeholder key is enough. The live agent eval
# (EVAL_AGENT=1) needs the real key from .env, which config.py loads when it is imported.
if os.environ.get("EVAL_AGENT") != "1":
    os.environ.setdefault("OPENAI_API_KEY", "test-key")


@pytest.fixture(scope="module")
def catalog():
    """Load the classifier tables once per module, or skip the test if the dataset is missing."""
    from genomic_evidence_agent.config import get_settings
    from genomic_evidence_agent.tools.classifier import ClassifierCatalog

    settings = get_settings()
    joined = settings.joined_dataset
    scored = settings.scored_vus
    if not joined.is_file():
        pytest.skip(f"joined dataset not found at {joined}")
    return ClassifierCatalog(joined, scored)
