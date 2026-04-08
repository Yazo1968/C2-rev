-- Task 1.6 — Create ingestion_runs table.
CREATE TABLE `c2-intelligence.c2_warehouse.ingestion_runs` (
  run_id            STRING NOT NULL,
  project_id        STRING NOT NULL,
  document_id       STRING,
  gcs_uri           STRING,
  started_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  completed_at      TIMESTAMP,
  status            STRING,  -- RUNNING, COMPLETE, FAILED
  chunks_created    INT64,
  processing_method STRING,
  error_message     STRING,
  retry_count       INT64 DEFAULT 0
);
