import json
import os
from typing import List, Dict

from google.cloud import aiplatform
from google.cloud import aiplatform_v1
from vertexai import init as vertex_init
from vertexai.preview.language_models import TextEmbeddingModel

CATALOG_PATH = os.getenv("CATALOG_PATH", ".artifacts/catalog.json")
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
INDEX_DISPLAY_NAME = os.getenv("INDEX_DISPLAY_NAME", "agentops-mock-index")
ENDPOINT_DISPLAY_NAME = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")

DEPLOYED_INDEX_ID = "agentops_deployed"
TOP_K = int(os.getenv("TOP_K", "5"))


def _embed_query(q: str) -> list[float]:
    vertex_init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    return model.get_embeddings([q])[0].values


def _get_endpoint_name() -> str:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    for ep in aiplatform.MatchingEngineIndexEndpoint.list():
        if ep.display_name == ENDPOINT_DISPLAY_NAME:
            return ep.resource_name
    raise RuntimeError(f"IndexEndpoint with display_name={ENDPOINT_DISPLAY_NAME} not found")


def _load_catalog() -> Dict[str, Dict]:
    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(
            f"Catalog not found at {CATALOG_PATH}. Run the upsert step locally to generate it, "
            "then redeploy the agent so the file is baked into the image."
        )
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def search_topk(query: str, top_k: int = TOP_K) -> List[Dict]:
    vector = _embed_query(query)
    endpoint_name = _get_endpoint_name()
    catalog = _load_catalog()

    client = aiplatform.gapic.IndexEndpointServiceClient(client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"})

    dp = aiplatform_v1.IndexDatapoint(
        datapoint_id="query",
        feature_vector=vector,
    )
    q = aiplatform_v1.FindNeighborsRequest.Query(
        datapoint=dp,
        neighbor_count=top_k,
    )

    resp = client.find_neighbors(
        index_endpoint=endpoint_name,
        deployed_index_id=DEPLOYED_INDEX_ID,
        queries=[q],
    )

    # One query -> one result set
    neighbors = []
    if resp.nearest_neighbors:
        for n in resp.nearest_neighbors[0].neighbors:
            nid = n.datapoint.datapoint_id
            entry = catalog.get(nid, {})
            neighbors.append({
                "datapoint_id": nid,
                "distance": n.distance,
                "title": entry.get("title"),
                "chunk_ix": entry.get("chunk_ix"),
                "text": entry.get("text"),
            })
    return neighbors
