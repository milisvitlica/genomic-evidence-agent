# Genomic Evidence Agent

A research assistant that answers questions about human variants by calling tools.
It reads two parquet tables built by
[clinvar-pathogenicity-classifier](https://github.com/milisvitlica/clinvar-pathogenicity-classifier)
and searches PubMed through an MCP server. A LangGraph agent decides which tool to
call, and FastAPI serves it over HTTP with a small browser page.

This is research support. It does not produce a clinical classification.

## Tools

| Tool | Source |
| --- | --- |
| `query_joined_dataset` | `JOINED_DATASET` (`clinvar_uniprot_joined.parquet`) |
| `query_scored_vus` | `SCORED_VUS` (`vus_inference_predictions.parquet`) |
| `search_pubmed` | PubMed MCP server (`python -m genomic_evidence_agent.mcp`) |
| `get_article_details` | Same server; metadata and abstract for one PMID |

The joined table is the classifier's ClinVar–UniProt gene-level join (expert-reviewed
pathogenic and benign variants). The scored VUS table is the stored CatBoost output:
probability, Youden threshold, and `pred_label`. This service does not reload the model.

`search_pubmed` returns PMID, title, authors, journal, date, and DOI.
`get_article_details` adds the abstract for one PMID. Neither fetches full text.

PubMed is on MCP because it is not tied to these tables. Another agent can reuse it,
it only wraps a public API, and its search logic can change without changing the agent.
The API starts it as a stdio process and keeps one session open. Node.js is not required.

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

Edit `.env`:

- `OPENAI_API_KEY` for the default `openai:gpt-4.1-mini` model. Set `MODEL` to another
  `provider:name` string and install that provider's package to use a different one.
- `JOINED_DATASET` and `SCORED_VUS` are the two parquet paths. They default to
  `../clinvar-pathogenicity-classifier/data/processed/clinvar_uniprot_joined.parquet` and
  `../clinvar-pathogenicity-classifier/data/processed/vus_inference_predictions.parquet`.
- `NCBI_API_KEY` and `NCBI_EMAIL` are optional and raise the PubMed rate limit.
- `PUBMED_MCP_ENABLED=false` runs with the two dataset tools only.

Start the API:

```bash
python -m uvicorn genomic_evidence_agent.api.app:app --host 127.0.0.1 --port 8000
```

## Usage

Open http://127.0.0.1:8000 to ask questions in the browser. Follow-ups stay on the same
conversation until you start a new one. **Save example** writes the current chat to
`docs/examples/saved_examples/` without asking the agent. `GET /health` lists the loaded
tools and whether the two parquet files are on disk.

From a terminal:

```bash
curl -s http://127.0.0.1:8000/evidence \
  -H 'content-type: application/json' \
  -d '{"question": "What does the joined classifier table say about ClinVar VariationID 7884?"}'
```

Pass the returned `thread_id` on the next request to continue the conversation. Memory is
in-process (`MemorySaver`), so a restart clears it.

The PubMed server also runs on its own and speaks MCP on stdin and stdout. Any MCP client
can launch it, with `NCBI_API_KEY` and `NCBI_EMAIL` in the environment if you have them:

```bash
python -m genomic_evidence_agent.mcp
```

## Rebuild the datasets

Clone [clinvar-pathogenicity-classifier](https://github.com/milisvitlica/clinvar-pathogenicity-classifier)
and follow its README: "Build the dataset" writes `data/processed/clinvar_uniprot_joined.parquet`,
and "Inference" writes `data/processed/vus_inference_predictions.parquet`. Then point
`JOINED_DATASET` and `SCORED_VUS` in `.env` at those two files.

## Run with Docker

Build the image from this repository and mount the two parquet files. The `-e` paths are
inside the container and the `-v` sources are the files on the host. The key comes from
`--env-file`.

```bash
docker build -t genomic-evidence-agent .
docker run --rm -p 8000:8000 \
  --env-file .env \
  -e JOINED_DATASET=/data/clinvar_uniprot_joined.parquet \
  -e SCORED_VUS=/data/vus_inference_predictions.parquet \
  -v /absolute/path/clinvar_uniprot_joined.parquet:/data/clinvar_uniprot_joined.parquet:ro \
  -v /absolute/path/vus_inference_predictions.parquet:/data/vus_inference_predictions.parquet:ro \
  genomic-evidence-agent
```

Open http://127.0.0.1:8000. `GET /health` shows whether the container can see both files.

## Project layout

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
  evals/                      # golden cases and evidence checks
docs/
  architecture.md
  examples/                   # reviewed examples for the repository
scripts/
  run_examples.py             # posts the fixed questions; writes outputs/examples
outputs/                      # generated runs and eval reports; ignored by Git
logs/                         # runtime traces; ignored by Git
```

See `docs/architecture.md` for the request path and `docs/examples/` for worked examples.
To refresh the examples, start the server and run `python scripts/run_examples.py`, review
`outputs/examples/`, then copy the cases you want into `docs/examples/`.

## Tests

```bash
pytest
pytest tests/unit
pytest tests/integration
pytest tests/evals
```

Integration and eval tests read `JOINED_DATASET` and `SCORED_VUS` and skip when those files
are missing. `tests/evals/golden_cases.csv` holds the questions, expected tool calls,
evidence fields, and answer checks. `pytest tests/evals` grades them without calling the
model and writes `outputs/evals/report.md`, whose first line is `n_passed / n_total`.
