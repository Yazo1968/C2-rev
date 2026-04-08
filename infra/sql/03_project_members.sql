-- Task 1.3 — Create project_members table.
-- This replaces BigQuery RLS. Authorization is enforced at the API layer
-- (api/auth.py:user_has_project_access). SESSION_USER() in BigQuery returns
-- the service account, not the Firebase UID, so RLS is unworkable here.
CREATE TABLE `c2-intelligence.c2_warehouse.project_members` (
  project_id   STRING NOT NULL,
  user_id      STRING NOT NULL,  -- Firebase UID
  user_email   STRING,
  role         STRING NOT NULL,  -- OWNER, ANALYST, VIEWER
  added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  added_by     STRING
);
