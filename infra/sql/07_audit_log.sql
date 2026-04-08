-- Task 1.7 — Create audit_log table.
-- Written via MCP Toolbox tool `write_audit_log` after every query stream completes.
CREATE TABLE `c2-intelligence.c2_warehouse.audit_log` (
  log_id           STRING NOT NULL,
  project_id       STRING NOT NULL,
  session_id       STRING,
  user_id          STRING,
  user_email       STRING,
  action           STRING NOT NULL,  -- QUERY, INGEST, LOGIN, EXPORT
  domain           STRING,           -- LEGAL, COMMERCIAL, FINANCIAL, TECHNICAL, MULTI
  query_text       STRING,
  chunks_retrieved INT64,
  model_used       STRING,
  latency_ms       INT64,
  logged_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(logged_at)
CLUSTER BY project_id, action;
