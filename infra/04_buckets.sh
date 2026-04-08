#!/usr/bin/env bash
# Task 0.5 — Create Cloud Storage buckets.
# Bucket names must be globally unique. If these collide, set BUCKET_PREFIX
# to something like "${PROJECT}-" and rerun.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"
REGION="${REGION:-me-central1}"     # locked from Task 0.1
BUCKET_PREFIX="${BUCKET_PREFIX:-}"

L1="gs://${BUCKET_PREFIX}c2-documents-l1"
L2A="gs://${BUCKET_PREFIX}c2-documents-l2a"
L2B="gs://${BUCKET_PREFIX}c2-documents-l2b"

gcloud config set project "${PROJECT}"

gcloud storage buckets create "${L1}"  --location="${REGION}" --uniform-bucket-level-access
gcloud storage buckets create "${L2A}" --location="${REGION}" --uniform-bucket-level-access
gcloud storage buckets create "${L2B}" --location="${REGION}" --uniform-bucket-level-access

echo "==> Verifying buckets"
gcloud storage buckets list --filter="name:${BUCKET_PREFIX}c2-documents-*"
