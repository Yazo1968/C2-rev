#!/usr/bin/env bash
# Task 3.3 — Deploy c2-ingestion to Cloud Run.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
REGION="${REGION:-me-central1}"

cd "$(dirname "$0")"

gcloud run deploy c2-ingestion \
  --source . \
  --region "${REGION}" \
  --service-account "c2-ingestion@${PROJECT}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --cpu 2 --memory 4Gi \
  --timeout 900 \
  --min-instances 0 \
  --set-env-vars "GCP_PROJECT=${PROJECT}" \
  --project "${PROJECT}"

echo "==> Service URL"
gcloud run services describe c2-ingestion --region "${REGION}" --format='value(status.url)'
