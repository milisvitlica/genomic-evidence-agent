# Genomic Evidence Agent

Research assistant that answers questions about human variants by calling three tools.
Two read processed tables from
[clinvar-pathogenicity-classifier](../clinvar-pathogenicity-classifier).
The third searches PubMed through an in-process MCP server. A LangGraph agent
decides which tool to call. FastAPI exposes the agent over HTTP.

This is research support. It does not produce a clinical classification.

## Tools

| Tool | Source |
| --- | --- |
| `query_joined_dataset` | `data/processed/clinvar_uniprot_joined.parquet` |
| `query_scored_vus` | `data/processed/vus_inference_predictions.parquet` |
| `search_pubmed` | In-process MCP server calling NCBI E-utilities |

The joined table is the classifier's ClinVar–UniProt gene-level join (expert-reviewed
pathogenic and benign variants). The scored VUS table is the stored CatBoost
output: probability, Youden threshold, and `pred_label`. This service does not
reload the model. PubMed search returns article metadata (PMID, title, authors,
journal, date, DOI) so a later ranking step can reorder those hits.

## Stack

- **LangGraph** — `langchain.agents.create_agent` compiles the tool-calling graph.
- **FastAPI** — `GET /health` and `POST /evidence`.
- **PubMed MCP** — a FastMCP server in this process, adapted with `langchain.mcp.MCPAdapter`.
  NCBI is called with `httpx`. Node.js is not required.

## Layout

```
genomic_evidence_agent/
  tools/
    classifier.py        # joined-dataset and scored-VUS queries
    pubmed.py            # PubMed search and LangChain wrapper
  mcp/
    pubmed_server.py     # in-process FastMCP server
  agent/                 # LangGraph graph, prompt, request trace
  api/                   # FastAPI
docs/
  architecture.md
  examples/              # committed question/tool-call examples
tests/
  fixtures/              # expected JSON checked by pytest
logs/                    # runtime traces; ignored by Git
```

See `docs/architecture.md` for the request path. The four worked examples are in `docs/examples/`.

## Getting started

Python 3.10+.

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Set `CLASSIFIER_ROOT` if the classifier checkout is not the sibling directory
`../clinvar-pathogenicity-classifier`. Set `OPENAI_API_KEY` for the default
`openai:gpt-4.1-mini` model. Change `MODEL` to another `provider:name` string
and install that provider package if you use a different one.

Optional NCBI credentials (`NCBI_API_KEY`, `NCBI_EMAIL`) raise the PubMed rate limit.
Set `PUBMED_MCP_ENABLED=false` to run with the two dataset tools only.

```bash
python -m uvicorn genomic_evidence_agent.api.app:app --host 127.0.0.1 --port 8000
```

`GET /health` lists the three tools and whether the classifier tables are on disk.

```bash
curl -s http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question": "What does the joined classifier table say about ClinVar VariationID 7884?"}'
```

Pass the returned `thread_id` on the next request to continue the same conversation.
Memory is in-process (`MemorySaver`).

## Tests

```bash
pytest
```

Dataset tests read the sibling checkout when those parquet files are present
and skip otherwise.
