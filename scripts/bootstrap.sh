#!/usr/bin/env bash
set -euo pipefail

# ---- CONFIG ----
DEFAULT_REGION="us-central1"
DEFAULT_LOCATION="us-central1"

# ---- CHECKS ----
need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing $1. Please install it and re-run."; exit 1; }; }
need gcloud
need python3
need git

# gh is optional (for auto-create GitHub repo). If missing, we just skip that step.
if ! command -v gh >/dev/null 2>&1; then
  echo "⚠️  GitHub CLI (gh) not found. You can still push manually later."
fi

# ---- INPUT ----
read -rp "GCP Project ID: " PROJECT_ID
read -rp "Region [${DEFAULT_REGION}]: " REGION
REGION=${REGION:-$DEFAULT_REGION}
read -rp "Location for Vertex AI [${DEFAULT_LOCATION}]: " LOCATION
LOCATION=${LOCATION:-$DEFAULT_LOCATION}

# ---- ENV ----
export PROJECT_ID REGION LOCATION

# ---- GCP AUTH + CONFIG ----
echo "
🔐 Logging into GCP (opens browser if needed)..."
gcloud auth login --quiet || true

echo "👤 Application Default Credentials (ADC)..."
gcloud auth application-default login --quiet || true

echo "🛠  Setting project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "✅ Enabling required APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com

# ---- PYTHON DEPS ----
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# ---- GIT INIT ----
if [ ! -d .git ]; then
  echo "🌱 Initializing git repo..."
  git init
  git add .
  git commit -m "chore: bootstrap AgentOps Mock (ADK + MCP + Vector Search)"
fi

# ---- CREATE GITHUB REPO (optional) ----
if command -v gh >/dev/null 2>&1; then
  echo "🐙 Creating GitHub repo (public) via gh..."
  gh repo create agentops-mock --public --source=. --remote=origin --push || true
  # If repo exists already or command fails, fall back to manual push
fi

echo "
✅ Bootstrap complete. Next steps:"
echo "1) Ensure your mock docs exist in mocks/data/docs/*.md"
echo "2) Build and deploy services via Makefile:"
echo "   make deploy-mock && make deploy-tasks && make deploy-claims"
echo "3) Upsert vectors: make upsert"
echo "4) Deploy agent: make deploy-agent"
echo "5) Show URLs: make urls"
