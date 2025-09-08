#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-agentops-mock}"
LOCATION="${LOCATION:-us-central1}"

echo "== Indexes =="
gcloud ai indexes list --region "$LOCATION"
echo
echo "== Endpoints =="
gcloud ai index-endpoints list --region "$LOCATION"
echo
echo "Tip: describe an endpoint:"
echo "gcloud ai index-endpoints describe <ID> --region $LOCATION | sed -n '1,200p'"
