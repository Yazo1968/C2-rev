# C2 Intelligence — Build Plan v2.0

**Architecture: BigQuery + MCP Toolbox + Cloud Run + React
Revised: April 2026 | Clean Slate**

\---

## What Changed from v1.0

|Change|Reason|
|-|-|
|Vector search moved from MCP Toolbox to Python agent|VECTOR\_SEARCH SQL cannot be parameterised with ARRAY<FLOAT64> via tools.yaml|
|BigQuery RLS removed|SESSION\_USER() returns service account, not Firebase UID|
|Two-path PDF ingestion|Document AI not available in me-central1; data sovereignty risk|
|C2-agents + C2-api collapsed into one service|Unnecessary complexity and service-to-service auth overhead|
|tools.yaml YAML structure corrected|Original had wrong key/name syntax|
|Report generation moved to v1.1|Undefined implementation; cuts scope to what is buildable|
|SSE streaming added to Phase 5 and 6|15-40 second responses require streaming|
|Clause-aware chunking added|FIDIC contracts have structured clause numbering that must be preserved|
|Vector index creation moved to Phase 3|Cannot create IVF index on empty table|
|L2b standards ingestion added as Task 3.6|Platform unusable without FIDIC/SCL/AACE reference layer|
|Embedding dimensions locked (768, text-embedding-004)|Prevents silent failures from model mismatch|
|Vertex AI regional availability check added as first task|me-central1 availability unverified for Vertex AI|
|OAuth setup for MCP Toolbox connector made explicit|Required for Claude Chat verification discipline|
|Session management designed|Multi-turn context was stated but never implemented|

\---

## Working Model

|Role|Responsibility|
|-|-|
|Yasser|Domain expert, product owner, approval gate before every commit|
|Claude Chat|Architecture, decisions, SQL, tools.yaml authoring, Claude Code prompt generation, independent verification via MCP Toolbox|
|Claude Code|Execution only — one task per commit, no action without explicit instruction|

**Verification discipline:** Claude Chat connects to MCP Toolbox (deployed to Cloud Run with OAuth) as a custom MCP connector in Claude.ai. Every task is independently verified by querying BigQuery directly before PASS is issued. No self-reporting accepted.

**One task per commit. QG PASS before next task. No batching.**

\---

## Platform Stack (Locked)

|Component|Technology|Notes|
|-|-|-|
|Data warehouse|BigQuery|Region: me-central1 if Vertex AI confirmed; else see Phase 0 Task 0.1|
|Document storage|Cloud Storage|3 buckets: L1, L2a, L2b|
|PDF ingestion — digital|PyMuPDF|Native text extraction, stays in GCC, no external API|
|PDF ingestion — scanned|Document AI (eu endpoint)|Flagged as EXTERNAL\_OCR in documents table; user acknowledged|
|Embeddings|Vertex AI text-embedding-004|768 dimensions, locked|
|Vector search|BigQuery Python client, VECTOR\_SEARCH()|In agent layer, not MCP Toolbox|
|MCP retrieval tools|MCP Toolbox (genai-toolbox) on Cloud Run|Document lookup, project listing, audit writes|
|Agent model|Claude on Vertex AI|Model string locked in Phase 0|
|API + Agent layer|Single FastAPI service on Cloud Run|C2-api|
|Streaming|Server-Sent Events (SSE)|Cloud Run + React EventSource|
|Front end|React + TypeScript + Vite|Deployed to Vercel|
|Auth|Firebase Auth (Google Sign-In)|JWT validated at API layer|
|Secrets|Secret Manager|All credentials|
|Audit|BigQuery audit\_log table|Written via MCP Toolbox tool|
|Cost control|BigQuery max bytes billed quota|Set in Phase 7|

\---

## Phase 0 — GCP Foundation

### Task 0.1 — Verify GCP service availability and lock region

Before any resource is created, verify:

```bash
# Check BigQuery availability
gcloud services list --available --filter="name:bigquery.googleapis.com"

# Check Vertex AI (text-embedding-004 and Claude) in me-central1
# Must confirm: aiplatform.googleapis.com available in me-central1
# Must confirm: Claude on Vertex AI available in me-central1

# Check Cloud Run in me-central1
gcloud run regions list | grep me-central1
```

**Decision gate:**

* If Vertex AI + Claude available in `me-central1` → all resources in `me-central1`
* If Vertex AI NOT available in `me-central1` → BigQuery + Cloud Storage + Cloud Run in `me-central1`; Vertex AI in `europe-west4`; document this split explicitly in CLAUDE.md

Lock the Claude model string. On Vertex AI, verify the exact model ID (e.g., `claude-sonnet-4-5@20251015` or current). Store in Secret Manager. Never use `@latest` in production.

**Verification:** Claude Chat confirms region decision is logged in CLAUDE.md before Phase 0 proceeds.

### Task 0.2 — Create GCP project and enable APIs

```bash
gcloud projects create C2-intelligence --name="C2 Intelligence"
gcloud config set project C2-intelligence

gcloud services enable \\
  bigquery.googleapis.com \\
  bigquerystorage.googleapis.com \\
  aiplatform.googleapis.com \\
  documentai.googleapis.com \\
  run.googleapis.com \\
  storage.googleapis.com \\
  secretmanager.googleapis.com \\
  iam.googleapis.com \\
  cloudresourcemanager.googleapis.com \\
  firebase.googleapis.com
```

### Task 0.3 — Create service accounts

```bash
# Single API + agent service account (services collapsed)
gcloud iam service-accounts create C2-api \\
  --display-name="C2 API and Agent layer"

# Ingestion service account
gcloud iam service-accounts create C2-ingestion \\
  --display-name="C2 Document Ingestion"

# MCP Toolbox service account
gcloud iam service-accounts create C2-toolbox \\
  --display-name="C2 MCP Toolbox"
```

### Task 0.4 — Grant IAM roles

```bash
PROJECT=C2-intelligence

# C2-api: reads BigQuery, calls Vertex AI, reads secrets
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-api@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.dataViewer"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-api@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-api@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-api@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/secretmanager.secretAccessor"

# C2-ingestion: writes BigQuery, reads/writes Cloud Storage, calls Vertex AI and Document AI
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-ingestion@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-ingestion@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-ingestion@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-ingestion@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-ingestion@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/documentai.apiUser"

# C2-toolbox: reads BigQuery, writes audit log
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-toolbox@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding $PROJECT \\
  --member="serviceAccount:C2-toolbox@$PROJECT.iam.gserviceaccount.com" \\
  --role="roles/bigquery.jobUser"
```

### Task 0.5 — Create Cloud Storage buckets

```bash
REGION=me-central1  # or region locked in Task 0.1
gcloud storage buckets create gs://C2-documents-l1 --location=$REGION --uniform-bucket-level-access
gcloud storage buckets create gs://C2-documents-l2a --location=$REGION --uniform-bucket-level-access
gcloud storage buckets create gs://C2-documents-l2b --location=$REGION --uniform-bucket-level-access
```

### Task 0.6 — Create GitHub repository

New repository: `github.com/Yazo1968/C2Intelligence-v2`
Branch: `main`
First commit: `CLAUDE.md` with session opening protocol.

**Session opening protocol (CLAUDE.md):**

```
1. cd C2Intelligence-v2 \&\& git pull origin main
2. Read CLAUDE.md
3. gcloud config set project C2-intelligence
4. Confirm MCP Toolbox service is running (Cloud Run status)
5. Confirm HEAD commit matches expected
6. Then act. Never clone.
```

\---

## Phase 1 — BigQuery Schema

### Task 1.1 — Create dataset

```sql
CREATE SCHEMA IF NOT EXISTS `C2-intelligence.C2\_warehouse`
OPTIONS (
  location = 'me-central1',
  description = 'C2 Intelligence document warehouse'
);
```

### Task 1.2 — Create projects table

```sql
CREATE TABLE C2\_warehouse.projects (
  project\_id      STRING NOT NULL,
  project\_name    STRING NOT NULL,
  client\_name     STRING,
  contract\_type   STRING,  -- FIDIC\_RED\_1999, FIDIC\_RED\_2017, FIDIC\_YELLOW\_2017, FIDIC\_SILVER\_2017, BESPOKE
  jurisdiction    STRING,  -- UAE, KSA, QAT
  currency        STRING DEFAULT 'AED',
  created\_at      TIMESTAMP DEFAULT CURRENT\_TIMESTAMP(),
  created\_by      STRING,
  is\_active       BOOL DEFAULT TRUE
);
```

### Task 1.3 — Create project\_members table

**This replaces BigQuery RLS. Authorization is enforced here at the API layer.**

```sql
CREATE TABLE C2\_warehouse.project\_members (
  project\_id   STRING NOT NULL,
  user\_id      STRING NOT NULL,  -- Firebase UID
  user\_email   STRING,
  role         STRING NOT NULL,  -- OWNER, ANALYST, VIEWER
  added\_at     TIMESTAMP DEFAULT CURRENT\_TIMESTAMP(),
  added\_by     STRING
);
```

### Task 1.4 — Create documents table

```sql
CREATE TABLE C2\_warehouse.documents (
  document\_id          STRING NOT NULL,
  project\_id           STRING NOT NULL,
  layer                STRING NOT NULL,  -- L1, L2A, L2B
  document\_type        STRING,           -- CONTRACT, CORRESPONDENCE, PROGRAMME, POLICY, STANDARD, DRAWING
  file\_name            STRING NOT NULL,
  gcs\_uri              STRING NOT NULL,
  page\_count           INT64,
  processing\_method    STRING,           -- GCC\_NATIVE (PyMuPDF) or EXTERNAL\_OCR (Document AI)
  ingested\_at          TIMESTAMP DEFAULT CURRENT\_TIMESTAMP(),
  ingestion\_run\_id     STRING,
  status               STRING DEFAULT 'ACTIVE'  -- ACTIVE, SUPERSEDED, DELETED
)
PARTITION BY DATE(ingested\_at)
CLUSTER BY project\_id, layer;
```

### Task 1.5 — Create chunks table

```sql
CREATE TABLE C2\_warehouse.chunks (
  chunk\_id        STRING NOT NULL,
  document\_id     STRING NOT NULL,
  project\_id      STRING NOT NULL,
  layer           STRING NOT NULL,
  chunk\_index     INT64 NOT NULL,
  chunk\_text      STRING NOT NULL,
  page\_number     INT64,
  section\_ref     STRING,        -- For CONTRACT docs: clause number e.g. "20.1" or "Sub-Clause 8.4"
  embedding       ARRAY<FLOAT64>, -- 768 dimensions, text-embedding-004
  token\_count     INT64,
  created\_at      TIMESTAMP DEFAULT CURRENT\_TIMESTAMP()
)
PARTITION BY DATE(created\_at)
CLUSTER BY project\_id, layer, document\_id;
```

**Note:** Vector index NOT created here. Created in Phase 3 after first data batch.

### Task 1.6 — Create ingestion\_runs table

```sql
CREATE TABLE C2\_warehouse.ingestion\_runs (
  run\_id          STRING NOT NULL,
  project\_id      STRING NOT NULL,
  document\_id     STRING,
  gcs\_uri         STRING,
  started\_at      TIMESTAMP DEFAULT CURRENT\_TIMESTAMP(),
  completed\_at    TIMESTAMP,
  status          STRING,  -- RUNNING, COMPLETE, FAILED
  chunks\_created  INT64,
  processing\_method STRING,
  error\_message   STRING,
  retry\_count     INT64 DEFAULT 0
);
```

### Task 1.7 — Create audit\_log table

```sql
CREATE TABLE C2\_warehouse.audit\_log (
  log\_id           STRING NOT NULL,
  project\_id       STRING NOT NULL,
  session\_id       STRING,
  user\_id          STRING,
  user\_email       STRING,
  action           STRING NOT NULL,  -- QUERY, INGEST, LOGIN, EXPORT
  domain           STRING,           -- LEGAL, COMMERCIAL, FINANCIAL, TECHNICAL, MULTI
  query\_text       STRING,
  chunks\_retrieved INT64,
  model\_used       STRING,
  latency\_ms       INT64,
  logged\_at        TIMESTAMP DEFAULT CURRENT\_TIMESTAMP()
)
PARTITION BY DATE(logged\_at)
CLUSTER BY project\_id, action;
```

### Task 1.8 — Create query\_sessions table

```sql
CREATE TABLE C2\_warehouse.query\_sessions (
  session\_id      STRING NOT NULL,
  project\_id      STRING NOT NULL,
  user\_id         STRING NOT NULL,
  started\_at      TIMESTAMP DEFAULT CURRENT\_TIMESTAMP(),
  last\_active\_at  TIMESTAMP,
  turn\_count      INT64 DEFAULT 0,
  domain          STRING,
  expires\_at      TIMESTAMP,  -- started\_at + 4 hours
  context\_json    STRING       -- last 10 turns serialised as JSON
);
```

**Verification:** Claude Chat queries `INFORMATION\_SCHEMA.TABLES` via MCP Toolbox to confirm all 7 tables exist with correct schemas.

\---

## Phase 2 — MCP Toolbox Setup

**Purpose of MCP Toolbox in this plan:** Document and project retrieval, audit log writes, and Claude Chat verification. Vector search is NOT in Toolbox — it runs in the agent layer Python code.

### Task 2.1 — Write tools.yaml (corrected structure)

```yaml
sources:
  C2-bigquery:
    kind: bigquery
    project: C2-intelligence
    location: me-central1

tools:
  list\_project\_documents:
    kind: bigquery-sql
    source: C2-bigquery
    description: List all active documents for a project
    parameters:
      - name: project\_id
        type: string
        description: The project ID
    statement: |
      SELECT document\_id, layer, document\_type, file\_name,
             page\_count, processing\_method, ingested\_at
      FROM `C2-intelligence.C2\_warehouse.documents`
      WHERE project\_id = @project\_id AND status = 'ACTIVE'
      ORDER BY layer, document\_type, file\_name

  get\_project\_summary:
    kind: bigquery-sql
    source: C2-bigquery
    description: Get document and chunk counts for a project by layer
    parameters:
      - name: project\_id
        type: string
        description: The project ID
    statement: |
      SELECT
        d.layer,
        COUNT(DISTINCT d.document\_id) AS document\_count,
        COUNT(c.chunk\_id) AS chunk\_count,
        SUM(d.page\_count) AS total\_pages
      FROM `C2-intelligence.C2\_warehouse.documents` d
      LEFT JOIN `C2-intelligence.C2\_warehouse.chunks` c
        ON d.document\_id = c.document\_id
      WHERE d.project\_id = @project\_id AND d.status = 'ACTIVE'
      GROUP BY d.layer
      ORDER BY d.layer

  get\_document\_chunks:
    kind: bigquery-sql
    source: C2-bigquery
    description: Retrieve all chunks for a specific document in order
    parameters:
      - name: document\_id
        type: string
        description: The document ID
    statement: |
      SELECT chunk\_index, chunk\_text, page\_number, section\_ref, token\_count
      FROM `C2-intelligence.C2\_warehouse.chunks`
      WHERE document\_id = @document\_id
      ORDER BY chunk\_index ASC

  get\_user\_projects:
    kind: bigquery-sql
    source: C2-bigquery
    description: Get projects accessible to a user
    parameters:
      - name: user\_id
        type: string
        description: Firebase user ID
    statement: |
      SELECT p.project\_id, p.project\_name, p.client\_name,
             p.contract\_type, p.jurisdiction, pm.role
      FROM `C2-intelligence.C2\_warehouse.project\_members` pm
      JOIN `C2-intelligence.C2\_warehouse.projects` p
        ON pm.project\_id = p.project\_id
      WHERE pm.user\_id = @user\_id AND p.is\_active = TRUE
      ORDER BY p.project\_name

  write\_audit\_log:
    kind: bigquery-sql
    source: C2-bigquery
    description: Write an audit log entry
    parameters:
      - name: log\_id
        type: string
      - name: project\_id
        type: string
      - name: session\_id
        type: string
      - name: user\_id
        type: string
      - name: user\_email
        type: string
      - name: action
        type: string
      - name: domain
        type: string
      - name: query\_text
        type: string
      - name: chunks\_retrieved
        type: integer
      - name: model\_used
        type: string
      - name: latency\_ms
        type: integer
    statement: |
      INSERT INTO `C2-intelligence.C2\_warehouse.audit\_log`
        (log\_id, project\_id, session\_id, user\_id, user\_email, action,
         domain, query\_text, chunks\_retrieved, model\_used, latency\_ms)
      VALUES
        (@log\_id, @project\_id, @session\_id, @user\_id, @user\_email, @action,
         @domain, @query\_text, @chunks\_retrieved, @model\_used, @latency\_ms)

  list\_all\_projects:
    kind: bigquery-sql
    source: C2-bigquery
    description: List all active projects (admin/verification use)
    parameters: \[]
    statement: |
      SELECT project\_id, project\_name, client\_name, jurisdiction, created\_at
      FROM `C2-intelligence.C2\_warehouse.projects`
      WHERE is\_active = TRUE
      ORDER BY created\_at DESC

toolsets:
  C2-retrieval:
    - list\_project\_documents
    - get\_project\_summary
    - get\_document\_chunks
    - get\_user\_projects

  C2-write:
    - write\_audit\_log

  C2-admin:
    - list\_all\_projects
    - get\_project\_summary
    - list\_project\_documents

  C2-all:
    - list\_project\_documents
    - get\_project\_summary
    - get\_document\_chunks
    - get\_user\_projects
    - write\_audit\_log
    - list\_all\_projects
```

### Task 2.2 — Build MCP Toolbox Docker image

```dockerfile
FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.31.0
COPY tools.yaml /app/tools.yaml
```

### Task 2.3 — Deploy MCP Toolbox to Cloud Run

```bash
gcloud run deploy C2-toolbox \\
  --image gcr.io/C2-intelligence/C2-toolbox:latest \\
  --region me-central1 \\
  --service-account C2-toolbox@C2-intelligence.iam.gserviceaccount.com \\
  --no-allow-unauthenticated \\
  --min-instances 1 \\
  --port 8080
```

### Task 2.4 — Configure OAuth for Claude.ai connector

1. Create OAuth 2.0 Client ID in GCP console (Web application type)
2. Add Claude.ai as an authorized redirect URI
3. Store client ID and secret in Secret Manager
4. Add MCP Toolbox Cloud Run URL as custom connector in Claude.ai settings
5. Authenticate using Google OAuth

### Task 2.5 — Verify Claude Chat can query BigQuery

Claude Chat calls `list\_all\_projects` and `get\_project\_summary` via the MCP connector.
**This is the verification gate. Build does not proceed until Claude Chat independently confirms BigQuery access.**

\---

## Phase 3 — Ingestion Pipeline

### Task 3.1 — Write ingestion service (two-path PDF handling)

```python
# ingestion/pipeline.py

import fitz  # PyMuPDF
import google.cloud.documentai as documentai
from vertexai.language\_models import TextEmbeddingModel
from google.cloud import bigquery
import uuid, re, tiktoken

EMBEDDING\_MODEL = "text-embedding-004"
EMBEDDING\_DIMS = 768
CHUNK\_TARGET\_TOKENS = 500
CHUNK\_OVERLAP\_TOKENS = 50
CLAUSE\_PATTERN = re.compile(r'^(\\d+\\.\[\\d\\.]\*)\\s+')  # matches "8.4.1 "

def detect\_pdf\_type(gcs\_uri: str) -> str:
    """Returns DIGITAL or SCANNED based on whether PDF has native text."""
    # Download first page, check if fitz extracts >50 chars of text
    # Returns 'DIGITAL' or 'SCANNED'

def extract\_text\_pymupdf(gcs\_uri: str) -> list\[dict]:
    """Extract text page by page using PyMuPDF. GCC-native, no external API."""
    # Returns list of {page\_number, text}

def extract\_text\_documentai(gcs\_uri: str, project\_id: str) -> list\[dict]:
    """Extract text using Document AI OCR via eu endpoint. Flags as EXTERNAL\_OCR."""
    # Uses eu endpoint explicitly: 'eu-documentai.googleapis.com'
    # Returns list of {page\_number, text}

def chunk\_text(pages: list\[dict], document\_type: str) -> list\[dict]:
    """
    Chunk text with strategy based on document type.
    - CONTRACT: clause-aware chunking (detect numbered clauses, break at boundaries)
    - CORRESPONDENCE/PROGRAMME/OTHER: paragraph/page-aware chunking
    Always: include page reference in each chunk, max 600 tokens, min 50
    Returns list of {chunk\_index, chunk\_text, page\_number, section\_ref, token\_count}
    """
    enc = tiktoken.get\_encoding("cl100k\_base")
    # ... clause detection for CONTRACT type ...

def generate\_embeddings(texts: list\[str]) -> list\[list\[float]]:
    """Generate embeddings. Validates 768 dims. Batches to avoid quota."""
    model = TextEmbeddingModel.from\_pretrained(EMBEDDING\_MODEL)
    # Process in batches of 5 (Vertex AI quota)
    # Validate: assert len(embedding) == EMBEDDING\_DIMS for each
    # Returns list of 768-element float arrays

def ingest\_document(
    project\_id: str,
    layer: str,
    document\_type: str,
    gcs\_uri: str,
    file\_name: str
) -> dict:
    run\_id = str(uuid.uuid4())
    document\_id = str(uuid.uuid4())

    # Step 1: Detect PDF type
    pdf\_type = detect\_pdf\_type(gcs\_uri)
    processing\_method = 'GCC\_NATIVE' if pdf\_type == 'DIGITAL' else 'EXTERNAL\_OCR'

    # Step 2: Extract text
    if pdf\_type == 'DIGITAL':
        pages = extract\_text\_pymupdf(gcs\_uri)
    else:
        pages = extract\_text\_documentai(gcs\_uri, 'C2-intelligence')

    # Step 3: Chunk
    chunks = chunk\_text(pages, document\_type)

    # Step 4: Embed (batch)
    texts = \[c\['chunk\_text'] for c in chunks]
    embeddings = generate\_embeddings(texts)

    # Step 5: Write document record
    bq = bigquery.Client()
    # INSERT into documents table...

    # Step 6: Batch insert chunks with embeddings
    rows = \[
        {
            'chunk\_id': str(uuid.uuid4()),
            'document\_id': document\_id,
            'project\_id': project\_id,
            'layer': layer,
            'chunk\_index': c\['chunk\_index'],
            'chunk\_text': c\['chunk\_text'],
            'page\_number': c\['page\_number'],
            'section\_ref': c.get('section\_ref'),
            'embedding': embeddings\[i],
            'token\_count': c\['token\_count']
        }
        for i, c in enumerate(chunks)
    ]
    bq.insert\_rows\_json('C2-intelligence.C2\_warehouse.chunks', rows)

    return {'document\_id': document\_id, 'chunk\_count': len(chunks),
            'processing\_method': processing\_method, 'run\_id': run\_id}
```

### Task 3.2 — Document AI processor setup (eu region)

```bash
# Create OCR processor in EU (not GCC — only option)
gcloud documentai processors create \\
  --location=eu \\
  --type=DOCUMENT\_OCR \\
  --display-name="C2-ocr-processor"
```

Store processor ID in Secret Manager. All scanned document processing will use the EU endpoint.

### Task 3.3 — Deploy ingestion service to Cloud Run

```bash
gcloud run deploy C2-ingestion \\
  --source . \\
  --region me-central1 \\
  --service-account C2-ingestion@C2-intelligence.iam.gserviceaccount.com \\
  --no-allow-unauthenticated \\
  --cpu 2 --memory 4Gi \\
  --timeout 900 \\
  --min-instances 0
```

### Task 3.4 — End-to-end ingestion test (digital PDF)

Upload a test PDF (FIDIC clause extract) to `C2-documents-l1`.
Call ingestion endpoint.
**Verification:** Claude Chat queries `C2\_warehouse.chunks` via MCP Toolbox — confirms rows, embedding array length = 768, section\_ref populated for CONTRACT type.

### Task 3.5 — Create vector index (after first data batch)

```sql
-- Only run after confirming chunks table has data
CREATE VECTOR INDEX IF NOT EXISTS chunks\_embedding\_idx
ON `C2-intelligence.C2\_warehouse.chunks`(embedding)
OPTIONS (
  index\_type = 'IVF',
  distance\_type = 'COSINE',
  ivf\_options = '{"num\_lists": 100}'
);
```

**Note:** Index requires \~5,000+ rows to be useful. If table has fewer rows, BigQuery uses brute force automatically — this is fine at prototype stage.

### Task 3.6 — Ingest L2b standards layer

Upload and ingest the following reference documents to `C2-documents-l2b` (project\_id = `GLOBAL\_STANDARDS`):

* FIDIC Red Book 1999 (Conditions of Contract for Construction)
* FIDIC Red Book 2017
* FIDIC Yellow Book 2017 (Plant and Design-Build)
* FIDIC Silver Book 2017 (EPC/Turnkey)
* SCL Protocol 2nd Edition 2017
* AACE RP 29R-03

These are document\_type = `STANDARD`. Layer = `L2B`. No project scope — accessible across all projects.

**Verification:** Claude Chat confirms all 6 documents appear in `list\_project\_documents` for project GLOBAL\_STANDARDS, with expected chunk counts.

\---

## Phase 4 — API + Agent Layer (single Cloud Run service)

**Architecture decision:** C2-api is one service. It exposes HTTP endpoints AND contains the agent logic as Python modules. No inter-service calls.

### Agent execution flow (for all four domain agents)

```
User query → API endpoint
→ Validate Firebase JWT → extract user\_id
→ Check project\_members (BigQuery via direct query) → confirm access
→ Generate query embedding (Vertex AI text-embedding-004)
→ VECTOR\_SEARCH in BigQuery (Python BQ client, returns top 8 chunks + L2b chunks)
→ Build grounded prompt with retrieved chunks as evidence
→ Call Claude on Vertex AI (SSE streaming)
→ Stream response tokens back to React client
→ Write audit log via MCP Toolbox
```

### Task 4.1 — Vector search implementation in Python

```python
from google.cloud import bigquery
import vertexai
from vertexai.language\_models import TextEmbeddingModel

def embed\_query(text: str) -> list\[float]:
    model = TextEmbeddingModel.from\_pretrained("text-embedding-004")
    result = model.get\_embeddings(\[text])
    embedding = result\[0].values
    assert len(embedding) == 768, f"Expected 768 dims, got {len(embedding)}"
    return embedding

def vector\_search(
    query\_embedding: list\[float],
    project\_id: str,
    layer\_filter: str = "ALL",
    top\_k: int = 8
) -> list\[dict]:
    """
    Direct BigQuery Python client call. Not via MCP Toolbox.
    Returns top\_k chunks from project + top 4 L2b standard chunks.
    """
    bq = bigquery.Client(project="C2-intelligence")

    # Convert embedding to BigQuery ARRAY literal
    embedding\_literal = "\[" + ",".join(str(v) for v in query\_embedding) + "]"

    query = f"""
    WITH project\_results AS (
      SELECT
        base.chunk\_id, base.chunk\_text, base.layer, base.page\_number,
        base.section\_ref, base.document\_id, distance
      FROM VECTOR\_SEARCH(
        TABLE `C2-intelligence.C2\_warehouse.chunks`,
        'embedding',
        (SELECT {embedding\_literal} AS embedding),
        top\_k => @top\_k,
        distance\_type => 'COSINE'
      )
      WHERE base.project\_id = @project\_id
        AND base.layer != 'L2B'
        AND (@layer\_filter = 'ALL' OR base.layer = @layer\_filter)
    ),
    standards\_results AS (
      SELECT
        base.chunk\_id, base.chunk\_text, base.layer, base.page\_number,
        base.section\_ref, base.document\_id, distance
      FROM VECTOR\_SEARCH(
        TABLE `C2-intelligence.C2\_warehouse.chunks`,
        'embedding',
        (SELECT {embedding\_literal} AS embedding),
        top\_k => 4,
        distance\_type => 'COSINE'
      )
      WHERE base.project\_id = 'GLOBAL\_STANDARDS'
        AND base.layer = 'L2B'
    )
    SELECT r.\*, d.file\_name, d.document\_type
    FROM (SELECT \* FROM project\_results UNION ALL SELECT \* FROM standards\_results) r
    JOIN `C2-intelligence.C2\_warehouse.documents` d ON r.document\_id = d.document\_id
    WHERE d.status = 'ACTIVE'
    ORDER BY r.distance ASC
    """

    job\_config = bigquery.QueryJobConfig(
        query\_parameters=\[
            bigquery.ScalarQueryParameter("project\_id", "STRING", project\_id),
            bigquery.ScalarQueryParameter("layer\_filter", "STRING", layer\_filter),
            bigquery.ScalarQueryParameter("top\_k", "INT64", top\_k),
        ]
    )
    results = bq.query(query, job\_config=job\_config).result()
    return \[dict(row) for row in results]
```

### Task 4.2 — Main orchestrator (deterministic routing, no LLM call)

```python
DOMAIN\_KEYWORDS = {
    'legal': \['contract', 'clause', 'fidic', 'dispute', 'dab', 'daab', 'termination',
              'breach', 'notice', 'engineer', 'claim', 'liability', 'indemnity',
              'arbitration', 'particular conditions', 'time at large', 'force majeure',
              'suspension', 'taking-over', 'defects notification'],
    'commercial': \['eot', 'extension of time', 'delay', 'prolongation', 'disruption',
                   'variation', 'compensation event', 'programme', 'critical path',
                   'concurrent delay', 'float', 'acceleration', 'scl protocol',
                   'baseline programme', 'as-built programme'],
    'financial': \['evm', 'earned value', 'cpi', 'spi', 'eac', 'etc', 'vac', 'cost control',
                  'budget', 'forecast', 'cash flow', 'valuation', 'payment certificate',
                  'retention', 'final account', 'reconciliation', 'cost to complete'],
    'technical': \['ncr', 'itp', 'defect', 'snag', 'inspection', 'test',
                  'specification', 'method statement', 'rfi', 'submittal',
                  'decennial', 'latent defect', 'workmanship', 'material approval']
}

def route\_query(query: str) -> list\[str]:
    query\_lower = query.lower()
    matched = \[domain for domain, keywords in DOMAIN\_KEYWORDS.items()
               if any(kw in query\_lower for kw in keywords)]
    return matched if matched else \['legal']  # default to legal for unmatched queries
```

### Task 4.3 — Domain agent prompts

**Legal agent system prompt:**

```
You are a construction law specialist analysing project documents under FIDIC and GCC jurisdiction.

GROUNDING RULES — NON-NEGOTIABLE:
1. Every legal position must cite a specific clause number from the retrieved document chunks
2. Characterise FIDIC clause obligations precisely — do not paraphrase loosely
3. State explicitly whether the clause is from General Conditions or Particular Conditions
4. CANNOT ASSESS is mandatory when the retrieved chunks do not contain sufficient evidence
5. Apply the correct jurisdiction: UAE Civil Code Art. 880 (decennial), KSA Civil Transactions Law, or Qatar Civil Code as applicable to the project
6. FIDIC hierarchy: Particular Conditions prevail over General Conditions
7. Never state a legal position on facts not in the document record

FORMAT: State your analysis, then list citations as \[Document Name, Page X, Clause Y].
If CANNOT ASSESS: state which specific evidence is missing.
```

**Commercial agent system prompt:**

```
You are a construction claims and delay analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. EOT analysis must reference programme evidence from the retrieved chunks
2. Identify the delay category explicitly: Employer Risk Event / Contractor Risk Event / Concurrent Delay
3. Prolongation cost methodology must follow SCL Protocol 2nd Edition 2017
4. Disruption requires contemporaneous record evidence — productivity records, method statements
5. Float ownership must be addressed where relevant
6. CANNOT ASSESS if programme baseline, as-built records, or contemporaneous evidence is absent
7. Apply AACE RP 29R-03 for cost methodology where referenced

FORMAT: State analysis, cite programme and correspondence evidence, identify SCL or AACE reference applied.
```

**Financial agent system prompt:**

```
You are a construction financial analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. EVM metrics (CPI, SPI, EAC, ETC, VAC) must be calculated from figures in the retrieved chunks
2. Show calculations explicitly — do not state a metric without showing the source numbers
3. Final account reconciliation must cite specific payment certificates and contract documents
4. Flag discrepancies between contract sum, certified amounts, and forecast final cost
5. CANNOT ASSESS if the required financial records are not in the document warehouse
6. Do not interpolate or estimate missing financial data

FORMAT: Present calculations in tables. Cite source document and page for every figure.
```

**Technical agent system prompt:**

```
You are a construction technical analyst.

GROUNDING RULES — NON-NEGOTIABLE:
1. NCR analysis must identify the specific ITP hold/witness point or specification clause breached
2. Defect characterisation requires a specification baseline from the retrieved chunks
3. Apply UAE Civil Code Art. 880 for structural defects with 10-year liability period
4. RFI and submittal analysis must be based on actual register entries in the document record
5. CANNOT ASSESS if the relevant specification, ITP, or inspection records are absent
6. Never characterise a defect as critical without a specification requirement to measure against

FORMAT: Cite ITP, specification clause, or NCR reference for each finding.
```

### Task 4.4 — Session management

```python
def create\_session(project\_id: str, user\_id: str, domain: str) -> str:
    session\_id = str(uuid.uuid4())
    bq = bigquery.Client()
    bq.insert\_rows\_json('C2-intelligence.C2\_warehouse.query\_sessions', \[{
        'session\_id': session\_id,
        'project\_id': project\_id,
        'user\_id': user\_id,
        'domain': domain,
        'expires\_at': (datetime.utcnow() + timedelta(hours=4)).isoformat(),
        'context\_json': '\[]'
    }])
    return session\_id

def get\_session\_context(session\_id: str) -> list\[dict]:
    """Returns last 10 turns from context\_json."""
    ...

def update\_session\_context(session\_id: str, turn: dict):
    """Appends turn to context, trims to last 10, updates last\_active\_at."""
    ...
```

### Task 4.5 — API endpoints with SSE streaming

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sse\_starlette.sse import EventSourceResponse
import anthropic  # for calling Claude on Vertex AI

app = FastAPI()

@app.post("/api/v1/query")
async def query(request: QueryRequest, user=Depends(verify\_firebase\_jwt)):
    # 1. Verify project access
    if not user\_has\_project\_access(user.uid, request.project\_id):
        raise HTTPException(403)

    # 2. Route to domain(s)
    domains = route\_query(request.query)

    # 3. Generate embedding
    embedding = embed\_query(request.query)

    # 4. Vector search
    chunks = vector\_search(embedding, request.project\_id, top\_k=8)

    # 5. Build prompt
    prompt = build\_grounded\_prompt(request.query, chunks, domains\[0])

    # 6. Stream Claude response via SSE
    async def generate():
        async with anthropic\_vertex\_client.messages.stream(
            model=CLAUDE\_MODEL\_ID,
            max\_tokens=4096,
            system=AGENT\_SYSTEM\_PROMPTS\[domains\[0]],
            messages=\[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text\_stream:
                yield {"data": text}

        # After stream completes, write audit log
        await write\_audit\_log(...)

    return EventSourceResponse(generate())

@app.post("/api/v1/ingest")
async def ingest(request: IngestRequest, user=Depends(verify\_firebase\_jwt)):
    # Trigger ingestion service (HTTP call to C2-ingestion on Cloud Run)
    ...

@app.get("/api/v1/projects")
async def get\_projects(user=Depends(verify\_firebase\_jwt)):
    # Query project\_members via BigQuery Python client
    ...

@app.get("/api/v1/project/{project\_id}/documents")
async def get\_documents(project\_id: str, user=Depends(verify\_firebase\_jwt)):
    ...

@app.get("/api/v1/audit/{project\_id}")
async def get\_audit\_log(project\_id: str, user=Depends(verify\_firebase\_jwt)):
    ...
```

### Task 4.6 — Deploy C2-api to Cloud Run

```bash
gcloud run deploy C2-api \\
  --source . \\
  --region me-central1 \\
  --service-account C2-api@C2-intelligence.iam.gserviceaccount.com \\
  --no-allow-unauthenticated \\
  --cpu 2 --memory 2Gi \\
  --min-instances 1 \\
  --set-env-vars CLAUDE\_MODEL\_ID=<locked-model-id>,GCP\_PROJECT=C2-intelligence
```

**Verification:** Claude Chat calls `/api/v1/projects` and `/api/v1/query` (with test project) via direct HTTP and confirms grounded response with citations, CANNOT ASSESS returned on insufficient evidence, and SSE stream received.

\---

## Phase 5 — React Front End

### Tech stack

```bash
npm create vite@latest C2-intelligence -- --template react-ts
npm install @tanstack/react-query firebase axios tailwindcss react-router-dom
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-toast
```

### Task 5.1 — Auth: Google Sign-In via Firebase

### Task 5.2 — Project selector screen

### Task 5.3 — Document upload screen

* Detect PDF type client-side (show warning if scanned: "This document will be processed via EU OCR. Construction document content will leave GCC temporarily for text extraction.")
* Upload to Cloud Storage via signed URL
* Trigger `/api/v1/ingest`
* Show processing status

### Task 5.4 — Query interface (core screen)

* Multi-turn conversation UI
* SSE consumption via EventSource or `@microsoft/fetch-event-source`
* Streaming token display (same UX as Claude.ai chat)
* Domain badge per response
* Expandable citations panel: source chunk text, document name, page, clause reference
* CANNOT ASSESS displayed prominently in red with missing evidence stated

### Task 5.5 — Audit trail screen

* Table of all queries for a project
* Filter by date, domain, action
* Export to CSV

### Task 5.6 — Deploy to Vercel

* Root dir: `frontend/`
* Set CORS in C2-api to match Vercel deployment domain (lock after first deployment)

\---

## Phase 6 — Governance and Security

### Task 6.1 — API-layer project authorization (replaces BigQuery RLS)

```python
@lru\_cache(maxsize=1000)
def get\_user\_project\_ids(user\_id: str) -> list\[str]:
    """
    Cached. Invalidated after 5 minutes.
    Queries project\_members table via BigQuery Python client.
    Returns list of project\_id strings the user can access.
    """
    bq = bigquery.Client()
    results = bq.query(
        "SELECT project\_id FROM C2\_warehouse.project\_members WHERE user\_id = @uid",
        job\_config=bigquery.QueryJobConfig(
            query\_parameters=\[bigquery.ScalarQueryParameter("uid", "STRING", user\_id)]
        )
    ).result()
    return \[row.project\_id for row in results]

def user\_has\_project\_access(user\_id: str, project\_id: str) -> bool:
    return project\_id in get\_user\_project\_ids(user\_id)
```

### Task 6.2 — Model Armor

```bash
gcloud services enable modelarmor.googleapis.com --project=C2-intelligence

gcloud model-armor floorsettings update \\
  --full-uri='projects/C2-intelligence/locations/global/floorSetting' \\
  --mcp-sanitization=ENABLED \\
  --malicious-uri-filter-settings-enforcement=ENABLED \\
  --pi-and-jailbreak-filter-settings-enforcement=ENABLED \\
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM\_AND\_ABOVE
```

### Task 6.3 — BigQuery cost control

```sql
-- Set max bytes billed per query: 100 GB
ALTER PROJECT `C2-intelligence`
SET OPTIONS (max\_bytes\_billed = 107374182400);
```

Set GCP billing alert at $100/month threshold.

\---

## Phase 7 — Governing Documents

### Task 7.1 — CLAUDE.md (final version)

### Task 7.2 — BUILD\_LOG.md (running log from session start)

### Task 7.3 — C2\_MASTER\_PLAN.md (architecture decisions and rationale)

\---

## Scope Boundary — v1.0 vs v1.1

|Feature|v1.0|v1.1|
|-|-|-|
|Interactive Q\&A with citations|✓||
|SSE streaming responses|✓||
|Document upload and ingestion|✓||
|Four domain agents with FIDIC grounding|✓||
|Audit trail|✓||
|L2b standards reference layer|✓||
|Multi-turn sessions|✓||
|Automated report generation||✓|
|Multi-project comparison||✓|
|Mobile-optimised UI||✓|
|CMEK / Customer-managed encryption||✓|

\---

## Pre-Build Checklist

* \[ ] GCP account active with billing enabled
* \[ ] `gcloud` CLI installed on Yasser's machine and authenticated
* \[ ] Claude Code installed on Yasser's machine
* \[ ] MCP Toolbox binary downloaded locally **for tools.yaml testing only** — production runs on Cloud Run
* \[ ] Firebase project created
* \[ ] Vercel account connected to GitHub
* \[ ] FIDIC Red/Yellow/Silver 1999 and 2017 PDFs available for L2b ingestion
* \[ ] SCL Protocol 2nd Edition 2017 PDF available
* \[ ] AACE RP 29R-03 PDF available
* \[ ] Phase 0 Task 0.1 completed before any other task begins

\---

## Execution Rules (unchanged from v1.0)

1. One task per commit. No batching.
2. QG PASS required before next task.
3. QG PASS = Claude Chat independently verifies via MCP Toolbox or gcloud CLI output.
4. No self-reporting.
5. Yasser approves each commit before Claude Code proceeds.
6. Claude Code always runs `git pull` before any work. Never clones.
7. Secrets in Secret Manager only. Never hardcoded.
8. Region: per decision in Phase 0 Task 0.1.
9. API versioned at `/api/v1/`.
10. Claude model string locked in Phase 0. Never `@latest`.

\---

*End of C2 Intelligence Build Plan v2.0*

