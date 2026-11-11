# Agent eval

5 / 5 passed

- Run started: 2026-11-11 15:53:00 CET (UTC+0100)
- Duration: 27 s
- Model: openai:gpt-4.1-mini
- System prompt hash: 31a98075
- Golden cases hash: c7368c2c

| Case | Result | Tools the agent called | Problems |
| --- | --- | --- | --- |
| joined-variation-7884 | pass | query_joined_dataset variation_id=7884 |  |
| vus-only-292 | pass | query_scored_vus variation_id=292, query_joined_dataset variation_id=292 |  |
| brca2-pathogenic-page | pass | query_joined_dataset gene=BRCA2 label=pathogenic limit=25 |  |
| pubmed-no-papers | pass | search_pubmed query=zzzznotagene999 p.NoSuchChange |  |
| joined-and-vus-disagree-7884 | pass | query_joined_dataset variation_id=7884, query_scored_vus variation_id=7884 |  |