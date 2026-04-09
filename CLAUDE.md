# C2 Intelligence — CLAUDE.md
# Read this file completely at the start of every session before taking any action.

---

## 1. Session Opening Protocol

Execute in order at the start of every session:

1. `cd C2-rev && git pull origin main`
2. Read this file in full.
3. `gcloud config set project c2-intelligence`
4. If MCP Toolbox is deployed, confirm it is running:
   `gcloud run services describe c2-toolbox --region me-central1 --format='value(status.url)'`
5. Confirm HEAD: `git rev-parse HEAD`
6. Read **§12 Current Build State** to identify the next task.
7. Read the relevant task section in `C2_MASTER_PLAN.md`.
8. Then act. **Never clone — always pull.**

---

## 2. Roles

| Role | Responsibility |
|---|---|
| Yasser | Domain expert, product owner, approval gate before every commit |
| Claude Chat | Architecture, SQL, tools.yaml, prompts, independent verification via MCP Toolbox |
| Claude Code | Execution only — one task per commit, no action without explicit instruction from Yasser |

---

## 3. Execution Rules

1. **One task per commit. No batching.** Two small tasks are still two commits.
2. **QG PASS required before the next task.** Issued by Claude Chat only after independent verification. Never by Claude Code.
3. **No self-reporting.** Claude Code never declares a task complete or writes PASS.
4. **Yasser approves every commit** before Claude Code proceeds.
5. **Always `git pull` before any work.** Never clone.
6. **Secrets in Secret Manager only.** Never hardcoded. Never in committed env defaults.
7. **Never `@latest` for the Claude model string.**
8. **API versioned at `/api/v1/`.** Do not change.
9. **Do not build v1.1 features.** See §14.
10. **Deploy order is mandatory.** See §11. Never deploy out of sequence.

---

## 4. Verification Backbone

Claude Chat connects to `c2-toolbox` via OAuth as a custom MCP connector in Claude.ai. Every task that touches BigQuery is verified by Claude Chat before PASS is issued.

**No PASS can be issued for any BigQuery task until Task 2.5 confirms the connector is working.** The build blocks here until confirmed.

For infrastructure tasks: verification is via `gcloud` CLI output or Console screenshots shared by Yasser.

---

## 5. Naming Conventions (Locked)

| Resource | Identifier |
|---|---|
| GCP project | `c2-intelligence` |
| BigQuery dataset | `c2_warehouse` |
| Service accounts | `c2-api`, `c2-ingestion`, `c2-toolbox` |
| Cloud Run services | `c2-api`, `c2-ingestion`, `c2-toolbox` |
| Cloud Storage buckets | `c2-documents-l1`, `c2-documents-l2a`, `c2-documents-l2b` |
| Artifact Registry repo | `c2-images` |
| GLOBAL_STANDARDS project_id | `GLOBAL_STANDARDS` |

Bucket names must be globally unique. If taken, append a short suffix and record the actual names here.

---

## 6. Region Decision — Fill in at Task 0.1

**Expected outcome: `SPLIT_REGIONS=YES`.** Claude on Vertex AI is not available in `me-central1` as of the planning date. Treat the split-region path as the default until Task 0.1 proves otherwise.

```
REGION_BIGQUERY=me-central1
REGION_CLOUD_RUN=me-central1
REGION_VERTEX_AI=europe-west4
REGION_DOCUMENT_AI=eu
SPLIT_REGIONS=YES
DECISION_DATE=2026-04-09
```

> **Note:** Vertex AI `me-central1` availability to be re-verified after Task 0.2 — proceeding with `SPLIT_REGIONS=YES` per plan default. Cloud Run `me-central1` confirmed available.

If `SPLIT_REGIONS=YES`, this affects: `api/claude_client.py`, `api/embeddings.py`, `ingestion/pipeline.py`, all Vertex AI deploy flags.

---

## 7. Locked Claude Model ID — Fill in at Task 0.1

```
CLAUDE_MODEL_ID=        # PENDING — fill after Task 0.2 when Vertex AI Model Garden is accessible
SECRET_PATH=            projects/c2-intelligence/secrets/CLAUDE_MODEL_ID/versions/latest
```

`api/config.py` raises at import time if `@latest` is detected. Never use `@latest` anywhere.

---

## 8. Locked Architecture Constants

| Constant | Value | File |
|---|---|---|
| Embedding model | `text-embedding-004` | `ingestion/pipeline.py`, `api/embeddings.py` |
| Embedding dimensions | `768` | All producers and consumers |
| Embedding batch size | `25` | `ingestion/pipeline.py` |
| Chunk target tokens | `500` | `ingestion/pipeline.py` |
| Chunk overlap tokens | `50` | `ingestion/pipeline.py` |
| Max chunk tokens | `600` | `ingestion/pipeline.py` |
| Min chunk tokens | `50` | `ingestion/pipeline.py` |
| Session context window | Last 10 turns | `api/sessions.py` |
| Session expiry | 4 hours | `api/sessions.py` |
| Auth cache TTL | 300 seconds | `api/auth.py` |
| Project vector top_k | `8` (SQL literal) | `api/vector_search.py` |
| L2b vector top_k | `4` (SQL literal) | `api/vector_search.py` |

All are code constants. None are environment variables.

---

## 9. Key Architecture Decisions

Full rationale in `C2_MASTER_PLAN.md §1`. These are the facts that directly affect how you write code:

**Authorization**
- Enforced at API layer via `project_members` table. Not BigQuery RLS.
- `GLOBAL_STANDARDS` is open to all authenticated users. `user_has_project_access` must special-case this project_id and return `True` without querying `project_members`.
- Auth cache: `cachetools.TTLCache(maxsize=1000, ttl=300)`. Never `functools.lru_cache` (no TTL support).

**Vector search**
- Runs in `c2-api` Python only. Not via MCP Toolbox.
- Embedding is inlined as a float array literal in the SQL string.
- `top_k` values are inlined as integer literals. BigQuery TVF arguments do not reliably accept named parameters.

**Audit log**
- Written via direct BigQuery DML INSERT from `api/audit.py`. Not via MCP Toolbox HTTP call.
- `write_audit_log` in tools.yaml exists for admin/verification only.
- Audit write is in a `finally` block in the SSE generator to survive client disconnection.

**PDF ingestion**
- Digital: PyMuPDF, stays in GCC, `GCC_NATIVE`.
- Scanned: Document AI EU endpoint, `EXTERNAL_OCR`.
- Frontend shows an acknowledgment banner on every upload. Detection is server-side only.

**Claude SDK**
- `anthropic[vertex]` package. `AnthropicVertex(project_id="c2-intelligence", region=VERTEX_REGION)` in `api/claude_client.py`.
- Model ID injected via `--set-secrets CLAUDE_MODEL_ID=CLAUDE_MODEL_ID:latest` at Cloud Run deploy time.

**Clause chunking**
- `CLAUSE_PATTERN = re.compile(r'^(?:(?:Sub-)?[Cc]lause\s+)?(\d+[\d\.]*)\s+', re.IGNORECASE)`
- Matches `8.4.1 Force Majeure` and `Sub-Clause 8.4 Engineer` formats.

**Sessions**
- State in BigQuery. Create and update use DML (not streaming insert).
- 1-5 second update latency per turn is accepted in v1.0.

**IVF index**
- Created after Task 3.4. If creation fails (insufficient rows), log and proceed. BigQuery uses brute force automatically at query time.

**Multi-domain queries**
- Router returns a list of matched domains. Execution uses `domains[0]` as the primary agent.
- Audit log records all matched domains as a comma-separated string.
- Full multi-domain routing is v1.1.

---

## 10. Active Plan File

All phases, tasks, SQL, shell commands, Python, prompts, Dockerfiles, and requirements are in:

```
C2_MASTER_PLAN.md
```

Read the relevant section before executing any task.

---

## 11. Deploy Order (Mandatory)

| Step | Phase | Hard Dependency |
|---|---|---|
| 1 | Phase 0 — infra, IAM, buckets, Artifact Registry, secrets | None |
| 2 | Phase 0 (manual) — Firebase setup | None (console only) |
| 3 | Phase 1 — BigQuery schema + GLOBAL_STANDARDS record | Phase 0 complete |
| 4 | Phase 2 — Toolbox build, deploy, OAuth, verify (Task 2.5 gate) | Phase 1 complete |
| 5 | Phase 3 — Ingestion deploy, Document AI, test, index, L2b | Phase 2 gate passed |
| 6 | Phase 4 — c2-api deploy | Phase 3 complete; INGESTION_URL + TOOLBOX_URL + CLAUDE_MODEL_ID known |
| 7 | Phase 5 — Frontend build + Vercel deploy | Phase 4 complete; API_URL known |
| 8 | Phase 6 — Model Armor, cost controls, billing alert | Phase 5 complete |

---

## 12. Current Build State

```
Last completed task : Task 0.1 (partial) — region decision locked, model ID pending Task 0.2
Last commit         : task-0.1
Next task           : Task 0.2 — Create GCP project and enable APIs
Verification status : pending (MCP Toolbox not yet deployed)
```

*Update after every verified task.*

---

## 13. Build Log

Append-only. One entry per task. **Claude Code never writes PASS.**

| Date | Task | Commit | Status |
|---|---|---|---|
| — | Scaffold — all files created, no GCP resources | (initial) | PASS (no verification needed) |
| 2026-04-09 | Task 0.1 — Lock region decision (SPLIT_REGIONS=YES), model ID deferred to post-0.2 | task-0.1 | partial — awaiting model ID |

---

## 14. Out of Scope — v1.1 Only

- Automated report generation
- Multi-project comparison
- Mobile-optimised UI
- CMEK / customer-managed encryption keys
- Session-aware retrieval / query expansion
- Multi-domain simultaneous routing
- Session state migration to Firestore
