import os
import requests
from fastapi import FastAPI

CLAIMS_BASE = os.getenv("CLAIMS_BASE")
if not CLAIMS_BASE:
    raise RuntimeError("CLAIMS_BASE env var required")

app = FastAPI(title="claims-mcp")


@app.get("/status")
def status():
    resp = requests.get(f"{CLAIMS_BASE}/status", timeout=10)
    return resp.json()


@app.get("/claim/{claim_id}")
def get_claim(claim_id: str):
    resp = requests.get(f"{CLAIMS_BASE}/claims/{claim_id}", timeout=10)
    return resp.json()


@app.post("/fnol")
def create_fnol(payload: dict):
    resp = requests.post(f"{CLAIMS_BASE}/fnol", json=payload, timeout=10)
    return resp.json()
