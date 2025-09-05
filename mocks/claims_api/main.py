import random
import string
import time
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="claims-mock")

CLAIMS: Dict[str, Dict] = {
    "25-44-069049": {"id": "25-44-069049", "status": "OPEN"}
}


class Fnol(BaseModel):
    external_ref: str
    docs: int = 0


def _gen_id() -> str:
    return "-".join([
        "".join(random.choices(string.digits, k=2)),
        "".join(random.choices(string.digits, k=2)),
        "".join(random.choices(string.digits, k=6)),
    ])


@app.get("/status")
def status():
    return {"ok": True, "ts": int(time.time())}


@app.get("/claims/{claim_id}")
def get_claim(claim_id: str):
    if claim_id not in CLAIMS:
        raise HTTPException(status_code=404, detail="Not found")
    return CLAIMS[claim_id]


@app.post("/fnol")
def create_fnol(fnol: Fnol):
    claim_id = _gen_id()
    CLAIMS[claim_id] = {"id": claim_id, "status": "OPEN", "external_ref": fnol.external_ref, "docs": fnol.docs}
    return CLAIMS[claim_id]
