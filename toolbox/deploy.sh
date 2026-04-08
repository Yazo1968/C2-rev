#!/usr/bin/env bash
# Task 2.3 — Deploy MCP Toolbox to Cloud Run.
# Verification gate: after this passes, register the service URL as a custom
# MCP connector at claude.ai (Task 2.4) and have Claude Chat call
# list_all_projects to confirm BigQuery access (Task 2.5). Phase 3 does not
# begin until that PASS is recorded.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
REGION="${REGION:-me-central1}"
IMAGE="${IMAGE:-gcr.io/${PROJECT}/c2-toolbox:latest}"

cd "$(dirname "$0")"

echo "==> Building image ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT}" .

echo "==> Deploying c2-toolbox to Cloud Run in ${REGION}"
gcloud run deploy c2-toolbox \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --service-account "c2-toolbox@${PROJECT}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --min-instances 1 \
  --port 8080 \
  --project "${PROJECT}"

echo "==> Service URL"
gcloud run services describe c2-toolbox --region "${REGION}" --format='value(status.url)'
