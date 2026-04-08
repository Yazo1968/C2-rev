#!/usr/bin/env bash
# Task 4.6 — Deploy c2-api to Cloud Run.
# Required env at deploy time:
#   CLAUDE_MODEL_ID  — exact pinned model id, never @latest
#   TOOLBOX_URL      — URL printed by toolbox/deploy.sh
#   INGESTION_URL    — URL printed by ingestion/deploy.sh
#   CORS_ORIGIN      — Vercel deployment domain (set after Phase 5.6)
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
REGION="${REGION:-me-central1}"
REGION_VERTEX="${REGION_VERTEX:-me-central1}"
CLAUDE_MODEL_ID="${CLAUDE_MODEL_ID:?CLAUDE_MODEL_ID must be set (no @latest)}"
TOOLBOX_URL="${TOOLBOX_URL:?TOOLBOX_URL must be set}"
INGESTION_URL="${INGESTION_URL:?INGESTION_URL must be set}"
CORS_ORIGIN="${CORS_ORIGIN:-}"

if [[ "${CLAUDE_MODEL_ID}" == *"@latest" ]]; then
  echo "ERROR: CLAUDE_MODEL_ID must be a pinned version, not @latest" >&2
  exit 1
fi

cd "$(dirname "$0")"

gcloud run deploy c2-api \
  --source . \
  --region "${REGION}" \
  --service-account "c2-api@${PROJECT}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --cpu 2 --memory 2Gi \
  --min-instances 1 \
  --set-env-vars "GCP_PROJECT=${PROJECT},REGION_VERTEX=${REGION_VERTEX},CLAUDE_MODEL_ID=${CLAUDE_MODEL_ID},TOOLBOX_URL=${TOOLBOX_URL},INGESTION_URL=${INGESTION_URL},CORS_ALLOWED_ORIGINS=${CORS_ORIGIN}" \
  --project "${PROJECT}"

echo "==> Service URL"
gcloud run services describe c2-api --region "${REGION}" --format='value(status.url)'
