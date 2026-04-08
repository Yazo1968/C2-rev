#!/usr/bin/env bash
# Task 0.4 — Grant IAM roles.
#   c2-api       : reads BigQuery, calls Vertex AI, reads secrets
#   c2-ingestion : writes BigQuery, R/W Cloud Storage, calls Vertex AI + Document AI
#   c2-toolbox   : reads BigQuery, writes audit log
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
gcloud config set project "${PROJECT}"

API_SA="c2-api@${PROJECT}.iam.gserviceaccount.com"
ING_SA="c2-ingestion@${PROJECT}.iam.gserviceaccount.com"
TBX_SA="c2-toolbox@${PROJECT}.iam.gserviceaccount.com"

# --- c2-api ---
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${API_SA}" --role="roles/bigquery.dataViewer"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${API_SA}" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${API_SA}" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${API_SA}" --role="roles/secretmanager.secretAccessor"

# --- c2-ingestion ---
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${ING_SA}" --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${ING_SA}" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${ING_SA}" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${ING_SA}" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${ING_SA}" --role="roles/documentai.apiUser"

# --- c2-toolbox ---
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${TBX_SA}" --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${TBX_SA}" --role="roles/bigquery.jobUser"

echo "==> Verifying IAM bindings"
gcloud projects get-iam-policy "${PROJECT}" \
  --flatten="bindings[].members" \
  --format="table(bindings.role,bindings.members)" \
  --filter="bindings.members:c2-*"
