# Scored VUS

Question: what score does the scored VUS table give VariationID 292?

```bash
curl -sS -m 120 http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question":"What score does the scored VUS table give VariationID 292?"}'
```

The agent calls `query_scored_vus` with `variation_id` 292.

The row is VWF `NM_000552.5(VWF):c.4837T>C (p.Ser1613Pro)`:

- `y_proba` about 0.557
- threshold about 0.495
- `pred_label` `pathogenic`

`y_proba` is the stored pathogenic score. The same question for VariationID 7884 calls `query_scored_vus` and returns `n_matches` 0, because that variant is labeled in the joined table and is not in the VUS file.
