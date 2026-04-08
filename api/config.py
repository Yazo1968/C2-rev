"""Locked configuration constants for c2-api.

All values are read from the environment with safe defaults that match
the rest of the build. Secrets (Claude model id, OAuth client) come from
Secret Manager — never hardcoded here.
"""

from __future__ import annotations

import os

GCP_PROJECT = os.environ.get("GCP_PROJECT", "c2-intelligence")
DATASET = os.environ.get("BQ_DATASET", "c2_warehouse")
REGION_VERTEX = os.environ.get("REGION_VERTEX", "me-central1")  # may be europe-west4 if split

# Claude model id MUST be injected at deploy time from Secret Manager.
# We refuse to start with @latest to enforce the rule from CLAUDE.md.
CLAUDE_MODEL_ID = os.environ.get("CLAUDE_MODEL_ID", "")
if CLAUDE_MODEL_ID.endswith("@latest"):
    raise RuntimeError("CLAUDE_MODEL_ID must be a pinned version, not @latest")

# c2-toolbox URL for audit log writes.
TOOLBOX_URL = os.environ.get("TOOLBOX_URL", "")

# CORS — locked to the Vercel deployment domain after Phase 5.6.
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Embedding settings (must match ingestion/pipeline.py).
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768
