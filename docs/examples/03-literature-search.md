# Literature search

Question: find PubMed articles about ABCA4 Val2050Leu.

```bash
curl -sS -m 120 http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question":"Find PubMed articles about ABCA4 Val2050Leu."}'
```

The agent calls `search_pubmed` with query `ABCA4 Val2050Leu`.

NCBI returned one article for that query: PMID 28061825, "New CDH3 mutation in the first Spanish case of hypotrichosis with juvenile macular dystrophy, a case report." The tool returns PMID, title, authors, journal, date, and DOI. It does not download the full text.

A broader query, `AIPL1 Leber congenital amaurosis`, returned eight articles. The first was PMID 30578499, "Leber Congenital Amaurosis."
