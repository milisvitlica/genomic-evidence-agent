# Combined investigation

Question: what is the ClinVar label for VariationID 7884, and find one PubMed paper on ABCA4 Val2050Leu?

```bash
curl -sS -m 120 http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question":"What is the ClinVar label for VariationID 7884, and find one PubMed paper on ABCA4 Val2050Leu?"}'
```

The agent calls both tools in one turn:

- `query_joined_dataset` with `variation_id` 7884, which returns label `benign`
- `search_pubmed` with query `ABCA4 Val2050Leu` and `max_results` 1, which returns PMID 28061825

A later message can stay on the same conversation. Copy `thread_id` from the response:

```bash
curl -sS -m 120 http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question":"Anything in ClinVar on this?","thread_id":"PASTE-THE-ID"}'
```

Keep the question inside one pair of quotes. A follow-up about HER2-positive cancer, after a PubMed search on that topic, called `query_joined_dataset` for gene ERBB2 and found the UniProt-only row `P04626`, with no ClinVar variation id in the joined table.

`thread_id` lives in the server process. Restarting the server clears it. Omitting `thread_id` starts a new conversation.
