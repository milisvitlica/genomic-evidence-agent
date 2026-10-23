"""PubMed search.

NCBI E-utilities return article metadata only. The in-process MCP server in
``mcp/pubmed_server.py`` exposes ``search_pubmed`` to the agent.
"""

from __future__ import annotations

from typing import Any

import httpx

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
TOOL_NAME = "genomic-evidence-agent"
DEFAULT_MAX_RESULTS = 8
MAX_RESULTS = 20


def parse_pubmed_summary(payload: dict[str, Any], pmids: list[str]) -> list[dict[str, Any]]:
    """Turn an esummary JSON payload into a short article list, in PMID order."""
    result = payload.get("result") or {}
    articles: list[dict[str, Any]] = []
    for pmid in pmids:
        item = result.get(str(pmid))
        if not isinstance(item, dict):
            continue
        authors = [
            author.get("name")
            for author in item.get("authors") or []
            if isinstance(author, dict) and author.get("name")
        ]
        doi = None
        for article_id in item.get("articleids") or []:
            if isinstance(article_id, dict) and article_id.get("idtype") == "doi":
                doi = article_id.get("value")
                break
        articles.append(
            {
                "pmid": str(pmid),
                "title": item.get("title"),
                "journal": item.get("source"),
                "pubdate": item.get("pubdate"),
                "authors": authors[:8],
                "doi": doi,
            }
        )
    return articles


def search_pubmed(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    api_key: str | None = None,
    email: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Search PubMed and return article metadata. Full text is not fetched."""
    text = query.strip()
    if not text:
        return {"error": "Provide a PubMed query."}
    retmax = max(1, min(int(max_results), MAX_RESULTS))
    common: dict[str, Any] = {"tool": TOOL_NAME, "retmode": "json"}
    if email:
        common["email"] = email
    if api_key:
        common["api_key"] = api_key

    owns_client = client is None
    http = client or httpx.Client(timeout=30)
    try:
        search = http.get(
            ESEARCH_URL,
            params={**common, "db": "pubmed", "term": text, "retmax": retmax, "sort": "relevance"},
        )
        search.raise_for_status()
        id_list = [str(pmid) for pmid in search.json().get("esearchresult", {}).get("idlist", [])]
        if not id_list:
            return {"query": text, "n_results": 0, "articles": []}
        summary = http.get(
            ESUMMARY_URL,
            params={**common, "db": "pubmed", "id": ",".join(id_list)},
        )
        summary.raise_for_status()
        articles = parse_pubmed_summary(summary.json(), id_list)
    except httpx.HTTPError as exc:
        return {"error": f"PubMed request failed: {exc}", "query": text}
    finally:
        if owns_client:
            http.close()
    return {"query": text, "n_results": len(articles), "articles": articles}
