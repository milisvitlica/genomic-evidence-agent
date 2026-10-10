"""Runtime settings. Paths and model names come from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/genomic_evidence_agent/config.py -> repository root is parents[2].
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
# The OpenAI client reads OPENAI_API_KEY from the process environment.
# pydantic-settings loads .env into Settings only, so export it here too.
load_dotenv(_PACKAGE_ROOT / ".env")


def default_classifier_root() -> Path:
    """Prefer the sibling clinvar-pathogenicity-classifier checkout."""
    candidates = [
        Path.cwd().parent / "clinvar-pathogenicity-classifier",
        _PACKAGE_ROOT.parent / "clinvar-pathogenicity-classifier",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return candidates[0]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    classifier_root: Path = Field(default_factory=default_classifier_root)
    model: str = "openai:gpt-4.1-mini"

    pubmed_mcp_enabled: bool = True
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
