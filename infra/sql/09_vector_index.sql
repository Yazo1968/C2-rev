-- Task 3.5 — Create vector index AFTER first data batch.
-- Running this on an empty table fails. Run only after Task 3.4 confirms
-- the chunks table has rows. Below ~5000 rows BigQuery falls back to brute
-- force; that's fine at prototype stage.
CREATE VECTOR INDEX IF NOT EXISTS chunks_embedding_idx
ON `c2-intelligence.c2_warehouse.chunks`(embedding)
OPTIONS (
  index_type = 'IVF',
  distance_type = 'COSINE',
  ivf_options = '{"num_lists": 100}'
);
