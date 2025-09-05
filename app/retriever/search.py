import json
import os
from pathlib import Path
from typing import List, Dict

from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
ENDPOINT_DISPLAY_NAME = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", ".artifacts/catalog.json"))
TOP_K = int(os.getenv("TOP_K", "5"))


def _load_catalog() -> Dict[str, Dict]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)}


def search_topk(query: str, top_k: int = TOP_K):
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    vector = model.get_embeddings([query])[0].values
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    endpoint = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{ENDPOINT_DISPLAY_NAME}"'
    )[0]
    response = endpoint.find_neighbors(datapoint_vector=vector, neighbor_count=top_k)
    catalog = _load_catalog()
    results = []
    for neighbor in response[0].neighbors:
        dp_id = neighbor.datapoint.datapoint_id
        meta = catalog.get(dp_id, {})
        results.append({
            "datapoint_id": dp_id,
            "distance": neighbor.distance,
            "title": meta.get("title"),
            "chunk_ix": meta.get("chunk_ix"),
            "text": meta.get("text"),
        })
    return results
