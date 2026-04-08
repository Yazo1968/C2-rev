#!/usr/bin/env bash
# Task 0.1 — Verify GCP service availability and lock region.
# MUST be the first thing run in this build. Records nothing — operator
# transcribes results into CLAUDE.md and decides single-region vs split.
#
# Decision gate:
#   - If Vertex AI + Claude available in me-central1 → all resources in me-central1
#   - If Vertex AI NOT available in me-central1 → BigQuery + Cloud Storage + Cloud
#     Run in me-central1; Vertex AI in europe-west4; document the split in CLAUDE.md.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
TARGET_REGION="${TARGET_REGION:-me-central1}"
FALLBACK_REGION="${FALLBACK_REGION:-europe-west4}"

echo "==> Verifying service availability for project=${PROJECT} target=${TARGET_REGION}"
echo

echo "--- BigQuery API availability ---"
gcloud services list --available --filter="name:bigquery.googleapis.com" --format="value(name)"
echo

echo "--- Cloud Run regions including ${TARGET_REGION} ---"
gcloud run regions list --format="value(locationId)" | grep -F "${TARGET_REGION}" || {
  echo "WARN: Cloud Run not available in ${TARGET_REGION}" >&2
}
echo

echo "--- Vertex AI (aiplatform) regions including ${TARGET_REGION} ---"
# aiplatform region list is not exposed; check by attempting a no-op describe.
if gcloud ai models list --region="${TARGET_REGION}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "Vertex AI: available in ${TARGET_REGION}"
  VERTEX_REGION="${TARGET_REGION}"
else
  echo "Vertex AI: NOT available in ${TARGET_REGION} — will fall back to ${FALLBACK_REGION}"
  VERTEX_REGION="${FALLBACK_REGION}"
fi
echo

echo "--- Claude model availability on Vertex AI in ${VERTEX_REGION} ---"
echo "Operator: open https://console.cloud.google.com/vertex-ai/model-garden"
echo "  - Filter by Anthropic"
echo "  - Confirm Claude is available in region: ${VERTEX_REGION}"
echo "  - Note the EXACT model id (e.g. claude-sonnet-4-5@20251015) — never @latest"
echo

echo "==> RECORD IN CLAUDE.md:"
cat <<EOF
REGION_BIGQUERY=${TARGET_REGION}
REGION_CLOUD_RUN=${TARGET_REGION}
REGION_VERTEX_AI=${VERTEX_REGION}
REGION_DOCUMENT_AI=eu
SPLIT_REGIONS=$([ "${VERTEX_REGION}" = "${TARGET_REGION}" ] && echo NO || echo YES)
DECISION_DATE=$(date +%Y-%m-%d)
EOF
