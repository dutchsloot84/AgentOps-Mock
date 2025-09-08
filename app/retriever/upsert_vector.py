import json, os, time, uuid
from typing import List, Dict, Tuple

from google.cloud import aiplatform
from google.cloud import aiplatform_v1  # GAPIC for datapoints
from vertexai import init as vertex_init
from vertexai.preview.language_models import TextEmbeddingModel

from .chunk import load_docs, chunk_text

# -------------------
# Env
# -------------------
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")

# A base name; we’ll suffix the true dim automatically, e.g., agentops-mock-index-768d
INDEX_DISPLAY_NAME_BASE = os.getenv("INDEX_DISPLAY_NAME", "agentops-mock-index")
ENDPOINT_DISPLAY_NAME   = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
DOCS_DIR                = os.getenv("DOCS_DIR", "mocks/data/docs")

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")  # returns 3072 by default
DEPLOYED_INDEX_ID = "agentops_deployed"


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


def _ensure_index(dimensions: int, display_name: str) -> str:
    """Create or reuse a Tree-AH index with STREAM_UPDATE for the given dim."""
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Look for exact display_name match
    for idx in aiplatform.MatchingEngineIndex.list():
        if idx.display_name == display_name:
            return idx.resource_name

    # Create Tree-AH with stream updates
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=display_name,
        dimensions=dimensions,
        distance_measure_type="COSINE_DISTANCE",
        leaf_node_embedding_count=1000,      # small demo
        leaf_nodes_to_search_percent=7,
        approximate_neighbors_count=10,      # required for Tree-AH
        index_update_method="STREAM_UPDATE", # important for upsert
        description=f"AgentOps demo Tree-AH ({dimensions}d, streaming)",
    )
    index.wait()
    return index.resource_name


def _ensure_endpoint(index_name: str) -> str:
    """Create or reuse a PUBLIC endpoint and deploy the given index."""
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Reuse endpoint if present
    endpoint = None
    for ep in aiplatform.MatchingEngineIndexEndpoint.list():
        if ep.display_name == ENDPOINT_DISPLAY_NAME:
            endpoint = ep
            break
    if endpoint is None:
        endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
            display_name=ENDPOINT_DISPLAY_NAME,
            description="AgentOps mock endpoint (public)",
            public_endpoint_enabled=True,
        )
        endpoint.wait()

    # Deploy if not already deployed
    if not any(d.index == index_name for d in endpoint.deployed_indexes):
        idx_obj = aiplatform.MatchingEngineIndex(index_name)
        endpoint.deploy_index(index=idx_obj, deployed_index_id=DEPLOYED_INDEX_ID)
        time.sleep(15)  # small settle time

    return endpoint.resource_name


def run_upsert() -> Dict:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # 1) Load & chunk docs
    docs: List[Tuple[str, str]] = load_docs(DOCS_DIR)
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

    # 2) Embed first so we know the true dimensionality
    vectors = _embed_texts([r["text"] for r in records])
    embed_dim = len(vectors[0])
    index_display_name = f"{INDEX_DISPLAY_NAME_BASE}-{embed_dim}d"

    # 3) Ensure index + endpoint
    index_name = _ensure_index(embed_dim, index_display_name)
    endpoint_name = _ensure_endpoint(index_name)

    # 4) Upsert datapoints via GAPIC
    idx_client = aiplatform_v1.IndexServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    )
    datapoints = []
    for r, v in zip(records, vectors):
        datapoints.append(
            aiplatform_v1.IndexDatapoint(
                datapoint_id=r["id"],
                feature_vector=v,
            )
        )
    req = aiplatform_v1.UpsertDatapointsRequest(index=index_name, datapoints=datapoints)
    idx_client.upsert_datapoints(request=req)

    # 5) Save catalog locally (baked into image on next build)
    os.makedirs(".artifacts", exist_ok=True)
    catalog = {
        r["id"]: {"title": r["title"], "chunk_ix": r["chunk_ix"], "text": r["text"]}
        for r in records
    }
    with open(".artifacts/catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "index": index_name,
        "endpoint": endpoint_name,
        "count": len(records),
        "dim": embed_dim,
        "index_display_name": index_display_name,
    }


if __name__ == "__main__":
    out = run_upsert()
    print(json.dumps(out, indent=2))
