-- Task 1.2 — Create projects table.
CREATE TABLE `c2-intelligence.c2_warehouse.projects` (
  project_id      STRING NOT NULL,
  project_name    STRING NOT NULL,
  client_name     STRING,
  contract_type   STRING,  -- FIDIC_RED_1999, FIDIC_RED_2017, FIDIC_YELLOW_2017, FIDIC_SILVER_2017, BESPOKE
  jurisdiction    STRING,  -- UAE, KSA, QAT
  currency        STRING DEFAULT 'AED',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by      STRING,
  is_active       BOOL DEFAULT TRUE
);
