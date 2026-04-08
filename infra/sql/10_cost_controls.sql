-- Task 6.3 — BigQuery cost control.
-- Set max bytes billed per query at the project level: 100 GB.
-- Combined with the GCP $100/month billing alert (set in console), this
-- provides a hard ceiling on accidental scans.
ALTER PROJECT `c2-intelligence`
SET OPTIONS (max_bytes_billed = 107374182400);
