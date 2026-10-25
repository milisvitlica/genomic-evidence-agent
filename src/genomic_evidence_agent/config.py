"""Runtime settings. Paths and model names come from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/genomic_evidence_agent/config.py -> repository root is parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
# The OpenAI client reads OPENAI_API_KEY from the process environment.
# pydantic-settings loads .env into Settings only, so export it here too.
load_dotenv(_REPO_ROOT / ".env")


def repo_root() -> Path:
    """Directory that contains pyproject.toml, docs/, logs/, and outputs/."""
    return _REPO_ROOT


_DEFAULT_JOINED_DATASET = (
    _REPO_ROOT.parent
    / "clinvar-pathogenicity-classifier"
    / "data"
    / "processed"
    / "clinvar_uniprot_joined.parquet"
)
_DEFAULT_SCORED_VUS = (
    _REPO_ROOT.parent
    / "clinvar-pathogenicity-classifier"
    / "data"
    / "processed"
    / "vus_inference_predictions.parquet"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    joined_dataset: Path = _DEFAULT_JOINED_DATASET
    scored_vus: Path = _DEFAULT_SCORED_VUS
    model: str = "openai:gpt-4.1-mini"

    pubmed_mcp_enabled: bool = True
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
