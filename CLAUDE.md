# C2 Intelligence — Session Protocol

This file is read at the start of every Claude Code session working on this repo. Read it, then act.

## Session opening protocol

1. `cd C2Intelligence-v2 && git pull origin main`
2. Read this file (CLAUDE.md).
3. `gcloud config set project c2-intelligence`
4. Confirm MCP Toolbox service is running: `gcloud run services describe c2-toolbox --region <REGION> --format='value(status.url)'`
5. Confirm `git rev-parse HEAD` matches the commit you expect to be working from.
6. Then act. **Never clone — always pull.**

## Naming conventions (locked)

| Resource | Identifier |
|---|---|
| GCP project | `c2-intelligence` |
| BigQuery dataset | `c2_warehouse` |
| Service accounts | `c2-api`, `c2-ingestion`, `c2-toolbox` |
| Cloud Run services | `c2-api`, `c2-ingestion`, `c2-toolbox` |
| Cloud Storage buckets | `c2-documents-l1`, `c2-documents-l2a`, `c2-documents-l2b` (must be globally unique — append a project suffix if these are taken) |

## Region decision — TO BE FILLED IN AT TASK 0.1

Run `infra/00_verify_region.sh` first. Record the outcome here:

```
REGION_BIGQUERY=        # me-central1 (target)
REGION_CLOUD_RUN=       # me-central1 (target)
REGION_VERTEX_AI=       # me-central1 if available, else europe-west4
REGION_DOCUMENT_AI=     # eu (no GCC option)
SPLIT_REGIONS=          # YES if Vertex AI not in me-central1, NO otherwise
DECISION_DATE=          # YYYY-MM-DD
```

If `SPLIT_REGIONS=YES`, also document the cross-region data flow in `C2_MASTER_PLAN.md`.

## Locked Claude model ID — TO BE FILLED IN AT TASK 0.1

Read the exact `claude-…@YYYYMMDD` ID off the Vertex AI model garden. Store in Secret Manager as `CLAUDE_MODEL_ID`. **Never `@latest`.**

```
CLAUDE_MODEL_ID=        # e.g. claude-sonnet-4-5@20251015
SECRET_MANAGER_KEY=projects/c2-intelligence/secrets/CLAUDE_MODEL_ID/versions/latest
```

## Locked embedding configuration

| Setting | Value |
|---|---|
| Model | `text-embedding-004` |
| Dimensions | `768` |
| Chunk target | `500` tokens |
| Chunk overlap | `50` tokens |
| Max chunk | `600` tokens |
| Min chunk | `50` tokens |

These are referenced as constants in `ingestion/pipeline.py`. Do not change.

## Execution rules

1. **One task per commit. No batching.**
2. **QG PASS required before next task.** QG PASS = Claude Chat independently verifies via MCP Toolbox or `gcloud` CLI output.
3. **No self-reporting.** Claude Code does not say "done" — Claude Chat verifies and says "PASS".
4. Yasser approves each commit before Claude Code proceeds.
5. Claude Code always runs `git pull` before any work. Never clones.
6. Secrets in Secret Manager only. **Never hardcoded.** Never in environment variable defaults in source.
7. API versioned at `/api/v1/`.
8. Claude model string locked in Phase 0. Never `@latest`.
9. Two-path PDF ingestion: digital → PyMuPDF (GCC-resident); scanned → Document AI EU endpoint (flagged `EXTERNAL_OCR`).
10. Vector search runs in `c2-api` Python only — **NOT** via MCP Toolbox.
11. Authorization is enforced at the API layer via `project_members` — **NOT** BigQuery RLS.

## Verification backbone

Claude Chat connects to `c2-toolbox` (deployed to Cloud Run with OAuth) as a custom MCP connector at claude.ai. Every task is independently verified by Claude Chat querying BigQuery directly through this connector before PASS is issued.

If the MCP connector is not yet wired up, no PASS can be issued for any task that touches BigQuery — block on Phase 2.

## Out of scope (deferred to v1.1)

- Automated report generation
- Multi-project comparison
- Mobile-optimised UI
- CMEK / customer-managed encryption keys

Do not build these in v1.0.
