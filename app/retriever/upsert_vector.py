import json
import os
import time
import uuid
from typing import List, Dict

from google.cloud import aiplatform
from vertexai import init as vertex_init
from vertexai.preview.language_models import TextEmbeddingModel

from .chunk import load_docs, chunk_text

# Env
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
INDEX_DISPLAY_NAME = os.getenv("INDEX_DISPLAY_NAME", "agentops-mock-index")
ENDPOINT_DISPLAY_NAME = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
DOCS_DIR = os.getenv("DOCS_DIR", "mocks/data/docs")

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
DIMENSIONS = int(os.getenv("EMBED_DIM", "3072"))  # text-embedding-004 outputs 3072 dims


def _ensure_index() -> str:
    """Create or reuse a small Tree-AH index with required params."""
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Reuse if exists
    for idx in aiplatform.MatchingEngineIndex.list():
        if idx.display_name == INDEX_DISPLAY_NAME:
            return idx.resource_name

    # Create a new Tree-AH index (explicitly set approximate_neighbors_count)
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=INDEX_DISPLAY_NAME,
        dimensions=DIMENSIONS,
        distance_measure_type="COSINE_DISTANCE",
        leaf_node_embedding_count=1000,        # tiny demo value
        leaf_nodes_to_search_percent=7,        # search % for recall/speed tradeoff
        approximate_neighbors_count=10,        # REQUIRED for Tree-AH
        description="AgentOps mock Tree-AH index",
    )
    index.wait()
    return index.resource_name


def _ensure_endpoint(index_name: str) -> str:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Reuse endpoint if present
    for ep in aiplatform.MatchingEngineIndexEndpoint.list():
        if ep.display_name == ENDPOINT_DISPLAY_NAME:
            endpoint = ep
            break
    else:
        # PUBLIC endpoint for demo (no VPC needed)
        endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
            display_name=ENDPOINT_DISPLAY_NAME,
            description="AgentOps mock endpoint",
            public_endpoint_enabled=True,
        )
        endpoint.wait()

    # Deploy index if not already deployed
    deployed = any(d.index == index_name for d in endpoint.deployed_indexes)
    if not deployed:
        idx_obj = aiplatform.MatchingEngineIndex(index_name)  # <-- key line
        endpoint.deploy_index(index=idx_obj, deployed_index_id="agentops_deployed")
        time.sleep(15)

    return endpoint.resource_name

def _embed_texts(texts: List[str]) -> List[List[float]]:
    vertex_init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    vecs: List[List[float]] = []
    B = 16
    for i in range(0, len(texts), B):
        batch = texts[i:i+B]
        embeddings = model.get_embeddings(batch)
        vecs.extend(e.values for e in embeddings)
    return vecs


def run_upsert() -> Dict:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # 1) Ensure index + endpoint
    index_name = _ensure_index()
    endpoint_name = _ensure_endpoint(index_name)

    # 2) Load & chunk docs
    docs = load_docs(DOCS_DIR)
    records = []
    for title, text in docs:
        for ix, ch in enumerate(chunk_text(text)):
            records.append({
                "id": str(uuid.uuid4()),
                "title": title,
                "chunk_ix": ix,
                "text": ch,
            })

    if not records:
        return {"ok": False, "reason": "no docs/chunks"}

    # 3) Embed
    vectors = _embed_texts([r["text"] for r in records])

    # 4) Upsert datapoints
    index = aiplatform.MatchingEngineIndex(index_name)
    dps = []
    for r, v in zip(records, vectors):
        dp = aiplatform.datapoint.Datapoint(
            datapoint_id=r["id"],
            feature_vector=v,
            restricts=[],
            crowding_tag=None,
        )
        dps.append(dp)

    index.upsert_datapoints(datapoints=dps)

    # 5) Save catalog mapping locally
    os.makedirs(".artifacts", exist_ok=True)
    catalog = {r["id"]: {"title": r["title"], "chunk_ix": r["chunk_ix"], "text": r["text"]} for r in records}
    with open(".artifacts/catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    return {"ok": True, "index": index_name, "endpoint": endpoint_name, "count": len(records)}


if __name__ == "__main__":
    out = run_upsert()
    print(json.dumps(out, indent=2))
