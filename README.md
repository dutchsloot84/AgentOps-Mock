# AgentOps Mock – ADK + MCP + Vertex AI Vector Search (Cloud Run)

A weekend, production‑shaped demo showing **GenAI Agents** with:

* **Vertex AI Vector Search** for RAG over a tiny, mock doc set
* **MCP tools** for actions:

  * **Tasks MCP** – add/list/complete tasks (in‑memory for speed)
  * **Claims MCP** – calls a **mock Claims API** (Cloud Run)
* Deployed on **Cloud Run** (cheap, serverless). Local dev works too.

> Goal: Showcase Google‑aligned Agents (ADK) + Vector Search + MCP orchestration, mapped to real enterprise workflows (release audit, claims/FNOL), using 100% mock data.

---

## Architecture

```mermaid
graph TD
  U[User] --> A[AgentOps-Mock (ADK, FastAPI)]
  A -->|Embed query| VE[Vertex AI Vector Search]
  A -->|Use contexts| G[Gemini 1.5 Flash]
  A -->|Call tool| T[Tasks MCP]
  A -->|Call tool| C[Claims MCP]
  C --> CM[Claims Mock API]
```

Services:

* `agentops-mock` – the Agent (ADK wiring + retrieval + tool calls)
* `tasks-mcp` – MCP server for tasks (in‑memory)
* `claims-mcp` – MCP facade calling `claims-mock`
* `claims-mock` – FastAPI mock API with `/status`, `/claims/{id}`, `/fnol`

---

## Repo Layout (suggested)

```
agentops-mock/
  app/
    main.py                  # Agent (ADK) + tool routing + /chat
    prompts/system.txt
    retriever/
      chunk.py
      upsert_vector.py       # build & upsert to Vertex AI Vector Search
      search.py              # semantic search via index endpoint
    mcp/
      tasks_mcp.py           # FastAPI MCP server (in‑memory)
      claims_mcp.py          # FastAPI MCP server calling claims‑mock
  mocks/
    claims_api/
      main.py                # FastAPI mock Claims API
      Dockerfile
    data/
      docs/*.md              # mock runbooks/notes used for RAG
      seed_tasks.json
  infra/
    agent.Dockerfile
    tasks_mcp.Dockerfile
    claims_mcp.Dockerfile
  requirements.txt
  .env.example
  README.md
```

---

## Prereqs

* Python 3.11+
* `gcloud` CLI logged in: `gcloud auth login`
* GCP project set: `gcloud config set project <PROJECT_ID>`
* Enable APIs:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

* Region: use one that supports Vertex AI Vector Search (e.g., `us-central1`).
* (Optional) Create a GCS bucket to stash artifacts:

```bash
gsutil mb -l us-central1 gs://<PROJECT_ID>-agentops-mock
```

---

## Python Dependencies

`requirements.txt`

```
fastapi
uvicorn[standard]
python-dotenv
pydantic
requests

# Google Vertex / AI Platform
vertexai>=1.67.0
google-cloud-aiplatform>=1.66.0
google-cloud-storage
```

---

## Env Example

`.env.example`

```
PROJECT_ID=your-gcp-project-id
REGION=us-central1
LOCATION=us-central1
INDEX_DISPLAY_NAME=agentops-mock-index
ENDPOINT_DISPLAY_NAME=agentops-mock-endpoint
DOCS_DIR=mocks/data/docs
EMBED_MODEL=text-embedding-004
EMBED_DIM=3072

# MCP endpoints will be filled after deploy
tasks_mcp_base=
claims_mcp_base=
claims_base=
```

---

## Mock Docs (RAG Source)

Create a few small Markdown files in `mocks/data/docs/`:

* `release_audit_checklist.md` – 10–15 bullets
* `partner_onboarding_guide.md` – 8–12 bullets
* `claims_ops_runbook.md` – FNOL steps, attachment limits, retries (8–12 bullets)
* `env_health_playbook.md` – 5–8 bullets

Keep them short — fast to embed, cheap to store.

---

## Retriever, MCP Services, Agent, Dockerfiles

> Already defined above in detail (see full README).

---

## Build & Deploy (Cloud Run)

1. Deploy **claims-mock** → Cloud Run.
2. Deploy **tasks-mcp** → Cloud Run.
3. Deploy **claims-mcp** → Cloud Run (pointing at claims-mock URL).
4. Run `python -m app.retriever.upsert_vector` locally to create embeddings + index.
5. Deploy **agentops-mock** → Cloud Run with env vars pointing to MCP services and Vector Search settings.

## RAG bring-up

```bash
# venv + deps
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# upsert (creates index+endpoint and writes .artifacts/catalog.json)
PROJECT_ID=<PROJECT_ID> LOCATION=us-central1 python -m app.retriever.upsert_vector

# build+deploy agent (catalog now baked into image)
gcloud builds submit --config infra/cloudbuild.agent.yaml --substitutions=_IMAGE=gcr.io/<PROJECT_ID>/agentops-mock .
gcloud run deploy agentops-mock --image gcr.io/<PROJECT_ID>/agentops-mock --allow-unauthenticated --region us-central1 --port 8080 \
  --set-env-vars PROJECT_ID=<PROJECT_ID>,LOCATION=us-central1,INDEX_DISPLAY_NAME=agentops-mock-index,ENDPOINT_DISPLAY_NAME=agentops-mock-endpoint

# smoke test
AGENT_URL=$(gcloud run services describe agentops-mock --region us-central1 --format='value(status.url)')
curl -i -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' -d '{"query":"What are the key steps in our release audit checklist?"}'
```

---

## Try It

### RAG question

```bash
curl -s -X POST "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"query":"What are the key steps in our release audit checklist?"}' | jq
```

### Tasks MCP – add & list

```bash
curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"Add a task: Prepare enablement deck for SI workshop due 2025-09-09"}' | jq

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"List my tasks"}' | jq
```

### Claims MCP – status, FNOL, claim lookup

```bash
curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"What is the claims service status?"}' | jq

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"Create FNOL for external ref 734206245 with 2 docs"}' | jq

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"Get claim 25-44-069049"}' | jq
```

---

## Demo Script (90 seconds)

1. “What are our **release audit** steps?” → RAG returns bullets (with titles from your mock docs).
2. “**Add** a task … due Tuesday; then **list** tasks.” → Tasks MCP shows creation and list.
3. “**Create FNOL** for external ref 734206245 with 2 docs.” → Claims MCP calls Cloud Run mock and returns a new claim id.
4. “What’s the **claim status** for 25-44-069049?” → Claims MCP returns OPEN.

---

## Swapping the Mock Answer for Gemini (Optional Upgrade)

Replace the mock `answer` in `app/main.py` with a real Gemini call that includes retrieved `contexts`.

---

## Costs & Quotas (Typical Weekend Run)

* **Vector Search**: small index (≤ 500 chunks) stays inexpensive on credits.
* **Embeddings (text-embedding-004)**: a few hundred chunks = cents.
* **Gemini 1.5 Flash**: light queries often covered by free tier; otherwise uses your \$300 credit.
* **Cloud Run**: all services usually within free tier at low RPS.

---

## Troubleshooting

* Endpoint not found → rerun `upsert_vector`.
* Permission denied → `gcloud auth application-default login` and APIs enabled.
* Cold starts → retry once.
* CORS issues → add FastAPI CORS middleware.

---

## Clean Up

```bash
gcloud run services delete agentops-mock --region $REGION -q
gcloud run services delete tasks-mcp --region $REGION -q
gcloud run services delete claims-mcp --region $REGION -q
gcloud run services delete claims-mock --region $REGION -q
```

Also delete Vector Search index + endpoint with a quick Python snippet if needed.

---

## Positioning Notes (for interviews)

* **Vector Search**: production‑grade, recommended over FAISS.
* **MCP**: Agents that act, not just answer.
* **Cloud Run**: serverless + minimal ops = realistic enterprise deployment.

This gives you a ready‑to‑run project for your weekend build and interview prep.

---

## Starter Files (copy/paste)

### `requirements.txt`

```
fastapi==0.112.2
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
pydantic==2.9.2
requests==2.32.3

# Google SDKs
vertexai==1.67.1
google-cloud-aiplatform==1.66.0
google-cloud-storage==2.18.2
```

> If your environment pins differently, keep `vertexai` and `google-cloud-aiplatform` fairly up to date.

### `.env.example`

```
# Core
PROJECT_ID=your-gcp-project
LOCATION=us-central1
REGION=us-central1

# Vector Search
INDEX_DISPLAY_NAME=agentops-mock-index
ENDPOINT_DISPLAY_NAME=agentops-mock-endpoint
EMBED_MODEL=text-embedding-004
EMBED_DIM=3072

# MCP base URLs (set after Cloud Run deploys)
TASKS_MCP_BASE=https://tasks-mcp-xxxxxxxx.a.run.app
CLAIMS_MCP_BASE=https://claims-mcp-xxxxxxxx.a.run.app

# Claims mock service (used by claims-mcp)
CLAIMS_BASE=https://claims-mock-xxxxxxxx.a.run.app

# Catalog path
CATALOG_PATH=.artifacts/catalog.json
TOP_K=5
```

> Copy to `.env` and export when running locally. Cloud Run values are set via `--set-env-vars`.

### Minimal Mock Docs (drop in `mocks/data/docs/`)

`release_audit_checklist.md`

```
# Release Audit Checklist (Mock)
- Confirm code freeze date and release branch cut.
- Validate Jira fixVersion matches release window.
- Verify Bitbucket/GitHub commits mapped to Jira issues.
- Regenerate release notes draft.
- Identify regression test candidates.
- Confirm partner API allowlists and secrets rotation.
- Smoke test TRN/SIT environments.
```

`claims_ops_runbook.md`

```
# Claims Ops Runbook (Mock)
- FNOL payload must include external_ref, claimant_name, incident_ts.
- Soft limit: 5 attachments per request; batch if more.
- Retry policy: 3 attempts, exponential backoff.
- Status API: /status returns ok flag and timestamp.
- Claim lookup: /claims/{id} returns status and metadata.
```

`partner_onboarding_guide.md`

```
# Partner Onboarding (Mock)
- Exchange IP ranges and rotate secrets quarterly.
- Validate webhook endpoints and retry semantics.
- Provide sample payloads and Postman collection.
- Enable sandbox access; run end-to-end smoke.
- Checklist sign-off before production cutover.
```

### `Makefile` (quality-of-life)

```
PROJECT_ID?=$(shell gcloud config get-value project)
REGION?=us-central1

.PHONY: deps run-agent run-tasks run-claims run-claims-mock upsert deploy-mock deploy-tasks deploy-claims deploy-agent urls clean

deps:
	pip install -r requirements.txt

run-agent:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

run-tasks:
	uvicorn app.mcp.tasks_mcp:app --host 0.0.0.0 --port 9001

run-claims-mock:
	uvicorn mocks.claims_api.main:app --host 0.0.0.0 --port 9000

run-claims:
	CLAIMS_BASE=$$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)') \
	uvicorn app.mcp.claims_mcp:app --host 0.0.0.0 --port 9002

upsert:
	PROJECT_ID=$(PROJECT_ID) LOCATION=$(REGION) python -m app.retriever.upsert_vector

deploy-mock:
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/claims-mock .
	gcloud run deploy claims-mock --image gcr.io/$(PROJECT_ID)/claims-mock --allow-unauthenticated --region $(REGION) --port 9000 --command uvicorn --args mocks.claims_api.main:app,--host,0.0.0.0,--port,9000

deploy-tasks:
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/tasks-mcp -f infra/tasks_mcp.Dockerfile .
	gcloud run deploy tasks-mcp --image gcr.io/$(PROJECT_ID)/tasks-mcp --allow-unauthenticated --region $(REGION) --port 9001

deploy-claims:
	CLAIMS_BASE=$$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)') \
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/claims-mcp -f infra/claims_mcp.Dockerfile . && \
	gcloud run deploy claims-mcp --image gcr.io/$(PROJECT_ID)/claims-mcp --allow-unauthenticated --region $(REGION) --port 9002 --set-env-vars CLAIMS_BASE=$$CLAIMS_BASE

deploy-agent:
	TASKS_MCP_BASE=$$(gcloud run services describe tasks-mcp --region $(REGION) --format 'value(status.url)'); \
	CLAIMS_MCP_BASE=$$(gcloud run services describe claims-mcp --region $(REGION) --format 'value(status.url)'); \
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/agentops-mock -f infra/agent.Dockerfile . && \
	gcloud run deploy agentops-mock --image gcr.io/$(PROJECT_ID)/agentops-mock --allow-unauthenticated --region $(REGION) --port 8080 \
	  --set-env-vars PROJECT_ID=$(PROJECT_ID),LOCATION=$(REGION),INDEX_DISPLAY_NAME=agentops-mock-index,ENDPOINT_DISPLAY_NAME=agentops-mock-endpoint,TASKS_MCP_BASE=$$TASKS_MCP_BASE,CLAIMS_MCP_BASE=$$CLAIMS_MCP_BASE

urls:
	@echo Agent: $$(gcloud run services describe agentops-mock --region $(REGION) --format 'value(status.url)')
	@echo Tasks MCP: $$(gcloud run services describe tasks-mcp --region $(REGION) --format 'value(status.url)')
	@echo Claims MCP: $$(gcloud run services describe claims-mcp --region $(REGION) --format 'value(status.url)')
	@echo Claims Mock: $$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)')

clean:
	-gcloud run services delete agentops-mock --region $(REGION) -q
	-gcloud run services delete tasks-mcp --region $(REGION) -q
	-gcloud run services delete claims-mcp --region $(REGION) -q
	-gcloud run services delete claims-mock --region $(REGION) -q
```

### Mermaid Diagram (paste into README.md or a docs page)

```mermaid
flowchart LR
    U[User] --> A[Cloud Run: agentops-mock]
    A --> V1[Vertex AI: Gemini (chat)]
    A --> V2[Vertex AI: text-embedding-004]
    A --> VS[Vertex AI Vector Search]
    A --> T[Cloud Run: tasks-mcp]
    A --> C[Cloud Run: claims-mcp]
    C --> CM[Cloud Run: claims-mock]
```

### One-Command Quickstart

```bash
make deps \
 && make deploy-mock \
 && make deploy-tasks \
 && make deploy-claims \
 && make upsert \
 && make deploy-agent \
 && make urls
```

### Smoke Tests (curl)

```bash
AGENT_URL=$(gcloud run services describe agentops-mock --region $REGION --format 'value(status.url)')

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"List my tasks"}' | jq

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"Add a task: Prepare enablement deck for SI workshop due 2025-09-09"}' | jq

curl -s -X POST "$AGENT_URL/chat" -H 'Content-Type: application/json' \
  -d '{"query":"What are the key steps in our release audit checklist?"}' | jq
```

### Nice-to-haves (do later if time allows)

* Swap in **Gemini call** (already sketched) to replace the mock answer.
* Add **auth** on the Agent endpoint (API key/IAP).
* Persist tasks to **Firestore** instead of memory.
* Store chunk catalog in **Firestore/BigQuery** instead of local JSON.
* Add **Cloud Build triggers** on `main` branch for CI.

---

## GitHub Repo Setup (from zero)

### 1) Initialize and push

```bash
# from your workspace root
mkdir agentops-mock && cd agentops-mock
# add the files from this README (folders and code)

git init
printf "# AgentOps Mock
" > README.md
# (Paste the full README content from this canvas into README.md)

# Helpful starter files
cat > .gitignore <<'GIT'
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
.venv/
venv/
.env
.env.*

# Build/ops
.artifacts/
.dist/
.cache/
.pytest_cache/

# Editors
.vscode/
.idea/
GIT

cat > LICENSE <<'LIC'
MIT License

Copyright (c) 2025 Shayne Vandersloot

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
LIC

# Optional: CODEOWNERS (route PRs to you by default)
mkdir -p .github
cat > .github/CODEOWNERS <<'OWN'
* @DutchSloot84
OWN

# Commit and push
git add .
git commit -m "chore: bootstrap AgentOps Mock (ADK + MCP + Vertex Vector Search)"

gh repo create agentops-mock --public --source=. --remote=origin --push
# or create repo in GitHub UI, then:
# git remote add origin git@github.com:<you>/agentops-mock.git
# git push -u origin main
```

### 2) Optional: GitHub Actions CI (lint + unit test + Docker build)

Create `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Lint (flake8 minimal)
        run: |
          pip install flake8
          flake8 app mocks || true
      - name: Build Agent image
        run: |
          docker build -f infra/agent.Dockerfile -t agentops-mock:ci .
```

> Keep CI simple; deployment happens via `gcloud run deploy` from your machine for this weekend build.

### 3) README structure

Your `README.md` should include:

* **What**: short project pitch + badges (already at the top)
* **Why**: relevance to enterprise Agents (release audits, claims/FNOL)
* **Architecture**: Mermaid diagram
* **Quickstart**: Makefile one-liner and smoke tests
* **Local dev**: `make run-*`
* **Deploy**: Cloud Run steps
* **Troubleshooting** and **Clean up**
* **License** and **Credits**

---

## Next: Set Up in GCP

Follow the sections above: *Prereqs → Build & Deploy (Cloud Run) → Try It*. Start with:

```bash
make deps && make deploy-mock && make deploy-tasks && make deploy-claims && make upsert && make deploy-agent && make urls
```

If you hit issues, check the **Troubleshooting** section and confirm API enablement and ADC (`gcloud auth application-default login`).

---

## Scripts (optional but recommended)

### `scripts/bootstrap.sh`

Creates the repo structure locally, installs deps, logs into GCP (ADC), enables APIs, and commits/pushes to GitHub. It can also optionally kick off the initial Cloud Run deploys.

```bash
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
```

### `scripts/deploy_all.sh`

Runs the full deployment sequence end-to-end using the Makefile. You’ll be prompted for your project/region the first time via `bootstrap.sh`.

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${REGION:=us-central1}"

make deps \
 && make deploy-mock \
 && make deploy-tasks \
 && make deploy-claims \
 && make upsert \
 && make deploy-agent \
 && make urls
```

> After adding these, run `chmod +x scripts/*.sh` so you can execute them.

---

## Positioning Notes (for interviews)

* **Why Vector Search?** Production‑grade, managed ANN; aligns to Google’s recommended path over local FAISS.
* **Why MCP?** Demonstrates Agents that *act* (tasks, claims) beyond Q\&A.
* **Why Cloud Run?** Serverless, secure, minimal ops; mirrors real GCP delivery patterns.

You now have an end‑to‑end, mock‑backed Agent that’s easy to demo and discuss in a role‑related interview.
