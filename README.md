# Genomic Evidence Agent

Research assistant that answers questions about human variants by calling tools.
Two read processed tables from
[clinvar-pathogenicity-classifier](../clinvar-pathogenicity-classifier).
Another searches PubMed through a stdio MCP server. A LangGraph agent
decides which tool to call. FastAPI exposes the agent over HTTP. The page can
save the current chat to `docs/examples/saved_examples/` without asking the agent.

This is research support. It does not produce a clinical classification.

## Tools

| Tool | Source |
| --- | --- |
| `query_joined_dataset` | `data/processed/clinvar_uniprot_joined.parquet` |
| `query_scored_vus` | `data/processed/vus_inference_predictions.parquet` |
| `search_pubmed` | PubMed MCP server (`python -m genomic_evidence_agent.mcp`) |
| `get_article_details` | Same server; metadata and abstract for one PMID |

The joined table is the classifier's ClinVar–UniProt gene-level join (expert-reviewed
pathogenic and benign variants). The scored VUS table is the stored CatBoost
output: probability, Youden threshold, and `pred_label`. This service does not
reload the model. PubMed search returns article metadata (PMID, title, authors,
journal, date, DOI) so a later ranking step can reorder those hits.
`get_article_details` adds the abstract for one of those PMIDs.

PubMed is the MCP server because the search is not tied to these tables: another agent can reuse it, and the server only wraps a public API (the NCBI key and rate limits are the sensitive part). Ranking, caching, and query logic can change there without changing the agent. It is also the concrete place to see tools, schemas, transports, and session lifecycle.

## Stack

- **LangGraph** — `langchain.agents.create_agent` compiles the tool-calling graph.
- **FastAPI** — a page at `/`, plus `GET /health` and `POST /evidence`.
- **PubMed MCP** — a FastMCP server over stdio, adapted with `langchain.mcp.MCPAdapter`.
  NCBI is called with `httpx`. Node.js is not required. The API keeps one session open.

## Layout

```
src/genomic_evidence_agent/   # application code
  agent/                      # LangGraph graph, prompt, request trace
  tools/                      # classifier queries and PubMed search
  mcp/                        # PubMed MCP server (stdio)
  api/                        # FastAPI and the browser page
tests/
  fixtures/                   # expected JSON
  unit/                       # individual functions
  integration/                # API, tool calls, MCP lifecycle
  evals/                      # representative evidence checks
docs/
  architecture.md
  examples/                   # reviewed examples for the repository
scripts/
  run_examples.py             # posts the fixed questions; writes outputs/examples
outputs/                      # generated example runs; ignored by Git
logs/                         # runtime traces; ignored by Git
```

See `docs/architecture.md` for the request path. The worked examples are in `docs/examples/`.

To refresh them, start the server and run `python scripts/run_examples.py`. Review `outputs/examples/`, then copy the cases you want into `docs/examples/`.

## Getting started

Python 3.10+.

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
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

Open http://127.0.0.1:8000 to ask a question in the browser. A follow-up stays on the same conversation until you start a new one. `GET /health` lists the loaded tools and whether the classifier tables are on disk.

The same PubMed server can run on its own. From this environment:

```bash
python -m genomic_evidence_agent.mcp
```

It speaks MCP on stdin and stdout. The API launches that command when it starts. Another client can launch it too, with `NCBI_API_KEY` and `NCBI_EMAIL` in the environment when you have them.

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
pytest tests/unit
pytest tests/integration
pytest tests/evals
```

Integration and eval tests read the sibling checkout when those parquet files are present
and skip otherwise.
