"""Two read-only queries over clinvar-pathogenicity-classifier tables.

The classifier project owns ingest, joins, and the CatBoost model. These tools
only filter the processed parquet files.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from langchain_core.tools import tool

JOINED_TABLE = "clinvar_uniprot_joined.parquet"
SCORED_VUS_TABLE = "vus_inference_predictions.parquet"

JOINED_COLUMNS = [
    "VariationID",
    "Name",
    "gene",
    "GeneSymbol",
    "HGNC_ID",
    "ClinicalSignificance",
    "label",
    "ReviewStatus",
    "NumberSubmitters",
    "PhenotypeList",
    "Chromosome",
    "Start",
    "Stop",
    "ReferenceAlleleVCF",
    "AlternateAlleleVCF",
    "Entry",
    "Entry Name",
    "Protein names",
    "Length",
    "match_type",
    "Function [CC]",
    "Involvement in disease",
]

VUS_COLUMNS = [
    "VariationID",
    "gene",
    "Name",
    "ClinicalSignificance",
    "label",
    "y_proba",
    "threshold",
    "y_pred",
    "pred_label",
]

LONG_TEXT = {"Function [CC]", "Involvement in disease", "PhenotypeList", "Protein names"}
TEXT_LIMIT = 400
DEFAULT_LIMIT = 10
MAX_LIMIT = 25


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if math.isnan(number) else number
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value
    return value


def _cell(column: str, value: Any) -> Any:
    parsed = _jsonable(value)
    if column in LONG_TEXT and isinstance(parsed, str) and len(parsed) > TEXT_LIMIT:
        return parsed[: TEXT_LIMIT - 1] + "…"
    if column == "VariationID" and parsed is not None:
        return int(parsed)
    return parsed


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    present = [column for column in columns if column in frame.columns]
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append({column: _cell(column, row[column]) for column in present})
    return rows


def _cap(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


class ClassifierCatalog:
    """Cached reader for the two classifier tables the agent is allowed to query."""

    def __init__(self, joined_dataset: Path, scored_vus: Path):
        self.paths = {
            JOINED_TABLE: Path(joined_dataset),
            SCORED_VUS_TABLE: Path(scored_vus),
        }
        self._frames: dict[str, pd.DataFrame] = {}

    def table_status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {"path": str(path), "exists": path.is_file()}
            for name, path in self.paths.items()
        }

    def _load(self, name: str) -> pd.DataFrame:
        if name not in self._frames:
            path = self.paths[name]
            if not path.is_file():
                raise FileNotFoundError(f"Missing classifier table: {path}")
            self._frames[name] = pd.read_parquet(path)
        return self._frames[name]

    def query_joined_dataset(
        self,
        *,
        gene: str | None = None,
        variation_id: int | None = None,
        variant_name: str | None = None,
        label: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        if not any([gene and gene.strip(), variation_id is not None, variant_name and variant_name.strip(), label and label.strip()]):
            return {"error": "Provide at least one of gene, variation_id, variant_name, or label."}
        wanted = label.strip().lower() if label and label.strip() else None
        if wanted == "vus":
            return {
                "error": "VUS model scores are in the scored VUS dataset. Use query_scored_vus.",
                "table": JOINED_TABLE,
            }
        if wanted not in {None, "pathogenic", "benign"}:
            return {"error": "label must be pathogenic or benign. VUS scores use query_scored_vus."}

        frame = self._filter_identity(self._load(JOINED_TABLE), gene=gene, variation_id=variation_id, variant_name=variant_name)
        if wanted is not None and "label" in frame.columns:
            frame = frame.loc[frame["label"].astype("string").str.lower() == wanted]
        frame = _dedupe_variations(frame)
        return _page(JOINED_TABLE, frame, JOINED_COLUMNS, _cap(limit))

    def query_scored_vus(
        self,
        *,
        gene: str | None = None,
        variation_id: int | None = None,
        variant_name: str | None = None,
        pred_label: str | None = None,
        min_proba: float | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        has_identity = any([
            gene and gene.strip(),
            variation_id is not None,
            variant_name and variant_name.strip(),
        ])
        wanted = pred_label.strip().lower() if pred_label and pred_label.strip() else None
        if wanted not in {None, "pathogenic", "benign"}:
            return {"error": "pred_label must be pathogenic or benign."}
        if not has_identity and wanted is None and min_proba is None:
            return {"error": "Provide gene, variation_id, variant_name, pred_label, or min_proba."}

        frame = self._filter_identity(self._load(SCORED_VUS_TABLE), gene=gene, variation_id=variation_id, variant_name=variant_name)
        if wanted is not None and "pred_label" in frame.columns:
            frame = frame.loc[frame["pred_label"].astype("string").str.lower() == wanted]
        if min_proba is not None and "y_proba" in frame.columns:
            scores = pd.to_numeric(frame["y_proba"], errors="coerce")
            frame = frame.loc[scores >= float(min_proba)]
        if "y_proba" in frame.columns:
            frame = frame.sort_values("y_proba", ascending=False, kind="mergesort")
        frame = frame.drop_duplicates("VariationID") if "VariationID" in frame.columns else frame
        payload = _page(SCORED_VUS_TABLE, frame, VUS_COLUMNS, _cap(limit))
        payload["note"] = (
            "Scores are the stored CatBoost probabilities in vus_inference_predictions.parquet. "
            "pred_label applies the saved Youden threshold. This is computational evidence, "
            "not a clinical classification."
        )
        return payload

    def _filter_identity(
        self,
        frame: pd.DataFrame,
        *,
        gene: str | None,
        variation_id: int | None,
        variant_name: str | None,
    ) -> pd.DataFrame:
        matched = frame
        if variation_id is not None and "VariationID" in matched.columns:
            ids = pd.to_numeric(matched["VariationID"], errors="coerce")
            matched = matched.loc[ids == int(variation_id)]
        if gene and gene.strip() and "gene" in matched.columns:
            matched = matched.loc[matched["gene"].astype("string").str.upper() == gene.strip().upper()]
        if variant_name and variant_name.strip() and "Name" in matched.columns:
            needle = variant_name.strip()
            names = matched["Name"].astype("string")
            exact = matched.loc[names.str.casefold() == needle.casefold()]
            matched = exact if not exact.empty else matched.loc[
                names.str.contains(re.escape(needle), case=False, na=False)
            ]
        return matched


def _dedupe_variations(frame: pd.DataFrame) -> pd.DataFrame:
    if "VariationID" not in frame.columns:
        return frame
    identified = frame.loc[pd.to_numeric(frame["VariationID"], errors="coerce").notna()].drop_duplicates("VariationID")
    anonymous = frame.loc[pd.to_numeric(frame["VariationID"], errors="coerce").isna()]
    return pd.concat([identified, anonymous], ignore_index=True)


def _page(table: str, frame: pd.DataFrame, columns: list[str], limit: int) -> dict[str, Any]:
    records = _records(frame.head(limit), columns)
    return {
        "table": table,
        "n_matches": int(len(frame)),
        "returned": len(records),
        "records": records,
    }


def build_classifier_tools(catalog: ClassifierCatalog) -> list:
    """The two dataset tools. PubMed is attached separately through MCP."""

    @tool
    def query_joined_dataset(
        gene: str | None = None,
        variation_id: int | None = None,
        variant_name: str | None = None,
        label: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> str:
        """Query clinvar_uniprot_joined.parquet from the pathogenicity classifier.

        The table is the ClinVar–UniProt gene-level join (expert-reviewed pathogenic
        and benign variants, plus unmatched protein rows). Filter with at least one
        of gene, variation_id, variant_name (ClinVar Name / HGVS), or label
        (pathogenic or benign). VUS model scores are a different tool.
        """
        try:
            payload = catalog.query_joined_dataset(
                gene=gene,
                variation_id=variation_id,
                variant_name=variant_name,
                label=label,
                limit=limit,
            )
        except FileNotFoundError as exc:
            payload = {"error": str(exc)}
        return json.dumps(payload)

    @tool
    def query_scored_vus(
        gene: str | None = None,
        variation_id: int | None = None,
        variant_name: str | None = None,
        pred_label: str | None = None,
        min_proba: float | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> str:
        """Query vus_inference_predictions.parquet, the classifier's scored VUS table.

        Each row is a ClinVar variant of uncertain significance with the stored
        CatBoost probability (y_proba), decision threshold, and pred_label.
        Filter with gene, variation_id, variant_name, pred_label (pathogenic or
        benign), or min_proba. Results are sorted by y_proba descending.
        """
        try:
            payload = catalog.query_scored_vus(
                gene=gene,
                variation_id=variation_id,
                variant_name=variant_name,
                pred_label=pred_label,
                min_proba=min_proba,
                limit=limit,
            )
        except FileNotFoundError as exc:
            payload = {"error": str(exc)}
        return json.dumps(payload)

    return [query_joined_dataset, query_scored_vus]
