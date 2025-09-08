import os
import requests
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .retriever.search import search_topk

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
TASKS_MCP_BASE = os.getenv("TASKS_MCP_BASE")  # e.g., https://tasks-mcp-...a.run.app
CLAIMS_MCP_BASE = os.getenv("CLAIMS_MCP_BASE")  # e.g., https://claims-mcp-...a.run.app

app = FastAPI(title="agentops-mock", version="1.0.0")

# CORS (demo-wide). If you later split UI/API origins, restrict allow_origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static UI at /ui
_UI_DIR = os.path.join(os.path.dirname(__file__), "web")
app.mount("/ui", StaticFiles(directory=_UI_DIR), name="ui")


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str


# -------------------------------------------------------------------
# Utilities to call MCP mocks with basic error handling
# -------------------------------------------------------------------
_DEFAULT_TIMEOUT = 10  # seconds


def _tasks(path: str, payload: Optional[dict] = None):
    if not TASKS_MCP_BASE:
        raise HTTPException(status_code=500, detail="TASKS_MCP_BASE not set")
    url = f"{TASKS_MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    try:
        if payload is not None:
            resp = requests.post(url, json=payload, timeout=_DEFAULT_TIMEOUT)
        else:
            resp = requests.get(url, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Tasks MCP error: {e}") from e


def _claims(path: str, method: str = "get", payload: Optional[dict] = None):
    if not CLAIMS_MCP_BASE:
        raise HTTPException(status_code=500, detail="CLAIMS_MCP_BASE not set")
    url = f"{CLAIMS_MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    try:
        func = requests.post if method.lower() == "post" else requests.get
        resp = func(url, json=payload, timeout=_DEFAULT_TIMEOUT) if payload else func(url, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Claims MCP error: {e}") from e


# -------------------------------------------------------------------
# Health / Liveness
# -------------------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


# -------------------------------------------------------------------
# Primary chat endpoint (RAG + MCP actions)
# -------------------------------------------------------------------
@app.post("/chat")
def chat(req: ChatRequest):
    q_lower = req.query.lower().strip()

    # Tasks MCP flows
    if q_lower.startswith("list my tasks"):
        return _tasks("list")

    if q_lower.startswith("add a task"):
        # Expect format: "Add a task: Title goes here due 2025-09-09"
        parts = req.query.split(":", 1)[-1].strip() if ":" in req.query else req.query[len("add a task"):].strip()
        if " due " in parts:
            title, due = parts.rsplit(" due ", 1)
        else:
            title, due = parts, ""
        return _tasks("add", {"title": title.strip(), "due": due.strip()})

    if q_lower.startswith("complete task"):
        # "Complete task T-0001"
        pieces = req.query.strip().split()
        task_id = pieces[-1] if pieces else ""
        if not task_id:
            raise HTTPException(status_code=400, detail="Missing task id")
        return _tasks(f"complete/{task_id}")

    # Claims MCP flows
    if "claims service status" in q_lower:
        return _claims("status")

    if q_lower.startswith("get claim"):
        # "Get claim C-1234"
        pieces = req.query.strip().split()
        claim_id = pieces[-1] if pieces else ""
        if not claim_id:
            raise HTTPException(status_code=400, detail="Missing claim id")
        return _claims(f"claim/{claim_id}")

    if q_lower.startswith("create fnol"):
        # "Create FNOL for external ref 123 with 2 docs"
        try:
            parts = q_lower.split("external ref", 1)[1].strip()
            ext_ref, rest = parts.split("with", 1)
            docs = int(rest.split("doc")[0].strip())
            return _claims("fnol", method="post", payload={"external_ref": ext_ref.strip(), "docs": docs})
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Expected format: 'Create FNOL for external ref <REF> with <N> docs'",
            )

    # RAG retrieval
    try:
        contexts = search_topk(req.query)
        # Keep answer mock; contexts are the real retrieved chunks
        return {"answer": "(mock) see contexts", "contexts": contexts}
    except Exception as e:
        # Surface a controlled error for easier debugging in Cloud Run logs/UI
        raise HTTPException(status_code=500, detail=f"RAG search error: {e}") from e
