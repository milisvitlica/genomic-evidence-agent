"""PubMed search and article details.

NCBI E-utilities supply citation metadata. ``get_article_details`` also returns
the abstract. ``python -m genomic_evidence_agent.mcp`` exposes both functions
over stdio. Neither tool downloads full text.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import httpx

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME = "genomic-evidence-agent"
DEFAULT_MAX_RESULTS = 8
MAX_RESULTS = 20
_PMID = re.compile(r"\d{1,9}")


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


def normalize_pmid(pmid: str) -> str | None:
    """Return the first PMID digit group, or None when the text has no PMID."""
    match = _PMID.search(pmid.strip())
    return match.group(0) if match else None


def parse_pubmed_article(xml_text: str, pmid: str) -> dict[str, Any] | None:
    """Turn one PubMed efetch XML record into metadata plus the abstract."""
    root = ElementTree.fromstring(xml_text)
    article = root.find(".//{*}PubmedArticle")
    if article is None:
        return None
    authors: list[str] = []
    for author in article.findall(".//{*}AuthorList/{*}Author"):
        collective = _text(author.find("{*}CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        name = " ".join(
            part
            for part in (_text(author.find("{*}LastName")), _text(author.find("{*}ForeName")))
            if part
        )
        if name:
            authors.append(name)
    abstract_parts: list[str] = []
    for node in article.findall(".//{*}Abstract/{*}AbstractText"):
        text = "".join(node.itertext()).strip()
        if not text:
            continue
        label = (node.attrib.get("Label") or "").strip()
        abstract_parts.append(f"{label}: {text}" if label else text)
    doi = None
    for node in article.findall(".//{*}ArticleId"):
        if node.attrib.get("IdType") == "doi" and _text(node):
            doi = _text(node)
            break
    return {
        "pmid": pmid,
        "title": _text(article.find(".//{*}ArticleTitle")),
        "journal": _text(article.find(".//{*}Journal/{*}ISOAbbreviation"))
        or _text(article.find(".//{*}Journal/{*}Title")),
        "pubdate": _pubdate(article.find(".//{*}JournalIssue/{*}PubDate")),
        "authors": authors[:20],
        "doi": doi,
        "abstract": "\n\n".join(abstract_parts) or None,
    }


def get_article_details(
    pmid: str,
    *,
    api_key: str | None = None,
    email: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch metadata and the abstract for one PMID. Full text is not fetched."""
    cleaned = normalize_pmid(pmid)
    if not cleaned:
        return {"error": "Provide a PubMed PMID."}
    owns_client = client is None
    http = client or httpx.Client(timeout=30)
    try:
        response = http.get(
            EFETCH_URL,
            params={**_ncbi_params(api_key, email), "db": "pubmed", "id": cleaned, "retmode": "xml"},
        )
        response.raise_for_status()
        try:
            article = parse_pubmed_article(response.text, cleaned)
        except ElementTree.ParseError:
            return {"error": "PubMed returned an unreadable record.", "pmid": cleaned}
    except httpx.HTTPError as exc:
        return {"error": f"PubMed request failed: {exc}", "pmid": cleaned}
    finally:
        if owns_client:
            http.close()
    if article is None:
        return {"error": f"No PubMed record for PMID {cleaned}.", "pmid": cleaned}
    return article


def _ncbi_params(api_key: str | None, email: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"tool": TOOL_NAME}
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _text(node: ElementTree.Element | None) -> str | None:
    if node is None:
        return None
    text = "".join(node.itertext()).strip()
    return text or None


def _pubdate(node: ElementTree.Element | None) -> str | None:
    if node is None:
        return None
    medline = _text(node.find("{*}MedlineDate"))
    if medline:
        return medline
    parts = [_text(node.find(f"{{*}}{name}")) for name in ("Year", "Month", "Day")]
    date = " ".join(part for part in parts if part)
    return date or None


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
    common = {**_ncbi_params(api_key, email), "retmode": "json"}

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
