-- Task 1.8 — Create query_sessions table.
-- Multi-turn context store. expires_at = started_at + 4 hours.
-- context_json holds last 10 turns serialised; trimmed by api/sessions.py.
CREATE TABLE `c2-intelligence.c2_warehouse.query_sessions` (
  session_id      STRING NOT NULL,
  project_id      STRING NOT NULL,
  user_id         STRING NOT NULL,
  started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  last_active_at  TIMESTAMP,
  turn_count      INT64 DEFAULT 0,
  domain          STRING,
  expires_at      TIMESTAMP,  -- started_at + 4 hours
  context_json    STRING       -- last 10 turns serialised as JSON
);
