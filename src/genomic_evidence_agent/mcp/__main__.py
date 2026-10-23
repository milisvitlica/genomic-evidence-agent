"""Run the PubMed MCP server over stdio.

Any MCP client can start this process and talk to it on stdin/stdout::

    python -m genomic_evidence_agent.mcp

The local evidence agent launches the same command. NCBI credentials come from
the environment (``NCBI_API_KEY``, ``NCBI_EMAIL``).
"""

from __future__ import annotations

from genomic_evidence_agent.config import get_settings
from genomic_evidence_agent.mcp.pubmed_server import build_pubmed_server


def main() -> None:
    """Serve search_pubmed and get_article_details on stdio."""
    build_pubmed_server(get_settings()).run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
