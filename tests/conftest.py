import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")


@pytest.fixture(scope="module")
def catalog():
    from genomic_evidence_agent.config import default_classifier_root
    from genomic_evidence_agent.tools.classifier import ClassifierCatalog

    root = default_classifier_root()
    table = root / "data" / "processed" / "clinvar_uniprot_joined.parquet"
    if not table.is_file():
        pytest.skip(f"classifier table not found at {table}")
    return ClassifierCatalog(root)
