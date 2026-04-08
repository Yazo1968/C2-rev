-- Task 1.5 — Create chunks table.
-- Vector index is NOT created here. It is created in Phase 3 (file 09)
-- AFTER the first data batch is ingested. CREATE VECTOR INDEX on an empty
-- table fails.
CREATE TABLE `c2-intelligence.c2_warehouse.chunks` (
  chunk_id        STRING NOT NULL,
  document_id     STRING NOT NULL,
  project_id      STRING NOT NULL,
  layer           STRING NOT NULL,
  chunk_index     INT64 NOT NULL,
  chunk_text      STRING NOT NULL,
  page_number     INT64,
  section_ref     STRING,         -- For CONTRACT docs: clause number e.g. "20.1" or "Sub-Clause 8.4"
  embedding       ARRAY<FLOAT64>, -- 768 dimensions, text-embedding-004 (LOCKED)
  token_count     INT64,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(created_at)
CLUSTER BY project_id, layer, document_id;
