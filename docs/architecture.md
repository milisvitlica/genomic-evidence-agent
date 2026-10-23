# Architecture

The browser page at `/` posts a question to `POST /evidence`. FastAPI hands it to a LangGraph agent. The agent calls one or more tools, then writes the answer. The page shows that answer and the tool trace, and sends the returned `thread_id` on the next question. `GET /health` reports whether the two classifier tables and the PubMed tools loaded. It does not call the model.

## Request path

1. `api/app.py` starts the agent once, in the FastAPI lifespan.
2. `agent/graph.py` builds the tool list and compiles it with `create_agent`. The graph has a `model` node and a `tools` node. `MemorySaver` keeps a conversation under `thread_id`.
3. `agent/prompts.py` tells the model to call a tool before stating a label, a score, or a paper.
4. `agent/trace.py` records each tool call and tool result. That file is appended under `logs/`, which Git ignores.

## Tools

| Tool | Code | Data |
| --- | --- | --- |
| `query_joined_dataset` | `tools/classifier.py` | `clinvar_uniprot_joined.parquet` |
| `query_scored_vus` | `tools/classifier.py` | `vus_inference_predictions.parquet` |
| `search_pubmed` | `tools/pubmed.py`, served by `mcp/pubmed_server.py` | NCBI E-utilities |
| `get_article_details` | `tools/pubmed.py`, served by `mcp/pubmed_server.py` | NCBI E-utilities, including the abstract |

`tools/pubmed.py` holds the NCBI search and the single-PMID lookup. `python -m genomic_evidence_agent.mcp` serves both as a FastMCP process over stdio. The API launches that command at startup and keeps the session open until shutdown, so a tool call reuses the process. Another MCP client can run the same command.

The classifier checkout is a sibling project. This service reads its processed tables. It does not reload the CatBoost model. A VUS `pred_label` is the stored probability compared with the saved Youden threshold.

## What is committed

`docs/examples/` records each reviewed run as the question, the evidence returned, the agent's final answer, and the limitations. The page button **Save example** posts the current `thread_id` to `POST /examples`. That writes a new file under `docs/examples/saved_examples/` from the stored messages. The agent does not choose when to save. That folder is gitignored. `tests/fixtures/` holds the small JSON files the tests compare against. `tests/unit/` covers individual functions. `tests/integration/` covers the API, classifier tool calls, and the PubMed MCP lifecycle. `tests/evals/` checks a few representative records and grades `golden_cases.csv`: retrieved fields, tool choice, and whether an answer reports that evidence. The run writes `outputs/evals/report.md` with `n_passed / n_total`. `logs/` and `outputs/` stay out of Git.

`scripts/run_examples.py` posts a fixed question list to a running server and writes each response under `outputs/examples/`. Review those drafts, then copy the cases you want into `docs/examples/` and write the limitations there. The script does not edit the committed examples.
