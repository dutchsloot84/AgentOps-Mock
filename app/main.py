import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .retriever.search import search_topk

TASKS_MCP_BASE = os.getenv("TASKS_MCP_BASE")
CLAIMS_MCP_BASE = os.getenv("CLAIMS_MCP_BASE")

app = FastAPI(title="agentops-mock")


class ChatRequest(BaseModel):
    query: str


def _tasks(path: str, payload: dict | None = None):
    if not TASKS_MCP_BASE:
        raise HTTPException(status_code=500, detail="TASKS_MCP_BASE not set")
    url = f"{TASKS_MCP_BASE}/{path}"
    if payload:
        resp = requests.post(url, json=payload, timeout=10)
    else:
        resp = requests.get(url, timeout=10)
    return resp.json()


def _claims(path: str, method: str = "get", payload: dict | None = None):
    if not CLAIMS_MCP_BASE:
        raise HTTPException(status_code=500, detail="CLAIMS_MCP_BASE not set")
    url = f"{CLAIMS_MCP_BASE}/{path}"
    func = requests.post if method.lower() == "post" else requests.get
    resp = func(url, json=payload, timeout=10) if payload else func(url, timeout=10)
    return resp.json()


@app.post("/chat")
def chat(req: ChatRequest):
    q = req.query.lower()
    if q.startswith("list my tasks"):
        return _tasks("list")
    if q.startswith("add a task"):
        # expect format: "Add a task: title due 2025-09-09"
        parts = req.query.split(":", 1)[-1].strip()
        if " due " in parts:
            title, due = parts.rsplit(" due ", 1)
        else:
            title, due = parts, ""
        return _tasks("add", {"title": title.strip(), "due": due.strip()})
    if q.startswith("complete task"):
        task_id = req.query.split()[-1]
        return _tasks(f"complete/{task_id}")
    if "claims service status" in q:
        return _claims("status")
    if q.startswith("get claim"):
        claim_id = req.query.split()[-1]
        return _claims(f"claim/{claim_id}")
    if q.startswith("create fnol"):
        # "Create FNOL for external ref 123 with 2 docs"
        parts = q.split("external ref", 1)[1].strip()
        ext_ref, rest = parts.split("with", 1)
        docs = int(rest.split("doc")[0].strip())
        return _claims("fnol", method="post", payload={"external_ref": ext_ref.strip(), "docs": docs})
    contexts = search_topk(req.query)
    return {"answer": "(mock) see contexts", "contexts": contexts}
