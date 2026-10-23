# Variant lookup

Question: what does the joined classifier table say about ClinVar VariationID 7884?

```bash
curl -sS -m 120 http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question":"What does the joined classifier table say about ClinVar VariationID 7884?"}'
```

The agent calls `query_joined_dataset` with `variation_id` 7884.

The joined table returns one row:

- VariationID 7884
- `NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)`
- gene ABCA4
- label `benign`
- UniProt entry `P78363`

The stable fields are also in `tests/fixtures/variant_lookup_expected.json`.
