# Scored VUS

These questions were answered from `vus_inference_predictions.parquet` through `query_scored_vus`. `y_proba` is the stored CatBoost pathogenic score. `pred_label` applies the saved Youden threshold, about 0.495. The tool returns rows sorted by `y_proba` descending. This is computational evidence.

## VariationID 292

**Question:** What score does the scored VUS table give VariationID 292?

**Evidence returned:** One row (`n_matches` 1).

| Field | Value |
| --- | --- |
| VariationID | 292 |
| Name | `NM_000552.5(VWF):c.4837T>C (p.Ser1613Pro)` |
| Gene | VWF |
| ClinicalSignificance | Uncertain significance |
| label | vus |
| y_proba | 0.557 |
| threshold | 0.495 |
| y_pred | 1 |
| pred_label | pathogenic |

**Final answer:** For VariationID 292 in the VWF gene, the scored VUS table gives a CatBoost model probability (y_proba) of approximately 0.557. The predicted label at the set threshold is "pathogenic."

**Limitations:** ClinVar still calls this variant uncertain significance. `pred_label` pathogenic means the stored score is above the Youden threshold. The score sits close to that threshold (0.557 versus 0.495). The service reads the stored table and does not rescore the variant.

## Highest BRCA1 score

**Question:** Which scored VUS for gene BRCA1 has the highest y_proba?

**Evidence returned:** 17 BRCA1 rows. With `limit` 1 the tool returned the top score.

| Field | Value |
| --- | --- |
| VariationID | 55732 |
| Name | `NM_007294.4(BRCA1):c.83T>C (p.Leu28Pro)` |
| ClinicalSignificance | Uncertain significance |
| y_proba | 0.726 |
| threshold | 0.495 |
| pred_label | pathogenic |

**Final answer:** The scored VUS for gene BRCA1 with the highest y_proba is the variant NM_007294.4(BRCA1):c.83T>C (p.Leu28Pro) with a y_proba of 0.726 and a pred_label of pathogenic.

**Limitations:** Highest `y_proba` is the strongest pathogenic score in this table, because the tool sorts pathogenic probability descending. ClinVar clinical significance on the row remains uncertain significance. The other 16 BRCA1 rows were not returned.

## VariationID 7884 is absent

**Question:** Is ClinVar VariationID 7884 in the scored VUS table?

**Evidence returned:** `query_scored_vus` with `variation_id` 7884 returned `n_matches` 0 and an empty record list. The same variant is in the joined table as ABCA4 `NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)`, `label` benign, VariationID 7884.

**Final answer:** ClinVar VariationID 7884 is not present in the scored VUS table.

**Limitations:** A zero match means this variant was not in the scored VUS file. The joined table already carries an expert-reviewed label for it. Absence from the VUS file supplies no new score.
