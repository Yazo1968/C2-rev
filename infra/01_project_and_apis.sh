#!/usr/bin/env bash
# Task 0.2 — Create GCP project and enable APIs.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"

echo "==> Creating project ${PROJECT}"
gcloud projects create "${PROJECT}" --name="C2 Intelligence" || \
  echo "Project ${PROJECT} already exists — continuing"

gcloud config set project "${PROJECT}"

echo "==> Enabling APIs"
gcloud services enable \
  bigquery.googleapis.com \
  bigquerystorage.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  firebase.googleapis.com

echo "==> Verifying enabled APIs"
gcloud services list --enabled \
  --filter="name:(bigquery OR aiplatform OR documentai OR run OR storage OR secretmanager OR iam OR cloudresourcemanager OR firebase)" \
  --format="table(config.name)"
