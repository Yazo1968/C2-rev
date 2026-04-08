-- Task 1.4 — Create documents table.
CREATE TABLE `c2-intelligence.c2_warehouse.documents` (
  document_id          STRING NOT NULL,
  project_id           STRING NOT NULL,
  layer                STRING NOT NULL,  -- L1, L2A, L2B
  document_type        STRING,           -- CONTRACT, CORRESPONDENCE, PROGRAMME, POLICY, STANDARD, DRAWING
  file_name            STRING NOT NULL,
  gcs_uri              STRING NOT NULL,
  page_count           INT64,
  processing_method    STRING,           -- GCC_NATIVE (PyMuPDF) or EXTERNAL_OCR (Document AI)
  ingested_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  ingestion_run_id     STRING,
  status               STRING DEFAULT 'ACTIVE'  -- ACTIVE, SUPERSEDED, DELETED
)
PARTITION BY DATE(ingested_at)
CLUSTER BY project_id, layer;
