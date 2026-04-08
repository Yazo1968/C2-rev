-- Task 1.1 — Create dataset.
-- Location must match REGION_BIGQUERY recorded in CLAUDE.md (Task 0.1).
CREATE SCHEMA IF NOT EXISTS `c2-intelligence.c2_warehouse`
OPTIONS (
  location = 'me-central1',
  description = 'C2 Intelligence document warehouse'
);
