# Variant lookup

These questions were answered from `clinvar_uniprot_joined.parquet` through `query_joined_dataset`.

## VariationID 7884

**Question:** What does the joined classifier table say about ClinVar VariationID 7884?

**Evidence returned:** One row (`n_matches` 1).

| Field | Value |
| --- | --- |
| VariationID | 7884 |
| Name | `NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)` |
| Gene | ABCA4 (`HGNC:34`) |
| ClinicalSignificance | Likely benign |
| label | benign |
| ReviewStatus | reviewed by expert panel |
| NumberSubmitters | 22 |
| UniProt | `P78363` (`ABCA4_HUMAN`) |
| match_type | both |

**Final answer:** ClinVar VariationID 7884 corresponds to the ABCA4 gene variant NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu). It is labeled as "benign" with likely benign clinical significance, and this classification is reviewed by an expert panel. The variant is associated with diseases such as Stargardt disease 1 and other retinal dystrophies, but is considered non-pathogenic based on the expert review.

**Limitations:** `label` is the collapsed class `benign`. `ClinicalSignificance` is the ClinVar string `Likely benign`. The phenotype list is truncated and records conditions submitted with the variant. The protein function and disease text on the row describe ABCA4, and they are truncated at 400 characters.

## Three pathogenic BRCA2 variants

**Question:** List 3 pathogenic BRCA2 variants from the joined dataset.

**Evidence returned:** 651 pathogenic BRCA2 rows. The tool returned the first 3, all `label` pathogenic, UniProt `P51587`, review status reviewed by expert panel.

| VariationID | Name | Submitters |
| --- | --- | --- |
| 9340 | `NM_000059.4(BRCA2):c.8165C>G (p.Thr2722Arg)` | 23 |
| 9343 | `NM_000059.4(BRCA2):c.8219T>A (p.Leu2740Ter)` | 5 |
| 9344 | `NM_000059.4(BRCA2):c.4648G>T (p.Glu1550Ter)` | 9 |

**Final answer:** Here are 3 pathogenic BRCA2 variants from the joined dataset:

1. VariationID 9340: NM_000059.4(BRCA2):c.8165C>G (p.Thr2722Arg)
2. VariationID 9343: NM_000059.4(BRCA2):c.8219T>A (p.Leu2740Ter)
3. VariationID 9344: NM_000059.4(BRCA2):c.4648G>T (p.Glu1550Ter)

All are reviewed by expert panel and associated with breast-ovarian cancer susceptibility.

**Limitations:** The three rows are a page of 651 matches, with `limit` 3. They are the first rows the filter returned, so the list is a sample of the expert-reviewed pathogenic set.

## UniProt entry for the ABCA4 variant

**Question:** What UniProt entry is joined to NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu)?

**Evidence returned:** The tool searched `variant_name` `NM_000350.3(ABCA4):c.6148G>C` and returned the same VariationID 7884 row. UniProt entry `P78363`, entry name `ABCA4_HUMAN`, protein name retinal-specific phospholipid-transporting ATPase ABCA4, `match_type` both.

**Final answer:** The UniProt entry joined to NM_000350.3(ABCA4):c.6148G>C (p.Val2050Leu) is P78363, also known as ABCA4_HUMAN. It encodes the retinal-specific phospholipid-transporting ATPase ABCA4.

**Limitations:** The join is gene-level. `P78363` identifies the ABCA4 protein record attached to this ClinVar variant. It is a protein accession for the gene, and the row also carries the variant name and VariationID.

## Pathogenic CFTR variants

**Question:** Show a few pathogenic CFTR variants from the joined dataset.

**Evidence returned:** 238 pathogenic CFTR rows. The tool returned 5, UniProt `P13569`.

| VariationID | Name | ReviewStatus |
| --- | --- | --- |
| 7107 | `NM_000492.4(CFTR):c.1477C>T (p.Gln493Ter)` | reviewed by expert panel |
| 7109 | `NM_000492.4(CFTR):c.350G>A (p.Arg117His)` | practice guideline |
| 7110 | `NM_000492.4(CFTR):c.1040G>C (p.Arg347Pro)` | practice guideline |
| 7111 | `NM_000492.4(CFTR):c.1364C>A (p.Ala455Glu)` | practice guideline |
| 7112 | `NM_000492.4(CFTR):c.1585-1G>A` | practice guideline |

**Final answer:** Here are a few pathogenic CFTR variants from the joined dataset:

1. VariationID 7107: NM_000492.4(CFTR):c.1477C>T (p.Gln493Ter)
2. VariationID 7109: NM_000492.4(CFTR):c.350G>A (p.Arg117His)
3. VariationID 7110: NM_000492.4(CFTR):c.1040G>C (p.Arg347Pro)
4. VariationID 7111: NM_000492.4(CFTR):c.1364C>A (p.Ala455Glu)
5. VariationID 7112: NM_000492.4(CFTR):c.1585-1G>A

All are linked to Cystic fibrosis and related disorders. Let me know if you want more details on any specific variant.

**Limitations:** Five of 238 rows were returned (`limit` 5). Review status is mixed: VariationID 7107 is expert-panel reviewed, and the other four are practice guideline. The phenotype text on each row is truncated.
