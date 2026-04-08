# C2 Intelligence — Master Plan (Architecture Decisions and Rationale)

This document records the **why** behind every load-bearing decision in the
build, so that anyone joining later (or revisiting in six months) can
understand the constraints we were optimising against rather than just the
shape of the system. The implementation steps live in `C2_BUILD_PLAN_v2.md`
and `/root/.claude/plans/breezy-tumbling-lecun.md`.

## 1. Region strategy — me-central1 with europe-west4 fallback

The customer's data sovereignty constraint is GCC residency. Our hard
preference is `me-central1` for everything. The known risk at planning time
is that **Vertex AI (and Claude on Vertex AI) may not be available in
`me-central1`**. Task 0.1 (`infra/00_verify_region.sh`) is the first thing
that runs in any build session, exactly because every other resource depends
on the answer.

- If Vertex AI **is** available in `me-central1`: single-region deployment.
- If Vertex AI **is not** available in `me-central1`: BigQuery, Cloud
  Storage, and Cloud Run stay in `me-central1`; Vertex AI runs in
  `europe-west4`. The cross-region hop is documented here once known, and
  the user-facing UI surfaces the EU OCR banner for any document sent to
  Document AI (separate concern, see §4).

The Claude model id is **always pinned** (e.g. `claude-sonnet-4-5@20251015`)
and stored in Secret Manager. `api/config.py` raises at import time if it
sees `@latest`. Reason: silent model upgrades have produced regressions in
grounded-citation quality in past projects, and we cannot reproduce a
production failure if we can't pin the model.

## 2. RLS removed — authorization at the API layer

We initially planned to use BigQuery row-level security on
`project_members`. This does not work: BigQuery's `SESSION_USER()` returns
the **service account** the API runs as, not the Firebase UID of the human
who issued the request. RLS based on session user would either deny
everything or grant everything. There is no per-request impersonation
pattern that makes RLS work with a Firebase-fronted API.

Decision: enforce authorization in `api/auth.py` (`user_has_project_access`,
LRU-cached for 5 minutes) against the `project_members` table read directly
through the API service account. Every endpoint calls
`require_project_access(user, project_id)` before touching data. The
`GLOBAL_STANDARDS` project (L2B reference layer) is explicitly open to all
authenticated users.

## 3. Vector search lives in c2-api Python, not in MCP Toolbox

MCP Toolbox is the right place for parameterised SQL document retrieval.
It is the **wrong** place for `VECTOR_SEARCH()` — `tools.yaml` cannot
parameterise an `ARRAY<FLOAT64>` literal, which is exactly what
`VECTOR_SEARCH()` needs as the query embedding.

Decision: `api/vector_search.py` builds the SQL string with the embedding
inlined as a literal (validated to 768 dims first, no injection vector
because we're working with floats produced by Vertex AI), and passes the
remaining parameters (`project_id`, `layer_filter`, `top_k`) as scalar
query parameters. MCP Toolbox keeps document/project listings and the
audit log writes — both genuinely parameterisable — and serves as the
verification backbone for Claude Chat.

## 4. Two-path PDF ingestion

Document AI is not available in any GCC region. The two paths:

| Path | When | Where | Flag |
|---|---|---|---|
| GCC_NATIVE | Detected as digital PDF (PyMuPDF extracts ≥50 chars on first page) | PyMuPDF in `c2-ingestion`, never leaves GCC | `processing_method = 'GCC_NATIVE'` |
| EXTERNAL_OCR | Detected as scanned | Document AI `eu-documentai.googleapis.com` | `processing_method = 'EXTERNAL_OCR'` |

The UI surfaces a banner before any scanned-PDF upload (`frontend/src/pages/Upload.tsx`).
The user has acknowledged that scanned-document content will leave GCC for
text extraction; the audit trail makes this verifiable per document via the
`processing_method` column.

## 5. Embedding model and dimensions are locked

`text-embedding-004` at 768 dimensions. Locked in `ingestion/pipeline.py`
and `api/embeddings.py` as constants, not env vars. Both files assert
`len(embedding) == 768` on every call. The vector index in
`infra/sql/09_vector_index.sql` is dimensioned to match. A silent dimension
drift would only manifest at query time as garbage retrieval, so we fail
loudly at the producer instead.

## 6. Single c2-api service (not c2-agents + c2-api)

Splitting the agent from the HTTP layer added service-to-service auth
overhead, an extra deploy target, an extra cold-start path, and no
encapsulation benefit (the agent is called only by the API). Collapsed
into one Cloud Run service. The agent logic is just Python modules
(`routing.py`, `prompts.py`, `vector_search.py`, `claude_client.py`)
imported by `main.py`.

## 7. Clause-aware chunking for CONTRACT documents

FIDIC contracts and equivalent bespoke conditions are structured by clause
number (e.g. "8.4.1 Notice of Force Majeure"). Naive page-based or
sliding-window chunking destroys this structure and makes citations
imprecise. `ingestion/clause_chunker.py:chunk_contract_pages` detects
clause headers via `CLAUSE_PATTERN`, flushes the buffer at every clause
boundary, and stamps `section_ref` with the current clause number on every
chunk. Non-contract documents fall back to paragraph-aware chunking with
no `section_ref`.

The grounding rules in `api/prompts.py` require citations as
`[Document Name, Page X, Clause Y]`. Without `section_ref`, the legal
agent cannot satisfy that contract — so chunking and prompting are tightly
coupled by design.

## 8. SSE streaming, not request/response

Claude responses for grounded analysis routinely run 15–40 seconds. A
synchronous request/response shape produces a UX that looks broken. We
stream via `sse-starlette` from `api/main.py:query` and consume on the
client with `@microsoft/fetch-event-source` (chosen over native
`EventSource` because the latter cannot send an Authorization header).

The stream emits three event types:
- `meta`: session id, domain badge, citations (rendered immediately)
- `token`: a text delta (appended live)
- `done`: latency metrics (triggers audit write on the server)

## 9. Multi-turn sessions

`query_sessions` table holds last-10-turn context, 4-hour expiry.
`api/sessions.py` trims on every update. Context is opt-in: a query without
a `session_id` starts a fresh session; a query with one re-injects history
into the Claude messages list.

## 10. Verification discipline — Claude Chat is the second pair of eyes

This is the part that's easy to discard under deadline pressure and very
costly later. Every task is verified by Claude Chat **independently**
querying BigQuery via the MCP Toolbox connector before PASS is recorded
in `BUILD_LOG.md`. Claude Code does not self-report. The reason is that
silent successes ("the script ran with no error") are the most common
failure mode in build pipelines that touch many separate Google services
— each service can be in a half-configured state that the immediate caller
cannot see. Independent verification catches that.

The deferred features in v1.1 (report generation, multi-project comparison,
mobile UI, CMEK) were excluded from v1.0 specifically to keep the
verification surface small enough to walk through end to end.

## 11. Out of scope — explicitly

These were considered and **not** built in v1.0:

- **Automated report generation.** No agreed template at planning time;
  building speculative formatting is wasted work.
- **Multi-project comparison.** Cross-project authorization model is
  non-trivial and the use case has no committed customer.
- **Mobile-optimised UI.** Desktop is the primary surface for legal /
  commercial review; mobile is an enhancement, not a foundation.
- **CMEK / customer-managed encryption.** Default GCP encryption is
  acceptable for v1.0; CMEK is a v1.1 conversation when the customer is
  ready to manage their own keys.
