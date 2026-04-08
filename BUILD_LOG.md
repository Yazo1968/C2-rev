# C2 Intelligence — Build Log

Append-only log. One entry per task. **Claude Code never writes PASS** —
that's Claude Chat's job after independent verification via MCP Toolbox or
gcloud output.

Format:
```
## YYYY-MM-DD HH:MM  Task X.Y — short title
- commit: <hash>
- artefacts: file paths produced
- verification: pending | PASS (Claude Chat) | FAIL (reason)
```

---

## Initial scaffold (pre-Phase 0)

This repo started as the v2 build plan only. The first scaffold commit
materialises every file the plan calls for, in the directory layout from
`/root/.claude/plans/breezy-tumbling-lecun.md`. Nothing in this commit
touches GCP — all subsequent tasks are gated on operator-driven `gcloud`
runs and Claude Chat verification.

### Naming corrections applied during scaffold

The source plan (`C2_BUILD_PLAN_v2.md`) used `C2-intelligence` for the GCP
project ID and `C2_warehouse` for the BigQuery dataset. GCP project IDs,
service account IDs, Cloud Run service names, and Cloud Storage bucket
names must be lowercase. Normalised throughout the scaffold to:

- project: `c2-intelligence`
- dataset: `c2_warehouse`
- service accounts: `c2-api`, `c2-ingestion`, `c2-toolbox`
- Cloud Run services: `c2-api`, `c2-ingestion`, `c2-toolbox`
- buckets: `c2-documents-l1`, `c2-documents-l2a`, `c2-documents-l2b`
  (globally unique — `infra/04_buckets.sh` accepts `BUCKET_PREFIX`)

### Files scaffolded

```
CLAUDE.md
infra/00_verify_region.sh
infra/01_project_and_apis.sh
infra/02_service_accounts.sh
infra/03_iam.sh
infra/04_buckets.sh
infra/06_model_armor.sh
infra/sql/01_dataset.sql
infra/sql/02_projects.sql
infra/sql/03_project_members.sql
infra/sql/04_documents.sql
infra/sql/05_chunks.sql
infra/sql/06_ingestion_runs.sql
infra/sql/07_audit_log.sql
infra/sql/08_query_sessions.sql
infra/sql/09_vector_index.sql        # do NOT run until after Task 3.4
infra/sql/10_cost_controls.sql       # Task 6.3
toolbox/tools.yaml
toolbox/Dockerfile
toolbox/deploy.sh
ingestion/pipeline.py
ingestion/clause_chunker.py
ingestion/main.py
ingestion/requirements.txt
ingestion/Dockerfile
ingestion/deploy.sh
api/auth.py
api/config.py
api/embeddings.py
api/vector_search.py
api/routing.py
api/prompts.py
api/sessions.py
api/claude_client.py
api/audit.py
api/main.py
api/requirements.txt
api/Dockerfile
api/deploy.sh
frontend/package.json
frontend/vite.config.ts
frontend/tsconfig.json
frontend/tsconfig.node.json
frontend/index.html
frontend/.env.example
frontend/vercel.json
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/lib/firebase.ts
frontend/src/lib/auth.tsx
frontend/src/lib/api.ts
frontend/src/pages/Login.tsx
frontend/src/pages/Projects.tsx
frontend/src/pages/Upload.tsx
frontend/src/pages/Query.tsx
frontend/src/pages/Audit.tsx
BUILD_LOG.md
C2_MASTER_PLAN.md
```

### What still needs the operator

These cannot run from CI / sandboxes — they require `gcloud` auth, billing,
the FIDIC/SCL/AACE PDFs, and (for Phase 5.6) a Vercel account:

1. **Task 0.1** — `infra/00_verify_region.sh`. Record `REGION_VERTEX_AI` in `CLAUDE.md`.
2. **Task 0.1** — read the exact Claude model id off Vertex AI model garden, store in Secret Manager.
3. **Tasks 0.2–0.5** — run `infra/01..04`.
4. **Phase 1** — execute `infra/sql/01..08` against BigQuery (in order).
5. **Phase 2** — `toolbox/deploy.sh`, then OAuth client, then Claude.ai connector (Task 2.4), then verification gate Task 2.5.
6. **Phase 3** — `ingestion/deploy.sh`, Document AI processor (Task 3.2), Task 3.4 round-trip, then `infra/sql/09_vector_index.sql`, then Task 3.6 standards ingestion.
7. **Phase 4** — `api/deploy.sh` with `CLAUDE_MODEL_ID`, `TOOLBOX_URL`, `INGESTION_URL`.
8. **Phase 5** — `cd frontend && npm install && npm run dev`, then Vercel deploy, then lock CORS on c2-api.
9. **Phase 6** — `infra/06_model_armor.sh`, `infra/sql/10_cost_controls.sql`, billing alert in console.

---

## (next entry — Task 0.1)
```
- commit:
- artefacts:
- verification: pending
```
