# C2 Intelligence — Master Plan
# Complete technical blueprint. All phases, tasks, code, SQL, config.
# For execution rules, roles, build state, and build log → CLAUDE.md
# Revised: April 2026 | Clean Slate v2.0 | All conflicts, gaps, and assumptions resolved

---

## 1. Architecture Decisions and Rationale

### 1.1 Region Strategy — me-central1 with europe-west4 Fallback

The customer's data sovereignty constraint is GCC residency. Hard preference is `me-central1` for everything. Claude on Vertex AI is not available in `me-central1` as of the planning date. The expected outcome of Task 0.1 is `SPLIT_REGIONS=YES`: BigQuery, Cloud Storage, Cloud Run, and Artifact Registry in `me-central1`; Vertex AI in `europe-west4`.

The cross-region hop (Cloud Run in me-central1 calling Vertex AI in europe-west4) adds ~50–100ms latency per embedding call. For a 15–40 second Claude response, this is acceptable.

### 1.2 RLS Removed — Authorization at the API Layer

BigQuery `SESSION_USER()` returns the service account the API runs as, not the Firebase UID. RLS would grant access to all authenticated requests or none. Decision: `api/auth.py` enforces access via `project_members` table, using `cachetools.TTLCache(maxsize=1000, ttl=300)` — not `functools.lru_cache`, which has no TTL and would allow revoked access to persist indefinitely.

`GLOBAL_STANDARDS` is special-cased: `user_has_project_access` returns `True` for this project_id without querying `project_members`.

### 1.3 Vector Search in c2-api Python, Not MCP Toolbox

`tools.yaml` cannot parameterise an `ARRAY<FLOAT64>` literal. Additionally, `top_k` inside a VECTOR_SEARCH TVF argument is not reliably resolvable as a BigQuery named parameter. Both the embedding and `top_k` are inlined as literals in the SQL string. Remaining parameters (`project_id`, `layer_filter`) are passed as scalar query parameters.

### 1.4 Audit Log Written via Direct BigQuery DML, Not MCP Toolbox

genai-toolbox BigQuery sources are optimised for SELECT. DML INSERT support is not guaranteed across versions. More critically, calling MCP Toolbox over HTTP from `c2-api` requires `roles/run.invoker` on the toolbox service, adds a network hop, and creates a coupling between two Cloud Run services for a simple write. Decision: `api/audit.py` inserts directly via the BigQuery Python client. The Toolbox `write_audit_log` tool remains for admin and Claude Chat verification use only.

Audit writes are placed in a `finally` block in the SSE generator to guarantee execution even when the client disconnects mid-stream.

### 1.5 Two-Path PDF Ingestion

Document AI is not available in any GCC region.

| Path | Trigger | Processor | Flag |
|---|---|---|---|
| GCC_NATIVE | PyMuPDF extracts ≥50 chars from first page | PyMuPDF in c2-ingestion, never leaves GCC | `processing_method = 'GCC_NATIVE'` |
| EXTERNAL_OCR | Fewer than 50 chars extracted | Document AI `eu-documentai.googleapis.com` | `processing_method = 'EXTERNAL_OCR'` |

The frontend shows an acknowledgment banner on every upload. Detection is server-side. The banner text: "If this document is a scanned PDF, its content will be sent to an EU OCR processor for text extraction. This is the only way to process scanned documents. Tap Acknowledge to proceed."

### 1.6 Single c2-api Service

Splitting the agent from the HTTP layer adds service-to-service auth overhead, cold-start paths, and deployment complexity with no encapsulation benefit. Collapsed into one Cloud Run service.

### 1.7 Clause-Aware Chunking

FIDIC contracts use clause numbers (e.g. `8.4.1`, `Sub-Clause 8.4`). Naive chunking destroys this structure. `CLAUSE_PATTERN` detects both formats. `section_ref` is stamped on every chunk. The grounding prompt requires `[Document Name, Page X, Clause Y]` citations — `section_ref` is what makes this possible.

For non-CONTRACT documents, `section_ref` is null. The grounding prompt must conditionally format citations as `[Document Name, Page X]` when `section_ref` is absent.

### 1.8 SSE Streaming

Claude responses run 15–40 seconds. `sse-starlette` on the server; `@microsoft/fetch-event-source` on the client (native `EventSource` cannot send an Authorization header). Three event types: `meta` (session id, domain, citations), `token` (text delta), `done` (latency metrics).

### 1.9 BigQuery for Session State — Accepted Tradeoff

BigQuery DML UPDATE takes 1–5 seconds. Every multi-turn query incurs this latency after the first turn. This is accepted in v1.0. Session create uses DML INSERT (not streaming insert) to avoid the buffering delay of the streaming API. Migration to Firestore is deferred to v1.1.

### 1.10 Tiktoken as Token Counter — Known Approximation

Claude uses Anthropic's internal tokenizer. `tiktoken cl100k_base` (OpenAI) is used for chunk sizing. Counts will be close but not exact. For the purpose of preventing oversized chunks this is acceptable. The min/max token limits include a safety margin.

### 1.11 Verification Discipline

Every task is verified by Claude Chat independently querying BigQuery via MCP Toolbox before PASS is recorded. Claude Code does not self-report. Silent successes are the most common failure mode in multi-service builds.

---

## 2. What Changed from v1.0

| Change | Reason |
|---|---|
| Vector search moved to Python agent | VECTOR_SEARCH SQL cannot be parameterised with ARRAY via tools.yaml |
| BigQuery RLS removed | SESSION_USER() returns service account, not Firebase UID |
| Two-path PDF ingestion | Document AI not available in me-central1 |
| c2-agents + c2-api collapsed | Unnecessary complexity |
| tools.yaml YAML structure corrected | Original had wrong key/name syntax |
| Report generation deferred to v1.1 | Undefined implementation at planning time |
| SSE streaming added | 15–40 second responses require streaming |
| Clause-aware chunking added | FIDIC contracts have structured clause numbering |
| Vector index creation after Task 3.4 | Cannot create IVF index on empty table |
| L2b standards ingestion added as Task 3.6 | Platform unusable without FIDIC/SCL/AACE reference layer |
| Embedding dimensions locked at 768 | Prevents silent failures from model mismatch |
| Vertex AI region check added as first task | me-central1 availability unverified |
| OAuth for MCP Toolbox made explicit | Required for Claude Chat verification |
| Session management added | Multi-turn context was stated but never implemented |
| lru_cache replaced with cachetools.TTLCache | lru_cache has no TTL — revoked access would persist |
| Audit log moved to direct BigQuery DML | Toolbox DML support unverified; avoids service-to-service coupling |
| GLOBAL_STANDARDS special-cased in auth | Was described as open to all but not implemented |
| top_k inlined as SQL literal | BigQuery TVF named parameters unreliable |
| Artifact Registry tasks added | Container images need a registry before deployment |
| Secret Manager init tasks added | Secrets must be created before they can be populated |
| IAM bindings for service invocation added | c2-api → c2-ingestion and c2-api → c2-toolbox were missing |
| CORS on buckets added | Required for signed URL uploads from the browser |
| Firebase setup documented as explicit task | Was a checklist item with no implementation guidance |
| GLOBAL_STANDARDS project record insertion added | L2b chunks JOIN to projects table — record must exist |
| requirements.txt files defined | Were scaffolded but empty |
| Dockerfiles defined | Were scaffolded but empty |
| Scanned PDF UI approach clarified | Detection is server-side; frontend shows banner always |
| CLAUSE_PATTERN updated | Original regex missed Sub-Clause prefix format |
| Embedding batch size increased to 25 | Batches of 5 were 50x slower than necessary |
| IVF index error handling clarified | Index creation fails on sparse data — log and proceed |
| Session purge mechanism added | Sessions table grows unboundedly without cleanup |

---

## 3. Platform Stack (Locked)

| Component | Technology | Notes |
|---|---|---|
| Data warehouse | BigQuery | me-central1 |
| Document storage | Cloud Storage | 3 buckets: L1, L2a, L2b |
| Container registry | Artifact Registry | me-central1, repo: c2-images |
| PDF — digital | PyMuPDF | GCC-native, no external API |
| PDF — scanned | Document AI (eu endpoint) | EXTERNAL_OCR; user acknowledged |
| Embeddings | Vertex AI text-embedding-004 | 768 dims, locked; region from §6 |
| Vector search | BigQuery Python client, VECTOR_SEARCH() | api layer only |
| MCP retrieval | MCP Toolbox (genai-toolbox) on Cloud Run | Document lookup, project listing, admin |
| Agent model | Claude on Vertex AI via anthropic[vertex] | Model string locked in Phase 0 |
| API + Agent | Single FastAPI on Cloud Run | c2-api |
| Streaming | SSE via sse-starlette | Cloud Run + fetch-event-source |
| Frontend | React + TypeScript + Vite | Deployed to Vercel |
| Auth | Firebase Auth (Google Sign-In) | JWT validated at API layer |
| Secrets | Secret Manager | All credentials |
| Audit | BigQuery audit_log | Direct DML INSERT from api/audit.py |
| Session state | BigQuery query_sessions | DML INSERT/UPDATE; 1-5s latency accepted |
| Cost control | BigQuery max_bytes_billed (calibrated post-launch) | Set in Phase 6 |

---

## 4. Scope Boundary — v1.0 vs v1.1

| Feature | v1.0 | v1.1 |
|---|---|---|
| Interactive Q&A with citations | ✓ | |
| SSE streaming responses | ✓ | |
| Document upload and ingestion | ✓ | |
| Four domain agents (Legal, Commercial, Financial, Technical) | ✓ | |
| Audit trail | ✓ | |
| L2b standards reference layer | ✓ | |
| Multi-turn sessions | ✓ | |
| Automated report generation | | ✓ |
| Multi-project comparison | | ✓ |
| Mobile-optimised UI | | ✓ |
| CMEK / customer-managed encryption | | ✓ |
| Session-aware retrieval / query expansion | | ✓ |
| Multi-domain simultaneous routing | | ✓ |
| Session state in Firestore | | ✓ |

---

## 5. Pre-Build Checklist

- GCP account active with billing enabled
- `gcloud` CLI installed and authenticated on Yasser's machine
- Claude Code installed
- MCP Toolbox binary available locally for tools.yaml testing (production runs on Cloud Run)
- Firebase project created in console (see Task 0.8)
- Vercel account connected to GitHub
- FIDIC Red Book 1999 PDF
- FIDIC Red Book 2017 PDF
- FIDIC Yellow Book 2017 PDF
- FIDIC Silver Book 2017 PDF
- SCL Protocol 2nd Edition 2017 PDF
- AACE RP 29R-03 PDF
- Task 0.1 completed before any other task begins

---

## Phase 0 — GCP Foundation

### Task 0.1 — Verify GCP Service Availability and Lock Region

**This task must complete before any resource is created.**

`infra/00_verify_region.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
TARGET_REGION="me-central1"

echo "=== Checking BigQuery in ${TARGET_REGION} ==="
gcloud services list --enabled --project=${PROJECT} --filter="name:bigquery.googleapis.com"

echo "=== Checking Vertex AI platform in ${TARGET_REGION} ==="
gcloud ai models list --region=${TARGET_REGION} --project=${PROJECT} 2>&1 | head -5 || \
  echo "WARN: Vertex AI may not be available in ${TARGET_REGION}"

echo "=== Checking Claude on Vertex AI ==="
gcloud ai models list --region=${TARGET_REGION} --project=${PROJECT} \
  --filter="displayName:claude" 2>&1 | head -10 || \
  echo "WARN: Claude not found in ${TARGET_REGION} — try europe-west4"

echo "=== Checking Cloud Run in ${TARGET_REGION} ==="
gcloud run regions list | grep ${TARGET_REGION}

echo ""
echo "ACTION REQUIRED: Record results in CLAUDE.md §6 before proceeding."
echo "Expected: SPLIT_REGIONS=YES (Vertex AI in europe-west4)"
```

**Decision gate:**
- `SPLIT_REGIONS=NO` → all resources in `me-central1`
- `SPLIT_REGIONS=YES` → BigQuery + Cloud Storage + Cloud Run + Artifact Registry in `me-central1`; Vertex AI in `europe-west4`

Read the exact Claude model ID from the Vertex AI Model Garden. Store in Secret Manager (Task 0.7). Record in CLAUDE.md §7. **Never `@latest`.**

**Verification:** Claude Chat confirms region decision and model ID are recorded in CLAUDE.md before Phase 0 continues.

---

### Task 0.2 — Create GCP Project and Enable APIs

`infra/01_project_and_apis.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"

gcloud projects create ${PROJECT} --name="C2 Intelligence" || \
  echo "Project may already exist, continuing..."
gcloud config set project ${PROJECT}

gcloud services enable \
  bigquery.googleapis.com \
  bigquerystorage.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  firebase.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  modelarmor.googleapis.com

echo "APIs enabled."
```

Note: `cloudbuild.googleapis.com` is required for `gcloud run deploy --source .`. `artifactregistry.googleapis.com` is required for container images.

---

### Task 0.3 — Create Service Accounts

`infra/02_service_accounts.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"

gcloud iam service-accounts create c2-api \
  --display-name="C2 API and Agent layer" \
  --project=${PROJECT}

gcloud iam service-accounts create c2-ingestion \
  --display-name="C2 Document Ingestion" \
  --project=${PROJECT}

gcloud iam service-accounts create c2-toolbox \
  --display-name="C2 MCP Toolbox" \
  --project=${PROJECT}

echo "Service accounts created."
```

---

### Task 0.4 — Grant IAM Roles

`infra/03_iam.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"

# ── c2-api ──────────────────────────────────────────────────────────────
# BigQuery read (for project_members auth checks and vector search)
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
# Vertex AI (embeddings + Claude)
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
# Secret Manager
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# Cloud Storage (signed URL generation)
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
# Invoke c2-ingestion Cloud Run
gcloud run services add-iam-policy-binding c2-ingestion \
  --region=me-central1 \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/run.invoker" || \
  echo "WARN: c2-ingestion not yet deployed — rerun this binding after Task 3.3"
# Invoke c2-toolbox Cloud Run (for admin calls if needed)
gcloud run services add-iam-policy-binding c2-toolbox \
  --region=me-central1 \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/run.invoker" || \
  echo "WARN: c2-toolbox not yet deployed — rerun this binding after Task 2.3"
# Service Account Token Creator (for signed URL generation)
gcloud iam service-accounts add-iam-policy-binding \
  c2-api@${PROJECT}.iam.gserviceaccount.com \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
# Firebase Auth verification
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/firebase.sdkAdminServiceAgent" || \
  echo "INFO: Firebase SA role may need to be set via Firebase console"

# ── c2-ingestion ─────────────────────────────────────────────────────────
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"
# Secret Manager (Document AI processor ID, etc.)
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# ── c2-toolbox ───────────────────────────────────────────────────────────
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-toolbox@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:c2-toolbox@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

echo "IAM bindings applied."
echo "NOTE: Run the c2-ingestion and c2-toolbox run.invoker bindings again"
echo "      after those services are deployed (Tasks 2.3 and 3.3)."
```

---

### Task 0.5 — Create Cloud Storage Buckets

`infra/04_buckets.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
REGION="me-central1"
PREFIX="${1:-c2}"  # Pass a custom prefix if default names are taken

L1_BUCKET="${PREFIX}-documents-l1"
L2A_BUCKET="${PREFIX}-documents-l2a"
L2B_BUCKET="${PREFIX}-documents-l2b"

for BUCKET in ${L1_BUCKET} ${L2A_BUCKET} ${L2B_BUCKET}; do
  gcloud storage buckets create gs://${BUCKET} \
    --location=${REGION} \
    --uniform-bucket-level-access \
    --project=${PROJECT}
  echo "Created: gs://${BUCKET}"
done

# CORS configuration for signed URL uploads from the browser
cat > /tmp/cors.json << 'EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "PUT", "POST", "DELETE", "HEAD"],
    "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
    "maxAgeSeconds": 3600
  }
]
EOF

for BUCKET in ${L1_BUCKET} ${L2A_BUCKET} ${L2B_BUCKET}; do
  gcloud storage buckets update gs://${BUCKET} --cors-file=/tmp/cors.json
  echo "CORS applied to: gs://${BUCKET}"
done

echo ""
echo "ACTION: If bucket names differ from defaults, update CLAUDE.md §5."
```

---

### Task 0.6 — Create Artifact Registry Repository

`infra/05_artifact_registry.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
REGION="me-central1"

gcloud artifacts repositories create c2-images \
  --repository-format=docker \
  --location=${REGION} \
  --project=${PROJECT} \
  --description="C2 Intelligence container images"

# Configure Docker to authenticate with Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

echo "Artifact Registry repository created: ${REGION}-docker.pkg.dev/${PROJECT}/c2-images"
echo "Use this base path for all image references."
```

All Docker image references use: `me-central1-docker.pkg.dev/c2-intelligence/c2-images/<service>:latest`

---

### Task 0.7 — Create Secret Manager Secrets

`infra/06_secrets.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"

# Create secret placeholders — values are populated in subsequent tasks
SECRETS=(
  "CLAUDE_MODEL_ID"
  "DOCUMENT_AI_PROCESSOR_ID"
  "FIREBASE_SERVICE_ACCOUNT"
  "OAUTH_CLIENT_ID"
  "OAUTH_CLIENT_SECRET"
)

for SECRET in "${SECRETS[@]}"; do
  gcloud secrets create ${SECRET} \
    --replication-policy="automatic" \
    --project=${PROJECT} || \
    echo "Secret ${SECRET} may already exist, continuing..."
  echo "Created secret: ${SECRET}"
done

echo ""
echo "ACTION: Populate each secret after the relevant task:"
echo "  CLAUDE_MODEL_ID          → Task 0.1 (Vertex AI Model Garden)"
echo "  DOCUMENT_AI_PROCESSOR_ID → Task 3.2 (Document AI console)"
echo "  FIREBASE_SERVICE_ACCOUNT → Task 0.8 (Firebase console)"
echo "  OAUTH_CLIENT_ID          → Task 2.4 (GCP OAuth consent screen)"
echo "  OAUTH_CLIENT_SECRET      → Task 2.4 (GCP OAuth consent screen)"
```

To populate a secret after its value is known:
```bash
echo -n "VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
```

---

### Task 0.8 — Firebase Project Setup (Manual — Console Only)

This task cannot be automated. Yasser executes these steps in the Firebase and GCP consoles:

1. Go to [Firebase Console](https://console.firebase.google.com) → Add project → select `c2-intelligence` (link to existing GCP project)
2. Enable Authentication → Sign-in method → Google → Enable
3. Project Settings → Service accounts → Generate new private key → download JSON
4. Store the JSON in Secret Manager: `gcloud secrets versions add FIREBASE_SERVICE_ACCOUNT --data-file=<downloaded-key.json>`
5. Project Settings → General → Your apps → Add app → Web → register app named `c2-intelligence-web`
6. Copy the Firebase config object. It contains: `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`
7. Record these values — they are needed for Phase 5 frontend environment variables. They are public-safe (not secrets).

**Verification:** Yasser confirms the service account key is in Secret Manager and the web app config values are recorded.

---

### Task 0.9 — Insert GLOBAL_STANDARDS Project Record

Run this SQL in BigQuery after Phase 1 tables are created (after Task 1.2):

```sql
INSERT INTO `c2-intelligence.c2_warehouse.projects`
  (project_id, project_name, client_name, contract_type, jurisdiction, currency, created_by, is_active)
VALUES
  ('GLOBAL_STANDARDS', 'Global Standards Reference Layer', 'C2 Intelligence',
   'STANDARD', 'GLOBAL', 'USD', 'system', TRUE);
```

This record must exist before Task 3.6. The vector search JOINs `chunks → documents → projects`. Without this row, L2b chunks return no results.

**Verification:** Claude Chat confirms the row exists in `c2_warehouse.projects`.

---

## Phase 1 — BigQuery Schema

### Task 1.1 — Create Dataset

```sql
CREATE SCHEMA IF NOT EXISTS `c2-intelligence.c2_warehouse`
OPTIONS (
  location = 'me-central1',
  description = 'C2 Intelligence document warehouse'
);
```

### Task 1.2 — Create Projects Table

```sql
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.projects` (
  project_id      STRING NOT NULL,
  project_name    STRING NOT NULL,
  client_name     STRING,
  contract_type   STRING,
  -- Valid values: FIDIC_RED_1999, FIDIC_RED_2017, FIDIC_YELLOW_2017,
  --               FIDIC_SILVER_2017, BESPOKE, STANDARD
  jurisdiction    STRING,
  -- Valid values: UAE, KSA, QAT, GLOBAL
  currency        STRING DEFAULT 'AED',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by      STRING,
  is_active       BOOL DEFAULT TRUE
);
```

After creating this table, run Task 0.9 to insert the GLOBAL_STANDARDS record.

### Task 1.3 — Create Project Members Table

```sql
-- Enforces authorization at the API layer (BigQuery RLS is not used).
-- (project_id, user_id) should be unique — duplicates are prevented at the API layer.
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.project_members` (
  project_id   STRING NOT NULL,
  user_id      STRING NOT NULL,
  user_email   STRING,
  role         STRING NOT NULL,
  -- Valid values: OWNER, ANALYST, VIEWER
  added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  added_by     STRING
);
```

### Task 1.4 — Create Documents Table

```sql
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.documents` (
  document_id          STRING NOT NULL,
  project_id           STRING NOT NULL,
  layer                STRING NOT NULL,
  -- Valid values: L1, L2A, L2B
  document_type        STRING,
  -- Valid values: CONTRACT, CORRESPONDENCE, PROGRAMME, POLICY, STANDARD, DRAWING
  file_name            STRING NOT NULL,
  gcs_uri              STRING NOT NULL,
  file_hash            STRING,
  -- SHA-256 of file content; used to detect duplicate uploads
  page_count           INT64,
  processing_method    STRING,
  -- Valid values: GCC_NATIVE, EXTERNAL_OCR
  ingested_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  ingestion_run_id     STRING,
  status               STRING DEFAULT 'ACTIVE'
  -- Valid values: ACTIVE, SUPERSEDED, DELETED
)
PARTITION BY DATE(ingested_at)
CLUSTER BY project_id, layer;
```

### Task 1.5 — Create Chunks Table

```sql
-- Vector index is created AFTER Task 3.4, not here.
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.chunks` (
  chunk_id        STRING NOT NULL,
  document_id     STRING NOT NULL,
  project_id      STRING NOT NULL,
  layer           STRING NOT NULL,
  chunk_index     INT64 NOT NULL,
  chunk_text      STRING NOT NULL,
  page_number     INT64,
  section_ref     STRING,
  -- For CONTRACT docs: clause number e.g. "20.1", "Sub-Clause 8.4"
  -- NULL for non-CONTRACT docs; citations use [Doc, Page X] format when NULL
  embedding       ARRAY<FLOAT64>,
  -- 768 dimensions, text-embedding-004. Both producer and consumer assert len == 768.
  token_count     INT64,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(created_at)
CLUSTER BY project_id, layer, document_id;
```

### Task 1.6 — Create Ingestion Runs Table

```sql
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.ingestion_runs` (
  run_id            STRING NOT NULL,
  project_id        STRING NOT NULL,
  document_id       STRING,
  gcs_uri           STRING,
  started_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  completed_at      TIMESTAMP,
  status            STRING,
  -- Valid values: RUNNING, COMPLETE, FAILED, PARTIAL_ROLLBACK
  chunks_created    INT64,
  processing_method STRING,
  error_message     STRING,
  retry_count       INT64 DEFAULT 0
);
```

### Task 1.7 — Create Audit Log Table

```sql
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.audit_log` (
  log_id           STRING NOT NULL,
  project_id       STRING NOT NULL,
  session_id       STRING,
  user_id          STRING,
  user_email       STRING,
  action           STRING NOT NULL,
  -- Valid values: QUERY, INGEST, LOGIN, EXPORT
  domains          STRING,
  -- Comma-separated list of matched domains e.g. "legal" or "legal,commercial"
  query_text       STRING,
  chunks_retrieved INT64,
  model_used       STRING,
  latency_ms       INT64,
  logged_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(logged_at)
CLUSTER BY project_id, action;
```

### Task 1.8 — Create Query Sessions Table

```sql
CREATE TABLE IF NOT EXISTS `c2-intelligence.c2_warehouse.query_sessions` (
  session_id      STRING NOT NULL,
  project_id      STRING NOT NULL,
  user_id         STRING NOT NULL,
  started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  last_active_at  TIMESTAMP,
  turn_count      INT64 DEFAULT 0,
  domains         STRING,
  expires_at      TIMESTAMP,
  -- started_at + 4 hours; rows with expires_at < CURRENT_TIMESTAMP() are stale
  context_json    STRING
  -- JSON array of last 10 turns. Each turn: {"role": "user"|"assistant", "content": "..."}
  -- Per-turn content is truncated to 2000 chars before storage to control size.
);
```

### Task 1.9 — Create Session Purge Scheduled Query

```sql
-- Create this as a BigQuery scheduled query running daily at 02:00 UTC
-- Name: c2-session-purge
-- Schedule: every 24 hours
DELETE FROM `c2-intelligence.c2_warehouse.query_sessions`
WHERE expires_at < CURRENT_TIMESTAMP()
  AND expires_at IS NOT NULL;
```

Set up via BigQuery console: Scheduled Queries → Create → paste above SQL → set schedule to "every 24 hours starting at 02:00".

**Verification:** Claude Chat queries `INFORMATION_SCHEMA.TABLES` via MCP Toolbox to confirm all 7 tables exist with correct schemas.

---

## Phase 2 — MCP Toolbox Setup

### Task 2.1 — Write tools.yaml

The correct format for genai-toolbox v0.32.0 is **multi-document YAML** with `---` separators.
Each source, tool, and toolset is a top-level document with its own `kind` field.

```yaml
kind: source
name: c2-bigquery
type: bigquery
project: c2-intelligence
location: me-central1
writeMode: blocked
# blocked = only SELECT statements permitted. All our tools are read-only.
maxQueryResultRows: 500
# Default is 50. 500 allows document listing tools to return full results.
---
kind: tool
name: list-project-documents
type: bigquery-sql
source: c2-bigquery
description: List all active documents for a project.
parameters:
  - name: project_id
    type: string
    description: The project ID
statement: |
  SELECT document_id, layer, document_type, file_name,
         page_count, processing_method, ingested_at
  FROM `c2-intelligence.c2_warehouse.documents`
  WHERE project_id = @project_id AND status = 'ACTIVE'
  ORDER BY layer, document_type, file_name
---
kind: tool
name: get-project-summary
type: bigquery-sql
source: c2-bigquery
description: Get document and chunk counts for a project by layer.
parameters:
  - name: project_id
    type: string
    description: The project ID
statement: |
  SELECT
    d.layer,
    COUNT(DISTINCT d.document_id) AS document_count,
    COUNT(c.chunk_id) AS chunk_count,
    SUM(d.page_count) AS total_pages
  FROM `c2-intelligence.c2_warehouse.documents` d
  LEFT JOIN `c2-intelligence.c2_warehouse.chunks` c
    ON d.document_id = c.document_id
  WHERE d.project_id = @project_id AND d.status = 'ACTIVE'
  GROUP BY d.layer
  ORDER BY d.layer
---
kind: tool
name: get-document-chunks
type: bigquery-sql
source: c2-bigquery
description: Retrieve the first 50 chunks for a document in order. Admin and verification use only.
parameters:
  - name: document_id
    type: string
    description: The document ID
statement: |
  SELECT chunk_index, chunk_text, page_number, section_ref, token_count
  FROM `c2-intelligence.c2_warehouse.chunks`
  WHERE document_id = @document_id
  ORDER BY chunk_index ASC
  LIMIT 50
---
kind: tool
name: get-user-projects
type: bigquery-sql
source: c2-bigquery
description: Get all active projects accessible to a user.
parameters:
  - name: user_id
    type: string
    description: Firebase user ID
statement: |
  SELECT p.project_id, p.project_name, p.client_name,
         p.contract_type, p.jurisdiction, pm.role
  FROM `c2-intelligence.c2_warehouse.project_members` pm
  JOIN `c2-intelligence.c2_warehouse.projects` p
    ON pm.project_id = p.project_id
  WHERE pm.user_id = @user_id AND p.is_active = TRUE
  ORDER BY p.project_name
---
kind: tool
name: list-all-projects
type: bigquery-sql
source: c2-bigquery
description: List all active projects. Admin and verification use only.
statement: |
  SELECT project_id, project_name, client_name, jurisdiction, created_at
  FROM `c2-intelligence.c2_warehouse.projects`
  WHERE is_active = TRUE
  ORDER BY created_at DESC
---
kind: tool
name: get-audit-log
type: bigquery-sql
source: c2-bigquery
description: Get the 100 most recent audit log entries for a project.
parameters:
  - name: project_id
    type: string
    description: The project ID
statement: |
  SELECT log_id, user_email, action, domains, query_text,
         chunks_retrieved, model_used, latency_ms, logged_at
  FROM `c2-intelligence.c2_warehouse.audit_log`
  WHERE project_id = @project_id
  ORDER BY logged_at DESC
  LIMIT 100
---
kind: toolset
name: c2-retrieval
tools:
  - list-project-documents
  - get-project-summary
  - get-document-chunks
  - get-user-projects
---
kind: toolset
name: c2-admin
tools:
  - list-all-projects
  - get-project-summary
  - list-project-documents
  - get-audit-log
---
kind: toolset
name: c2-all
tools:
  - list-project-documents
  - get-project-summary
  - get-document-chunks
  - get-user-projects
  - list-all-projects
  - get-audit-log
```

Notes:
- `write_audit_log` is not in tools.yaml. Audit writes go directly via BigQuery Python client in `api/audit.py`.
- `list-all-projects` has no `parameters` field — omit it entirely for tools with no parameters.
- `writeMode: blocked` enforces SELECT-only at the source level as a safety guard.
- Tool names use hyphens per toolbox convention.

---

### Task 2.2 — Run Toolbox Locally for Verification

**This is the verification backbone during the build. No Cloud Run deployment needed.**

The toolbox binary runs on Yasser's machine, points at BigQuery, and Claude Desktop connects to it for all verification tasks from Phase 1 onwards.

**Download the Windows binary (PowerShell):**
```powershell
$VERSION = "0.32.0"
curl.exe -o toolbox.exe "https://storage.googleapis.com/mcp-toolbox-for-databases/v$VERSION/windows/amd64/toolbox.exe"
```

**Run the toolbox locally** (from the repo root, after Phase 1 tables exist):
```powershell
.	oolbox.exe --config toolbox	ools.yaml
```

The toolbox listens on `http://127.0.0.1:5000`. Leave this terminal open during every build session that requires BigQuery verification.

**Connect Claude Desktop** — add the following to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "c2-toolbox": {
      "type": "http",
      "url": "http://127.0.0.1:5000/mcp"
    }
  }
}
```
Restart Claude Desktop after editing the config. Confirm the `c2-toolbox` connector appears in Claude Desktop's tools list.

**Verify the connection** — in Claude Desktop, ask:
> "Using the c2-toolbox MCP connector, call list-all-projects and show me the result."

Expected response: the GLOBAL_STANDARDS project row.

---

### Task 2.3 — Verification Gate

Claude Desktop calls `list-all-projects` (should return the GLOBAL_STANDARDS project) and `get-project-summary` with `project_id = GLOBAL_STANDARDS` (should return 0 documents until Task 3.6).

**This is the gate. No BigQuery task receives PASS until Claude Desktop can query BigQuery via the local toolbox.**

Claude Chat issues PASS after independently confirming both tool calls return expected results.

---

### Task 2.4 — Build and Push MCP Toolbox Docker Image (Production)

This task is required for production deployment only. It does not block verification or the ingestion/API build.
Run after Phase 3 is complete (see deploy order in CLAUDE.md §11).

`toolbox/Dockerfile`:
```dockerfile
FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.32.0
COPY tools.yaml /app/tools.yaml
CMD ["/toolbox", "--config", "/app/tools.yaml", "--address", "0.0.0.0", "--port", "8080"]
```

Notes:
- Version pinned to `0.32.0` (latest stable as of April 2026).
- `--tools-file` was removed in v0.31.0. The correct flag is `--config`.
- `--address 0.0.0.0` is required for Cloud Run — the default `127.0.0.1` makes the service unreachable.
- `--port 8080` matches the Cloud Run `--port 8080` deploy flag.
- The toolbox binary is at `/toolbox` in the base image (not `/app/toolbox`).

`toolbox/deploy.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
REGION="me-central1"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/c2-images/c2-toolbox:latest"

echo "Building toolbox image..."
docker build -t ${IMAGE} .

echo "Pushing to Artifact Registry..."
docker push ${IMAGE}

echo "Image ready: ${IMAGE}"
```

---

### Task 2.5 — Deploy MCP Toolbox to Cloud Run (Production)

Run after Phase 3 complete. See deploy order in CLAUDE.md §11.

```bash
PROJECT="c2-intelligence"
REGION="me-central1"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/c2-images/c2-toolbox:latest"

gcloud run deploy c2-toolbox \
  --image=${IMAGE} \
  --region=${REGION} \
  --service-account=c2-toolbox@${PROJECT}.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --min-instances=1 \
  --port=8080 \
  --project=${PROJECT}

TOOLBOX_URL=$(gcloud run services describe c2-toolbox \
  --region=${REGION} --format='value(status.url)')
echo "TOOLBOX_URL=${TOOLBOX_URL}"
echo "ACTION: Record TOOLBOX_URL — needed for Phase 4 Task 4.13"
```

After deploy, rerun the IAM binding from Task 0.4:
```bash
gcloud run services add-iam-policy-binding c2-toolbox \
  --region=me-central1 \
  --member="serviceAccount:c2-api@c2-intelligence.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Verification:** Claude Desktop calls `list-all-projects` via the Cloud Run URL to confirm the production toolbox is serving correctly.

---

## Phase 3 — Ingestion Pipeline

### Task 3.1 — Write Ingestion Service

`ingestion/requirements.txt`:
```
PyMuPDF==1.24.3
google-cloud-documentai==2.29.0
google-cloud-bigquery==3.25.0
google-cloud-storage==2.18.2
google-cloud-aiplatform==1.67.1
google-cloud-secret-manager==2.20.0
tiktoken==0.7.0
uuid==1.30
```

`ingestion/pipeline.py`:
```python
import fitz  # PyMuPDF
import hashlib
import re
import uuid
import os
from datetime import datetime, timezone
from typing import Optional

import tiktoken
from google.cloud import bigquery, documentai, storage, secretmanager
from google.cloud.aiplatform_v1 import PredictionServiceClient
from vertexai.language_models import TextEmbeddingModel
import vertexai

# ── Constants ────────────────────────────────────────────────────────────────
PROJECT_ID = "c2-intelligence"
VERTEX_REGION = os.environ.get("VERTEX_REGION", "europe-west4")
DATASET = "c2_warehouse"
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768
EMBEDDING_BATCH_SIZE = 25
CHUNK_TARGET_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
CHUNK_MAX_TOKENS = 600
CHUNK_MIN_TOKENS = 50

# Matches: "8.4.1 Force Majeure", "Sub-Clause 8.4 Engineer", "Clause 20.1 ..."
CLAUSE_PATTERN = re.compile(
    r'^(?:(?:Sub-)?[Cc]lause\s+)?(\d+[\d\.]*)\s+',
    re.IGNORECASE
)

def _get_secret(secret_name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def _get_doc_ai_processor_id() -> str:
    return _get_secret("DOCUMENT_AI_PROCESSOR_ID")

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _download_gcs_bytes(gcs_uri: str) -> bytes:
    client = storage.Client(project=PROJECT_ID)
    bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()

def detect_pdf_type(pdf_bytes: bytes) -> str:
    """Returns 'DIGITAL' if native text is extractable, else 'SCANNED'."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
        if len(text.strip()) >= 50:
            return "DIGITAL"
    return "SCANNED"

def extract_text_pymupdf(pdf_bytes: bytes) -> list[dict]:
    """Extract text page by page. Returns [{page_number, text}]."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        pages.append({"page_number": i + 1, "text": page.get_text()})
    return pages

def extract_text_documentai(pdf_bytes: bytes) -> list[dict]:
    """
    Extract text via Document AI OCR using the EU endpoint.
    processor_id stored in Secret Manager as DOCUMENT_AI_PROCESSOR_ID.
    """
    processor_id = _get_doc_ai_processor_id()
    # EU endpoint — data leaves GCC
    client_options = {"api_endpoint": "eu-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)

    processor_name = (
        f"projects/{PROJECT_ID}/locations/eu/processors/{processor_id}"
    )
    raw_document = documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf"
    )
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=raw_document
    )
    result = client.process_document(request=request)
    document = result.document

    # Group text by page
    pages = []
    for i, page in enumerate(document.pages):
        page_text = "\n".join(
            segment.layout.text_anchor.content
            if hasattr(segment.layout.text_anchor, "content")
            else ""
            for segment in page.paragraphs
        )
        if not page_text:
            # Fallback: use full document text sliced by page token offsets
            page_text = document.text[
                page.layout.text_anchor.text_segments[0].start_index
                : page.layout.text_anchor.text_segments[0].end_index
            ] if page.layout.text_anchor.text_segments else ""
        pages.append({"page_number": i + 1, "text": page_text})
    return pages

def chunk_contract_pages(pages: list[dict], enc) -> list[dict]:
    """
    Clause-aware chunking for CONTRACT documents.
    Flushes at clause boundaries; stamps section_ref on each chunk.
    """
    chunks = []
    chunk_index = 0
    buffer_tokens = []
    buffer_text = []
    current_clause = None
    current_page = 1

    def flush(clause_ref, page_num):
        nonlocal chunk_index
        text = " ".join(buffer_text).strip()
        if len(buffer_tokens) >= CHUNK_MIN_TOKENS:
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": text,
                "page_number": page_num,
                "section_ref": clause_ref,
                "token_count": len(buffer_tokens)
            })
            chunk_index += 1

    for page in pages:
        current_page = page["page_number"]
        for line in page["text"].split("\n"):
            line = line.strip()
            if not line:
                continue
            m = CLAUSE_PATTERN.match(line)
            if m:
                # Flush current buffer at clause boundary
                if buffer_text:
                    flush(current_clause, current_page)
                    buffer_tokens = []
                    buffer_text = []
                current_clause = m.group(1)

            line_tokens = enc.encode(line)
            if len(buffer_tokens) + len(line_tokens) > CHUNK_MAX_TOKENS:
                flush(current_clause, current_page)
                # Overlap: keep last CHUNK_OVERLAP_TOKENS tokens
                overlap_text = enc.decode(buffer_tokens[-CHUNK_OVERLAP_TOKENS:])
                buffer_tokens = enc.encode(overlap_text)
                buffer_text = [overlap_text]

            buffer_tokens.extend(line_tokens)
            buffer_text.append(line)

    if buffer_text:
        flush(current_clause, current_page)

    return chunks

def chunk_generic_pages(pages: list[dict], enc) -> list[dict]:
    """
    Paragraph-aware chunking for non-CONTRACT documents.
    No section_ref stamped.
    """
    chunks = []
    chunk_index = 0
    buffer_tokens = []
    buffer_text = []
    current_page = 1

    def flush(page_num):
        nonlocal chunk_index
        text = " ".join(buffer_text).strip()
        if len(buffer_tokens) >= CHUNK_MIN_TOKENS:
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": text,
                "page_number": page_num,
                "section_ref": None,
                "token_count": len(buffer_tokens)
            })
            chunk_index += 1

    for page in pages:
        current_page = page["page_number"]
        paragraphs = [p.strip() for p in page["text"].split("\n\n") if p.strip()]
        for para in paragraphs:
            para_tokens = enc.encode(para)
            if len(buffer_tokens) + len(para_tokens) > CHUNK_MAX_TOKENS:
                flush(current_page)
                overlap_text = enc.decode(buffer_tokens[-CHUNK_OVERLAP_TOKENS:])
                buffer_tokens = enc.encode(overlap_text)
                buffer_text = [overlap_text]
            buffer_tokens.extend(para_tokens)
            buffer_text.append(para)

    if buffer_text:
        flush(current_page)

    return chunks

def chunk_text(pages: list[dict], document_type: str) -> list[dict]:
    enc = tiktoken.get_encoding("cl100k_base")
    # Note: cl100k_base is an OpenAI tokenizer used as an approximation.
    # Claude uses a different tokenizer. Chunk boundaries will be close but not exact.
    if document_type == "CONTRACT":
        return chunk_contract_pages(pages, enc)
    else:
        return chunk_generic_pages(pages, enc)

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings in batches of EMBEDDING_BATCH_SIZE. Asserts 768 dims."""
    vertexai.init(project=PROJECT_ID, location=VERTEX_REGION)
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        results = model.get_embeddings(batch)
        for result in results:
            emb = result.values
            assert len(emb) == EMBEDDING_DIMS, (
                f"Expected {EMBEDDING_DIMS} dims, got {len(emb)}"
            )
            all_embeddings.append(emb)
    return all_embeddings

def check_duplicate(gcs_uri: str, file_hash: str, project_id: str) -> Optional[str]:
    """Returns existing document_id if the same file_hash exists in the project."""
    bq = bigquery.Client(project=PROJECT_ID)
    query = """
        SELECT document_id FROM `c2-intelligence.c2_warehouse.documents`
        WHERE project_id = @project_id
          AND file_hash = @file_hash
          AND status = 'ACTIVE'
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
        bigquery.ScalarQueryParameter("file_hash", "STRING", file_hash),
    ])
    results = list(bq.query(query, job_config=job_config).result())
    return results[0].document_id if results else None

def rollback_partial_ingestion(document_id: str, run_id: str):
    """Delete orphaned chunks if ingestion failed after partial insert."""
    bq = bigquery.Client(project=PROJECT_ID)
    bq.query(f"""
        DELETE FROM `c2-intelligence.c2_warehouse.chunks`
        WHERE document_id = '{document_id}'
    """).result()
    bq.query(f"""
        UPDATE `c2-intelligence.c2_warehouse.documents`
        SET status = 'DELETED'
        WHERE document_id = '{document_id}'
    """).result()
    bq.query(f"""
        UPDATE `c2-intelligence.c2_warehouse.ingestion_runs`
        SET status = 'PARTIAL_ROLLBACK', completed_at = CURRENT_TIMESTAMP()
        WHERE run_id = '{run_id}'
    """).result()

def ingest_document(
    project_id: str,
    layer: str,
    document_type: str,
    gcs_uri: str,
    file_name: str
) -> dict:
    run_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    bq = bigquery.Client(project=PROJECT_ID)

    # ── Step 1: Write RUNNING run record ────────────────────────────────────
    bq.query(f"""
        INSERT INTO `c2-intelligence.c2_warehouse.ingestion_runs`
          (run_id, project_id, gcs_uri, status)
        VALUES ('{run_id}', '{project_id}', '{gcs_uri}', 'RUNNING')
    """).result()

    try:
        # ── Step 2: Download and hash ────────────────────────────────────────
        pdf_bytes = _download_gcs_bytes(gcs_uri)
        file_hash = _sha256(pdf_bytes)

        # ── Step 3: Deduplication check ──────────────────────────────────────
        existing = check_duplicate(gcs_uri, file_hash, project_id)
        if existing:
            bq.query(f"""
                UPDATE `c2-intelligence.c2_warehouse.ingestion_runs`
                SET status = 'COMPLETE', completed_at = CURRENT_TIMESTAMP(),
                    error_message = 'DUPLICATE: existing document_id={existing}'
                WHERE run_id = '{run_id}'
            """).result()
            return {"document_id": existing, "chunk_count": 0,
                    "processing_method": "DUPLICATE", "run_id": run_id}

        # ── Step 4: Detect PDF type and extract ──────────────────────────────
        pdf_type = detect_pdf_type(pdf_bytes)
        processing_method = "GCC_NATIVE" if pdf_type == "DIGITAL" else "EXTERNAL_OCR"

        if pdf_type == "DIGITAL":
            pages = extract_text_pymupdf(pdf_bytes)
        else:
            pages = extract_text_documentai(pdf_bytes)

        # ── Step 5: Chunk ─────────────────────────────────────────────────────
        chunks = chunk_text(pages, document_type)

        # ── Step 6: Embed ─────────────────────────────────────────────────────
        texts = [c["chunk_text"] for c in chunks]
        embeddings = generate_embeddings(texts)

        # ── Step 7: Write document record ────────────────────────────────────
        bq.query(f"""
            INSERT INTO `c2-intelligence.c2_warehouse.documents`
              (document_id, project_id, layer, document_type, file_name,
               gcs_uri, file_hash, page_count, processing_method, ingestion_run_id)
            VALUES (
              '{document_id}', '{project_id}', '{layer}', '{document_type}',
              '{file_name}', '{gcs_uri}', '{file_hash}',
              {len(pages)}, '{processing_method}', '{run_id}'
            )
        """).result()

        # ── Step 8: Batch insert chunks ───────────────────────────────────────
        rows = []
        for i, c in enumerate(chunks):
            emb_literal = "[" + ",".join(str(v) for v in embeddings[i]) + "]"
            rows.append({
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "project_id": project_id,
                "layer": layer,
                "chunk_index": c["chunk_index"],
                "chunk_text": c["chunk_text"],
                "page_number": c["page_number"],
                "section_ref": c.get("section_ref"),
                "embedding": embeddings[i],
                "token_count": c["token_count"]
            })

        errors = bq.insert_rows_json(
            f"{PROJECT_ID}.{DATASET}.chunks", rows
        )
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")

        # ── Step 9: Mark run COMPLETE ─────────────────────────────────────────
        bq.query(f"""
            UPDATE `c2-intelligence.c2_warehouse.ingestion_runs`
            SET status = 'COMPLETE', completed_at = CURRENT_TIMESTAMP(),
                chunks_created = {len(chunks)}, document_id = '{document_id}',
                processing_method = '{processing_method}'
            WHERE run_id = '{run_id}'
        """).result()

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "processing_method": processing_method,
            "run_id": run_id
        }

    except Exception as e:
        rollback_partial_ingestion(document_id, run_id)
        raise
```

`ingestion/Dockerfile`:
```dockerfile
FROM python:3.11-slim

# PyMuPDF requires native libraries
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

`ingestion/main.py`:
```python
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pipeline import ingest_document

app = FastAPI()

class IngestRequest(BaseModel):
    project_id: str
    layer: str
    document_type: str
    gcs_uri: str
    file_name: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ingest")
def ingest(request: IngestRequest):
    try:
        result = ingest_document(
            project_id=request.project_id,
            layer=request.layer,
            document_type=request.document_type,
            gcs_uri=request.gcs_uri,
            file_name=request.file_name
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Task 3.2 — Document AI Processor Setup (EU Region)

Creating a Document AI processor requires the GCP Console or REST API. The `gcloud` CLI does not support `documentai processors create` in all SDK versions.

**Console method (recommended):**
1. [Console → Document AI](https://console.cloud.google.com/ai/document-ai)
2. Switch location to **EU**
3. Create processor → Document OCR → name: `c2-ocr-processor`
4. Copy the Processor ID (format: `a1b2c3d4e5f6g7h8`)
5. Store: `echo -n "PROCESSOR_ID" | gcloud secrets versions add DOCUMENT_AI_PROCESSOR_ID --data-file=-`

**REST API method (alternative):**
```bash
PROJECT="c2-intelligence"
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -X POST \
  "https://eu-documentai.googleapis.com/v1/projects/${PROJECT}/locations/eu/processors" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"type": "DOCUMENT_OCR", "displayName": "c2-ocr-processor"}'
```

The response contains `name` field like `.../processors/PROCESSOR_ID`. Extract and store in Secret Manager.

---

### Task 3.3 — Deploy Ingestion Service to Cloud Run

`ingestion/deploy.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
REGION="me-central1"
VERTEX_REGION="europe-west4"  # Update to me-central1 if SPLIT_REGIONS=NO
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/c2-images/c2-ingestion:latest"

echo "Building ingestion image..."
docker build -t ${IMAGE} .
docker push ${IMAGE}

gcloud run deploy c2-ingestion \
  --image=${IMAGE} \
  --region=${REGION} \
  --service-account=c2-ingestion@${PROJECT}.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --cpu=2 \
  --memory=4Gi \
  --timeout=900 \
  --min-instances=0 \
  --set-env-vars="VERTEX_REGION=${VERTEX_REGION},PROJECT_ID=${PROJECT}" \
  --project=${PROJECT}

# Record URL for Task 0.4 IAM binding rerun
INGESTION_URL=$(gcloud run services describe c2-ingestion \
  --region=${REGION} --format='value(status.url)')
echo "INGESTION_URL=${INGESTION_URL}"
echo "ACTION: Record INGESTION_URL — needed for Phase 4 Task 4.6"

# Rerun the IAM binding from Task 0.4
gcloud run services add-iam-policy-binding c2-ingestion \
  --region=${REGION} \
  --member="serviceAccount:c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

---

### Task 3.4 — End-to-End Ingestion Test (Digital PDF)

Upload a test PDF (a FIDIC clause extract) to `gs://c2-documents-l1`.

To invoke `c2-ingestion` with service account auth:
```bash
PROJECT="c2-intelligence"
REGION="me-central1"
INGESTION_URL=$(gcloud run services describe c2-ingestion \
  --region=${REGION} --format='value(status.url)')
TOKEN=$(gcloud auth print-identity-token)

curl -X POST "${INGESTION_URL}/ingest" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project-001",
    "layer": "L1",
    "document_type": "CONTRACT",
    "gcs_uri": "gs://c2-documents-l1/test-fidic-extract.pdf",
    "file_name": "test-fidic-extract.pdf"
  }'
```

**Verification:** Claude Chat queries `c2_warehouse.chunks` via MCP Toolbox and confirms:
- Rows exist
- `embedding` array length = 768
- `section_ref` is populated for CONTRACT-type chunks
- `processing_method = 'GCC_NATIVE'` for a digital PDF

---

### Task 3.5 — Create Vector Index (After Task 3.4 PASS)

```sql
-- Run ONLY after Task 3.4 verification is PASS and chunks table has data.
-- If this fails due to insufficient rows (fewer rows than num_lists=100),
-- log the error and proceed. BigQuery automatically uses brute-force
-- search when no IVF index exists — this is correct behaviour at prototype scale.
CREATE VECTOR INDEX IF NOT EXISTS chunks_embedding_idx
ON `c2-intelligence.c2_warehouse.chunks`(embedding)
OPTIONS (
  index_type = 'IVF',
  distance_type = 'COSINE',
  ivf_options = '{"num_lists": 100}'
);
```

---

### Task 3.6 — Ingest L2b Standards Layer

Insert the GLOBAL_STANDARDS project record first (Task 0.9) if not already done.

Upload and ingest these documents to `gs://c2-documents-l2b` with `project_id = 'GLOBAL_STANDARDS'`:

| File | document_type | layer |
|---|---|---|
| FIDIC Red Book 1999 | STANDARD | L2B |
| FIDIC Red Book 2017 | STANDARD | L2B |
| FIDIC Yellow Book 2017 | STANDARD | L2B |
| FIDIC Silver Book 2017 | STANDARD | L2B |
| SCL Protocol 2nd Edition 2017 | STANDARD | L2B |
| AACE RP 29R-03 | STANDARD | L2B |

Use the same curl invocation as Task 3.4 with `project_id = 'GLOBAL_STANDARDS'` and `layer = 'L2B'`.

**Verification:** Claude Chat calls `list_project_documents` for `GLOBAL_STANDARDS` and confirms all 6 documents appear with expected chunk counts.

---

## Phase 4 — API + Agent Layer

### Agent Execution Flow

```
User query → POST /api/v1/query
→ verify_firebase_jwt → extract user_id
→ user_has_project_access(user_id, project_id)
→ embed_query (Vertex AI text-embedding-004)
→ vector_search (BigQuery Python client)
→ build_grounded_prompt (chunks + domain)
→ AnthropicVertex stream (SSE)
→ stream tokens to client
→ finally: write_audit_log (direct BigQuery DML)
```

---

### Task 4.1 — api/config.py

```python
# api/config.py
import os

def get_model_id() -> str:
    model_id = os.environ.get("CLAUDE_MODEL_ID", "")
    if not model_id:
        raise ValueError("CLAUDE_MODEL_ID environment variable is not set.")
    if "@latest" in model_id.lower():
        raise ValueError(
            f"CLAUDE_MODEL_ID '{model_id}' contains '@latest'. "
            "Pin to a specific model version. See CLAUDE.md §7."
        )
    return model_id

CLAUDE_MODEL_ID = get_model_id()
VERTEX_REGION = os.environ.get("VERTEX_REGION", "europe-west4")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "c2-intelligence")
TOOLBOX_URL = os.environ.get("TOOLBOX_URL", "")
INGESTION_URL = os.environ.get("INGESTION_URL", "")
```

---

### Task 4.2 — api/claude_client.py

```python
# api/claude_client.py
from anthropic import AnthropicVertex
from api.config import CLAUDE_MODEL_ID, VERTEX_REGION, GCP_PROJECT

_client: AnthropicVertex = None

def get_client() -> AnthropicVertex:
    global _client
    if _client is None:
        _client = AnthropicVertex(
            project_id=GCP_PROJECT,
            region=VERTEX_REGION
        )
    return _client
```

---

### Task 4.3 — api/auth.py

```python
# api/auth.py
import json
import os
from cachetools import TTLCache
from functools import wraps

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from google.cloud import bigquery, secretmanager
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_firebase_app = None
_project_cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute TTL

GLOBAL_STANDARDS_PROJECT_ID = "GLOBAL_STANDARDS"

def _init_firebase():
    global _firebase_app
    if _firebase_app is not None:
        return
    # Load service account from Secret Manager
    sm_client = secretmanager.SecretManagerServiceClient()
    name = "projects/c2-intelligence/secrets/FIREBASE_SERVICE_ACCOUNT/versions/latest"
    response = sm_client.access_secret_version(request={"name": name})
    sa_info = json.loads(response.payload.data.decode("UTF-8"))
    cred = credentials.Certificate(sa_info)
    _firebase_app = firebase_admin.initialize_app(cred)

_init_firebase()

security = HTTPBearer()

class FirebaseUser:
    def __init__(self, uid: str, email: str):
        self.uid = uid
        self.email = email

async def verify_firebase_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> FirebaseUser:
    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token)
        return FirebaseUser(uid=decoded["uid"], email=decoded.get("email", ""))
    except firebase_admin.exceptions.FirebaseError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

def get_user_project_ids(user_id: str) -> list[str]:
    """Returns list of project_ids the user can access. TTL-cached for 5 min."""
    if user_id in _project_cache:
        return _project_cache[user_id]
    bq = bigquery.Client(project="c2-intelligence")
    query = """
        SELECT project_id
        FROM `c2-intelligence.c2_warehouse.project_members`
        WHERE user_id = @user_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
    ])
    results = bq.query(query, job_config=job_config).result()
    project_ids = [row.project_id for row in results]
    _project_cache[user_id] = project_ids
    return project_ids

def user_has_project_access(user_id: str, project_id: str) -> bool:
    # GLOBAL_STANDARDS is open to all authenticated users
    if project_id == GLOBAL_STANDARDS_PROJECT_ID:
        return True
    return project_id in get_user_project_ids(user_id)

def require_project_access(user: FirebaseUser, project_id: str):
    if not user_has_project_access(user.uid, project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project.")
```

---

### Task 4.4 — api/vector_search.py

```python
# api/vector_search.py
from google.cloud import bigquery
from api.config import GCP_PROJECT

def vector_search(
    query_embedding: list[float],
    project_id: str,
    layer_filter: str = "ALL",
) -> list[dict]:
    """
    Runs two VECTOR_SEARCH calls:
    - top 8 chunks from the target project (excluding L2B)
    - top 4 chunks from GLOBAL_STANDARDS L2B

    top_k and embedding are inlined as literals.
    BigQuery TVF arguments do not reliably accept named parameters.
    """
    assert len(query_embedding) == 768, (
        f"Expected 768 dims, got {len(query_embedding)}"
    )

    embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    layer_clause = (
        ""
        if layer_filter == "ALL"
        else f"AND base.layer = '{layer_filter}'"
    )

    query = f"""
    WITH project_results AS (
      SELECT
        base.chunk_id,
        base.chunk_text,
        base.layer,
        base.page_number,
        base.section_ref,
        base.document_id,
        distance
      FROM VECTOR_SEARCH(
        TABLE `{GCP_PROJECT}.c2_warehouse.chunks`,
        'embedding',
        (SELECT {embedding_literal} AS embedding),
        top_k => 8,
        distance_type => 'COSINE'
      )
      WHERE base.project_id = @project_id
        AND base.layer != 'L2B'
        {layer_clause}
    ),
    standards_results AS (
      SELECT
        base.chunk_id,
        base.chunk_text,
        base.layer,
        base.page_number,
        base.section_ref,
        base.document_id,
        distance
      FROM VECTOR_SEARCH(
        TABLE `{GCP_PROJECT}.c2_warehouse.chunks`,
        'embedding',
        (SELECT {embedding_literal} AS embedding),
        top_k => 4,
        distance_type => 'COSINE'
      )
      WHERE base.project_id = 'GLOBAL_STANDARDS'
        AND base.layer = 'L2B'
    )
    SELECT r.*, d.file_name, d.document_type
    FROM (
      SELECT * FROM project_results
      UNION ALL
      SELECT * FROM standards_results
    ) r
    JOIN `{GCP_PROJECT}.c2_warehouse.documents` d
      ON r.document_id = d.document_id
    WHERE d.status = 'ACTIVE'
    ORDER BY r.distance ASC
    """

    bq = bigquery.Client(project=GCP_PROJECT)
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
    ])
    results = bq.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
```

---

### Task 4.5 — api/embeddings.py

```python
# api/embeddings.py
import vertexai
from vertexai.language_models import TextEmbeddingModel
from api.config import GCP_PROJECT, VERTEX_REGION

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768

_model = None

def _get_model() -> TextEmbeddingModel:
    global _model
    if _model is None:
        vertexai.init(project=GCP_PROJECT, location=VERTEX_REGION)
        _model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    return _model

def embed_query(text: str) -> list[float]:
    model = _get_model()
    result = model.get_embeddings([text])
    embedding = result[0].values
    assert len(embedding) == EMBEDDING_DIMS, (
        f"Expected {EMBEDDING_DIMS} dims, got {len(embedding)}"
    )
    return embedding
```

---

### Task 4.6 — api/routing.py

```python
# api/routing.py

DOMAIN_KEYWORDS = {
    'legal': [
        'contract', 'clause', 'fidic', 'dispute', 'dab', 'daab', 'termination',
        'breach', 'notice', 'engineer', 'claim', 'liability', 'indemnity',
        'arbitration', 'particular conditions', 'time at large', 'force majeure',
        'suspension', 'taking-over', 'defects notification', 'sub-clause'
    ],
    'commercial': [
        'eot', 'extension of time', 'delay', 'prolongation', 'disruption',
        'variation', 'compensation event', 'programme', 'critical path',
        'concurrent delay', 'float', 'acceleration', 'scl protocol',
        'baseline programme', 'as-built programme'
    ],
    'financial': [
        'evm', 'earned value', 'cpi', 'spi', 'eac', 'etc', 'vac', 'cost control',
        'budget', 'forecast', 'cash flow', 'valuation', 'payment certificate',
        'retention', 'final account', 'reconciliation', 'cost to complete'
    ],
    'technical': [
        'ncr', 'itp', 'defect', 'snag', 'inspection', 'test',
        'specification', 'method statement', 'rfi', 'submittal',
        'decennial', 'latent defect', 'workmanship', 'material approval'
    ]
}

def route_query(query: str) -> list[str]:
    """
    Returns matched domains in order of keyword density.
    Defaults to ['legal'] if no keywords match.
    Execution uses domains[0] as the primary agent.
    All matched domains are logged in the audit record.
    Full multi-domain routing is v1.1.
    """
    query_lower = query.lower()
    scored = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scored[domain] = score
    if not scored:
        return ['legal']
    return sorted(scored.keys(), key=lambda d: scored[d], reverse=True)
```

---

### Task 4.7 — api/prompts.py

```python
# api/prompts.py

LEGAL_SYSTEM_PROMPT = """You are a construction law specialist analysing project documents under FIDIC and GCC jurisdiction.

GROUNDING RULES — NON-NEGOTIABLE:
1. Every legal position must cite a specific clause number from the retrieved document chunks.
2. Characterise FIDIC clause obligations precisely — do not paraphrase loosely.
3. State explicitly whether the clause is from General Conditions or Particular Conditions.
4. CANNOT ASSESS is mandatory when the retrieved chunks do not contain sufficient evidence. State which specific evidence is missing.
5. Apply the correct jurisdiction: UAE Civil Code Art. 880 (decennial liability), KSA Civil Transactions Law, or Qatar Civil Code as applicable to the project.
6. FIDIC hierarchy: Particular Conditions prevail over General Conditions.
7. Never state a legal position on facts not in the document record.

CITATION FORMAT:
- When section_ref is present: [Document Name, Page X, Clause Y]
- When section_ref is absent: [Document Name, Page X]
List all citations after your analysis."""

COMMERCIAL_SYSTEM_PROMPT = """You are a construction claims and delay analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. EOT analysis must reference programme evidence from the retrieved chunks.
2. Identify the delay category explicitly: Employer Risk Event / Contractor Risk Event / Concurrent Delay.
3. Prolongation cost methodology must follow SCL Protocol 2nd Edition 2017.
4. Disruption requires contemporaneous record evidence — productivity records, method statements.
5. Float ownership must be addressed where relevant.
6. CANNOT ASSESS if programme baseline, as-built records, or contemporaneous evidence is absent.
7. Apply AACE RP 29R-03 for cost methodology where referenced.

CITATION FORMAT:
- When section_ref is present: [Document Name, Page X, Clause Y]
- When section_ref is absent: [Document Name, Page X]
State analysis, cite programme and correspondence evidence, identify SCL or AACE reference applied."""

FINANCIAL_SYSTEM_PROMPT = """You are a construction financial analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. EVM metrics (CPI, SPI, EAC, ETC, VAC) must be calculated from figures in the retrieved chunks.
2. Show calculations explicitly — do not state a metric without showing the source numbers.
3. Final account reconciliation must cite specific payment certificates and contract documents.
4. Flag discrepancies between contract sum, certified amounts, and forecast final cost.
5. CANNOT ASSESS if the required financial records are not in the document warehouse.
6. Do not interpolate or estimate missing financial data.

CITATION FORMAT:
- When section_ref is present: [Document Name, Page X, Clause Y]
- When section_ref is absent: [Document Name, Page X]
Present calculations in tables. Cite source document and page for every figure."""

TECHNICAL_SYSTEM_PROMPT = """You are a construction technical analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. NCR analysis must identify the specific ITP hold/witness point or specification clause breached.
2. Defect characterisation requires a specification baseline from the retrieved chunks.
3. Apply UAE Civil Code Art. 880 for structural defects with 10-year liability period.
4. RFI and submittal analysis must be based on actual register entries in the document record.
5. CANNOT ASSESS if the relevant specification, ITP, or inspection records are absent.
6. Never characterise a defect as critical without a specification requirement to measure against.

CITATION FORMAT:
- When section_ref is present: [Document Name, Page X, Clause Y]
- When section_ref is absent: [Document Name, Page X]
Cite ITP, specification clause, or NCR reference for each finding."""

AGENT_PROMPTS = {
    'legal': LEGAL_SYSTEM_PROMPT,
    'commercial': COMMERCIAL_SYSTEM_PROMPT,
    'financial': FINANCIAL_SYSTEM_PROMPT,
    'technical': TECHNICAL_SYSTEM_PROMPT,
}

def build_grounded_prompt(query: str, chunks: list[dict], domain: str) -> str:
    """Constructs the user turn of the grounded prompt with retrieved evidence."""
    evidence_blocks = []
    for i, chunk in enumerate(chunks):
        cite = f"[{chunk['file_name']}, Page {chunk['page_number']}"
        if chunk.get("section_ref"):
            cite += f", Clause {chunk['section_ref']}"
        cite += "]"
        evidence_blocks.append(
            f"--- Evidence {i+1} {cite} ---\n{chunk['chunk_text']}"
        )

    evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else \
        "No relevant document chunks retrieved."

    return f"""RETRIEVED EVIDENCE:
{evidence_text}

QUERY: {query}

Provide your analysis based solely on the evidence above. Apply all grounding rules. Use CANNOT ASSESS where evidence is insufficient."""
```

---

### Task 4.8 — api/sessions.py

```python
# api/sessions.py
import json
import uuid
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from api.config import GCP_PROJECT

DATASET = "c2_warehouse"
MAX_TURNS = 10
SESSION_TTL_HOURS = 4
MAX_TURN_CONTENT_CHARS = 2000  # Truncate long turns to control context_json size

def create_session(project_id: str, user_id: str, domain: str) -> str:
    """Creates a new session using DML INSERT. Returns session_id."""
    session_id = str(uuid.uuid4())
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    ).isoformat()

    bq = bigquery.Client(project=GCP_PROJECT)
    bq.query(f"""
        INSERT INTO `{GCP_PROJECT}.{DATASET}.query_sessions`
          (session_id, project_id, user_id, domains, expires_at,
           last_active_at, turn_count, context_json)
        VALUES (
          '{session_id}', '{project_id}', '{user_id}', '{domain}',
          TIMESTAMP('{expires_at}'), CURRENT_TIMESTAMP(), 0, '[]'
        )
    """).result()
    return session_id

def get_session_context(session_id: str) -> list[dict]:
    """Returns last MAX_TURNS turns from context_json. Empty list if not found."""
    bq = bigquery.Client(project=GCP_PROJECT)
    query = f"""
        SELECT context_json FROM `{GCP_PROJECT}.{DATASET}.query_sessions`
        WHERE session_id = @session_id
          AND expires_at > CURRENT_TIMESTAMP()
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
    ])
    results = list(bq.query(query, job_config=job_config).result())
    if not results or not results[0].context_json:
        return []
    return json.loads(results[0].context_json)

def update_session_context(session_id: str, user_query: str, assistant_response: str):
    """
    Appends the latest turn, trims to MAX_TURNS, updates last_active_at.
    Note: BigQuery DML UPDATE takes 1-5 seconds. Accepted v1.0 tradeoff.
    Per-turn content is truncated to MAX_TURN_CONTENT_CHARS to control size.
    """
    current = get_session_context(session_id)
    current.append({
        "role": "user",
        "content": user_query[:MAX_TURN_CONTENT_CHARS]
    })
    current.append({
        "role": "assistant",
        "content": assistant_response[:MAX_TURN_CONTENT_CHARS]
    })
    # Keep last MAX_TURNS turns (each turn = 1 user + 1 assistant = 2 entries)
    trimmed = current[-(MAX_TURNS * 2):]
    context_json = json.dumps(trimmed).replace("'", "\\'")

    bq = bigquery.Client(project=GCP_PROJECT)
    bq.query(f"""
        UPDATE `{GCP_PROJECT}.{DATASET}.query_sessions`
        SET context_json = '{context_json}',
            last_active_at = CURRENT_TIMESTAMP(),
            turn_count = turn_count + 1
        WHERE session_id = '{session_id}'
    """).result()
```

---

### Task 4.9 — api/audit.py

```python
# api/audit.py
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery
from api.config import GCP_PROJECT

def write_audit_log(
    project_id: str,
    user_id: str,
    user_email: str,
    session_id: str,
    action: str,
    domains: list[str],
    query_text: str,
    chunks_retrieved: int,
    model_used: str,
    latency_ms: int
):
    """
    Direct BigQuery DML INSERT. Not via MCP Toolbox.
    Called from a finally block in the SSE generator to survive client disconnects.
    """
    log_id = str(uuid.uuid4())
    domains_str = ",".join(domains)
    safe_query = query_text.replace("'", "\\'")[:500]

    bq = bigquery.Client(project=GCP_PROJECT)
    bq.query(f"""
        INSERT INTO `{GCP_PROJECT}.c2_warehouse.audit_log`
          (log_id, project_id, session_id, user_id, user_email,
           action, domains, query_text, chunks_retrieved, model_used, latency_ms)
        VALUES (
          '{log_id}', '{project_id}', '{session_id}', '{user_id}', '{user_email}',
          '{action}', '{domains_str}', '{safe_query}',
          {chunks_retrieved}, '{model_used}', {latency_ms}
        )
    """).result()
```

---

### Task 4.10 — api/main.py

```python
# api/main.py
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import google.auth.transport.requests
import google.oauth2.id_token
import httpx

from api.auth import verify_firebase_jwt, require_project_access, FirebaseUser
from api.config import CLAUDE_MODEL_ID, INGESTION_URL, GCP_PROJECT
from api.claude_client import get_client
from api.embeddings import embed_query
from api.vector_search import vector_search
from api.prompts import AGENT_PROMPTS, build_grounded_prompt
from api.routing import route_query
from api.sessions import create_session, get_session_context, update_session_context
from api.audit import write_audit_log
from google.cloud import bigquery, storage

app = FastAPI(title="C2 Intelligence API", version="1.0")

# CORS — updated after Vercel deployment (Phase 5 Task 5.6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock to Vercel domain after Phase 5 Task 5.6
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    project_id: str
    query: str
    session_id: Optional[str] = None
    layer_filter: Optional[str] = "ALL"

class IngestTriggerRequest(BaseModel):
    project_id: str
    layer: str
    document_type: str
    gcs_uri: str
    file_name: str

class CreateProjectRequest(BaseModel):
    project_id: str
    project_name: str
    client_name: Optional[str] = None
    contract_type: Optional[str] = None
    jurisdiction: Optional[str] = None

class AddMemberRequest(BaseModel):
    user_email: str
    role: str  # OWNER, ANALYST, VIEWER

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0"}

# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects")
async def get_projects(user: FirebaseUser = Depends(verify_firebase_jwt)):
    bq = bigquery.Client(project=GCP_PROJECT)
    query = """
        SELECT p.project_id, p.project_name, p.client_name,
               p.contract_type, p.jurisdiction, pm.role
        FROM `c2-intelligence.c2_warehouse.project_members` pm
        JOIN `c2-intelligence.c2_warehouse.projects` p
          ON pm.project_id = p.project_id
        WHERE pm.user_id = @user_id AND p.is_active = TRUE
        ORDER BY p.project_name
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("user_id", "STRING", user.uid)
    ])
    results = bq.query(query, job_config=job_config).result()
    return [dict(row) for row in results]

@app.post("/api/v1/projects")
async def create_project(
    request: CreateProjectRequest,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    bq = bigquery.Client(project=GCP_PROJECT)
    # Create project
    bq.query(f"""
        INSERT INTO `{GCP_PROJECT}.c2_warehouse.projects`
          (project_id, project_name, client_name, contract_type,
           jurisdiction, created_by)
        VALUES (
          '{request.project_id}', '{request.project_name}',
          '{request.client_name or ""}', '{request.contract_type or ""}',
          '{request.jurisdiction or ""}', '{user.uid}'
        )
    """).result()
    # Add creator as OWNER
    bq.query(f"""
        INSERT INTO `{GCP_PROJECT}.c2_warehouse.project_members`
          (project_id, user_id, user_email, role, added_by)
        VALUES (
          '{request.project_id}', '{user.uid}', '{user.email}',
          'OWNER', '{user.uid}'
        )
    """).result()
    return {"project_id": request.project_id, "status": "created"}

@app.post("/api/v1/project/{project_id}/members")
async def add_member(
    project_id: str,
    request: AddMemberRequest,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, project_id)
    bq = bigquery.Client(project=GCP_PROJECT)
    # Resolve email to UID via Firebase Admin SDK if needed, or store email only
    bq.query(f"""
        INSERT INTO `{GCP_PROJECT}.c2_warehouse.project_members`
          (project_id, user_id, user_email, role, added_by)
        VALUES (
          '{project_id}', '', '{request.user_email}',
          '{request.role}', '{user.uid}'
        )
    """).result()
    return {"status": "member added", "email": request.user_email}

# ── Documents ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/project/{project_id}/documents")
async def get_documents(
    project_id: str,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, project_id)
    bq = bigquery.Client(project=GCP_PROJECT)
    query = """
        SELECT document_id, layer, document_type, file_name,
               page_count, processing_method, ingested_at, status
        FROM `c2-intelligence.c2_warehouse.documents`
        WHERE project_id = @project_id AND status = 'ACTIVE'
        ORDER BY ingested_at DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("project_id", "STRING", project_id)
    ])
    results = bq.query(query, job_config=job_config).result()
    return [dict(row) for row in results]

@app.get("/api/v1/project/{project_id}/upload-url")
async def get_upload_url(
    project_id: str,
    filename: str = Query(...),
    layer: str = Query(default="L1"),
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, project_id)
    bucket_map = {"L1": "c2-documents-l1", "L2A": "c2-documents-l2a"}
    bucket_name = bucket_map.get(layer, "c2-documents-l1")
    gcs_path = f"{project_id}/{filename}"

    storage_client = storage.Client(project=GCP_PROJECT)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=3600,
        method="PUT",
        content_type="application/pdf"
    )
    return {
        "signed_url": signed_url,
        "gcs_uri": f"gs://{bucket_name}/{gcs_path}"
    }

# ── Ingestion trigger ─────────────────────────────────────────────────────────

@app.post("/api/v1/ingest")
async def trigger_ingest(
    request: IngestTriggerRequest,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, request.project_id)

    # Get an identity token to authenticate to c2-ingestion (Cloud Run)
    auth_request = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_request, INGESTION_URL)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{INGESTION_URL}/ingest",
            json=request.dict(),
            headers={"Authorization": f"Bearer {id_token}"},
            timeout=900.0
        )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ingestion error: {response.text}")
    return response.json()

# ── Query (SSE streaming) ─────────────────────────────────────────────────────

@app.post("/api/v1/query")
async def query(
    request: QueryRequest,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, request.project_id)

    domains = route_query(request.query)
    primary_domain = domains[0]
    start_time = time.time()

    # Session handling
    session_id = request.session_id or create_session(
        request.project_id, user.uid, primary_domain
    )
    session_context = get_session_context(session_id) if request.session_id else []

    # Embed and search
    embedding = embed_query(request.query)
    chunks = vector_search(embedding, request.project_id, request.layer_filter or "ALL")

    # Build prompt
    system_prompt = AGENT_PROMPTS[primary_domain]
    user_prompt = build_grounded_prompt(request.query, chunks, primary_domain)

    # Build messages list with session context
    messages = session_context + [{"role": "user", "content": user_prompt}]

    full_response = []

    async def generate():
        try:
            # Meta event: session info and domain
            yield {
                "event": "meta",
                "data": f'{{"session_id": "{session_id}", "domains": {domains}, '
                        f'"chunks_retrieved": {len(chunks)}}}'
            }

            # Stream tokens
            client = get_client()
            with client.messages.stream(
                model=CLAUDE_MODEL_ID,
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    full_response.append(text)
                    yield {"event": "token", "data": text}

            latency_ms = int((time.time() - start_time) * 1000)
            yield {
                "event": "done",
                "data": f'{{"latency_ms": {latency_ms}}}'
            }

        finally:
            # Guarantee audit write even if client disconnects
            response_text = "".join(full_response)
            latency_ms = int((time.time() - start_time) * 1000)

            try:
                write_audit_log(
                    project_id=request.project_id,
                    user_id=user.uid,
                    user_email=user.email,
                    session_id=session_id,
                    action="QUERY",
                    domains=domains,
                    query_text=request.query,
                    chunks_retrieved=len(chunks),
                    model_used=CLAUDE_MODEL_ID,
                    latency_ms=latency_ms
                )
            except Exception:
                pass  # Audit failure must not crash the response

            # Update session context (non-blocking best-effort)
            if response_text:
                try:
                    update_session_context(session_id, request.query, response_text)
                except Exception:
                    pass

    return EventSourceResponse(generate())

# ── Audit ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/audit/{project_id}")
async def get_audit_log(
    project_id: str,
    user: FirebaseUser = Depends(verify_firebase_jwt)
):
    require_project_access(user, project_id)
    bq = bigquery.Client(project=GCP_PROJECT)
    query = """
        SELECT log_id, user_email, action, domains, query_text,
               chunks_retrieved, model_used, latency_ms, logged_at
        FROM `c2-intelligence.c2_warehouse.audit_log`
        WHERE project_id = @project_id
        ORDER BY logged_at DESC
        LIMIT 200
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("project_id", "STRING", project_id)
    ])
    results = bq.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
```

---

### Task 4.11 — api/requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
sse-starlette==1.8.2
anthropic[vertex]==0.30.0
google-cloud-bigquery==3.25.0
google-cloud-storage==2.18.2
google-cloud-aiplatform==1.67.1
google-cloud-secret-manager==2.20.0
google-auth==2.30.0
firebase-admin==6.5.0
cachetools==5.3.3
httpx==0.27.0
pydantic==2.7.1
```

---

### Task 4.12 — api/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

### Task 4.13 — Deploy c2-api to Cloud Run

`api/deploy.sh`:
```bash
#!/bin/bash
set -e
PROJECT="c2-intelligence"
REGION="me-central1"
VERTEX_REGION="europe-west4"   # Update if SPLIT_REGIONS=NO
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/c2-images/c2-api:latest"

# These URLs must be known before running this script
# INGESTION_URL: from Phase 3 Task 3.3
# TOOLBOX_URL: from Phase 2 Task 2.3
if [ -z "${INGESTION_URL}" ] || [ -z "${TOOLBOX_URL}" ]; then
  echo "ERROR: INGESTION_URL and TOOLBOX_URL must be set before deploying c2-api"
  echo "  export INGESTION_URL=<url from Phase 3>"
  echo "  export TOOLBOX_URL=<url from Phase 2>"
  exit 1
fi

echo "Building c2-api image..."
docker build -t ${IMAGE} .
docker push ${IMAGE}

gcloud run deploy c2-api \
  --image=${IMAGE} \
  --region=${REGION} \
  --service-account=c2-api@${PROJECT}.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --cpu=2 \
  --memory=2Gi \
  --min-instances=1 \
  --timeout=300 \
  --set-env-vars="GCP_PROJECT=${PROJECT},VERTEX_REGION=${VERTEX_REGION},INGESTION_URL=${INGESTION_URL},TOOLBOX_URL=${TOOLBOX_URL}" \
  --set-secrets="CLAUDE_MODEL_ID=CLAUDE_MODEL_ID:latest" \
  --project=${PROJECT}

API_URL=$(gcloud run services describe c2-api \
  --region=${REGION} --format='value(status.url)')
echo "API_URL=${API_URL}"
echo "ACTION: Record API_URL — needed for Phase 5 frontend env vars"
```

**Verification:** Claude Chat calls `/api/v1/projects` and `/api/v1/query` (with test project) and confirms:
- JWT authentication works
- Grounded response returned with citations
- CANNOT ASSESS returned when evidence is absent
- SSE stream received with `meta`, `token`, and `done` events
- Audit log entry appears in BigQuery

---

## Phase 5 — React Front End

### Task 5.1 — Initialise Project

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install \
  @tanstack/react-query \
  firebase \
  axios \
  tailwindcss \
  postcss \
  autoprefixer \
  react-router-dom \
  @microsoft/fetch-event-source \
  @radix-ui/react-dialog \
  @radix-ui/react-dropdown-menu \
  @radix-ui/react-toast

npx tailwindcss init -p
```

`frontend/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

`frontend/src/index.css` — add at top:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`frontend/.env.example`:
```
# API
VITE_API_URL=https://<c2-api-cloud-run-url>    # Set after Phase 4 Task 4.13

# Firebase (public-safe values from Firebase console Task 0.8)
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
```

`frontend/vercel.json`:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

### Task 5.2 — Firebase Auth Setup

`frontend/src/lib/firebase.ts`:
```typescript
import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
```

---

### Task 5.3 — Implement Pages

**Upload page behaviour for scanned PDF banner:**
The frontend cannot reliably detect scanned PDFs client-side without reading the file content. Show the acknowledgment banner on every upload:

> "If this document is a scanned PDF, its content will be sent to an EU OCR processor for text extraction. This is the only way to process scanned documents. Please acknowledge to proceed."

User taps "Acknowledge and Upload" → signed URL is fetched → file is PUT to Cloud Storage → `/api/v1/ingest` is called.

**Pages to implement:**
- `src/pages/Login.tsx` — Google Sign-In button
- `src/pages/Projects.tsx` — project selector + create project form
- `src/pages/Upload.tsx` — document upload with acknowledgment banner
- `src/pages/Query.tsx` — multi-turn chat with SSE streaming, domain badge, citations panel, CANNOT ASSESS in red
- `src/pages/Audit.tsx` — audit trail table with CSV export

**Query page SSE consumption:**
```typescript
import { fetchEventSource } from '@microsoft/fetch-event-source';

const streamQuery = async (projectId: string, query: string, sessionId?: string) => {
  const token = await auth.currentUser?.getIdToken();
  await fetchEventSource(`${import.meta.env.VITE_API_URL}/api/v1/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ project_id: projectId, query, session_id: sessionId }),
    onmessage(event) {
      if (event.event === 'meta') {
        // parse session_id, domains, chunks_retrieved
      } else if (event.event === 'token') {
        // append event.data to displayed response
      } else if (event.event === 'done') {
        // parse latency_ms, mark streaming complete
      }
    },
    onerror(err) {
      throw err; // do not retry on error
    },
  });
};
```

---

### Task 5.4 — Deploy to Vercel

1. Push `frontend/` to GitHub (same repo, `frontend/` subdirectory)
2. Vercel dashboard → Import project → set Root Directory to `frontend`
3. Add environment variables from `.env.example` (with real values from Tasks 0.8 and 4.13)
4. Deploy

After first successful deployment, lock CORS in `c2-api`:
```python
# In api/main.py, replace allow_origins=["*"] with:
allow_origins=[
    "https://your-vercel-app.vercel.app",
    "http://localhost:5173"  # local dev only
]
```

Redeploy `c2-api` after updating CORS.

---

## Phase 6 — Governance and Security

### Task 6.1 — Model Armor

```bash
gcloud services enable modelarmor.googleapis.com --project=c2-intelligence

gcloud model-armor floor-settings update \
  --full-uri='projects/c2-intelligence/locations/global/floorSetting' \
  --mcp-sanitization=ENABLED \
  --malicious-uri-filter-settings-enforcement=ENABLED \
  --pi-and-jailbreak-filter-settings-enforcement=ENABLED \
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM_AND_ABOVE
```

Note: Model Armor uses `locations/global`. Verify availability in your GCP organisation before running.

---

### Task 6.2 — BigQuery Cost Controls

```sql
-- Set a per-query bytes billed limit.
-- WARNING: Set this value AFTER measuring actual vector search query costs
-- on real data. 100GB is a placeholder — a VECTOR_SEARCH on a large table
-- can easily exceed this and fail. Calibrate against production query costs.
ALTER PROJECT `c2-intelligence`
SET OPTIONS (max_bytes_billed = 107374182400);  -- 100 GB placeholder
```

**Do not treat 100GB as a safe production limit.** After Phase 5 is live, run representative queries and measure actual bytes billed via `INFORMATION_SCHEMA.JOBS`. Set `max_bytes_billed` to 2-3x the p99 query cost.

---

### Task 6.3 — Billing Alert

Manual step in GCP Console:
1. Billing → Budgets & Alerts → Create Budget
2. Set amount: $100/month
3. Alert thresholds: 50%, 90%, 100%
4. Add Yasser's email as notification recipient

**Verification:** Yasser confirms the alert appears in the Billing console.

---

## Execution Rules (Restated)

These are repeated here for completeness. The authoritative version is CLAUDE.md §3.

1. One task per commit. No batching.
2. QG PASS required before next task. Claude Chat only.
3. No self-reporting by Claude Code.
4. Yasser approves every commit.
5. Always `git pull` before any work.
6. Secrets in Secret Manager only.
7. Never `@latest` for the model string.
8. API versioned at `/api/v1/`.
9. Deploy order is fixed (CLAUDE.md §11).
10. Do not build v1.1 features.
