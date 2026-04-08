#!/usr/bin/env bash
# Task 6.2 — Model Armor floor settings.
# Enables MCP sanitization, malicious URI filtering, and PI/jailbreak filter
# at MEDIUM_AND_ABOVE confidence at the project floor — applies to every
# downstream model invocation regardless of caller.
set -euo pipefail

PROJECT="${PROJECT:-c2-intelligence}"

gcloud services enable modelarmor.googleapis.com --project="${PROJECT}"

gcloud model-armor floorsettings update \
  --full-uri="projects/${PROJECT}/locations/global/floorSetting" \
  --mcp-sanitization=ENABLED \
  --malicious-uri-filter-settings-enforcement=ENABLED \
  --pi-and-jailbreak-filter-settings-enforcement=ENABLED \
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM_AND_ABOVE
