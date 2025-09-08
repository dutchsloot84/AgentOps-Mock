#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-agentops-mock}"

AGENT_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "AGENT_URL=$AGENT_URL"

echo "== /healthz =="
curl -fsS "$AGENT_URL/healthz" && echo

echo "== /chat (RAG) =="
curl -fsS -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"What are the key steps in our release audit checklist?"}' && echo

echo "== UI =="
echo "$AGENT_URL/ui/index.html"
