#!/usr/bin/env bash
# Task 0.3 — Create service accounts.
# c2-api          : API + agent layer (collapsed single service)
# c2-ingestion    : ingestion pipeline
# c2-toolbox      : MCP Toolbox
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
gcloud config set project "${PROJECT}"

gcloud iam service-accounts create c2-api \
  --display-name="C2 API and Agent layer"

gcloud iam service-accounts create c2-ingestion \
  --display-name="C2 Document Ingestion"

gcloud iam service-accounts create c2-toolbox \
  --display-name="C2 MCP Toolbox"

echo "==> Verifying service accounts"
gcloud iam service-accounts list --filter="email:c2-*@${PROJECT}.iam.gserviceaccount.com"
