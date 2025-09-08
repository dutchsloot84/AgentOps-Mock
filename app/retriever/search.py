import json, os
from typing import List, Dict

from google.cloud import aiplatform_v1
from vertexai import init as vertex_init
from vertexai.preview.language_models import TextEmbeddingModel

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
ENDPOINT_DISPLAY_NAME = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")

CATALOG_PATH = ".artifacts/catalog.json"

def _embed_query(q: str) -> List[float]:
    vertex_init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    return model.get_embeddings([q])[0].values

def _resolve_endpoint_name() -> str:
    client = aiplatform_v1.IndexEndpointServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    )
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"
    for ep in client.list_index_endpoints(request={"parent": parent}):
        if ep.display_name == ENDPOINT_DISPLAY_NAME:
            return ep.name
    raise RuntimeError(f"IndexEndpoint with display_name '{ENDPOINT_DISPLAY_NAME}' not found")

def search_topk(query: str, top_k: int = 5) -> List[Dict]:
    if not os.path.exists(CATALOG_PATH):
        raise RuntimeError(f"Catalog not found at {CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    vec = _embed_query(query)

    match_client = aiplatform_v1.MatchServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    )
    endpoint_name = _resolve_endpoint_name()

    query_obj = aiplatform_v1.FindNeighborsRequest.Query(
        neighbor_count=top_k,
        datapoint=aiplatform_v1.IndexDatapoint(feature_vector=vec)
    )
    req = aiplatform_v1.FindNeighborsRequest(
        index_endpoint=endpoint_name,
        queries=[query_obj]
    )
    resp = match_client.find_neighbors(request=req)

    results: List[Dict] = []
    if resp and resp.nearest_neighbors:
        for nn in resp.nearest_neighbors[0].neighbors:
            dp_id = nn.datapoint.datapoint_id
            meta = catalog.get(dp_id, {})
            results.append({
                "id": dp_id,
                "score": nn.distance,
                "title": meta.get("title"),
                "chunk_ix": meta.get("chunk_ix"),
                "text": meta.get("text"),
            })
    return results
