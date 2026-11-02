import pandas as pd

from genomic_evidence_agent.tools.classifier import _jsonable


def test_jsonable_nulls():
    """``_jsonable`` maps NA and NaN to None and leaves ints alone."""
    assert _jsonable(pd.NA) is None
    assert _jsonable(float("nan")) is None
    assert _jsonable(1) == 1
