import json, os, time, uuid
from typing import List, Dict, Tuple

from google.cloud import aiplatform
from google.cloud import aiplatform_v1
from vertexai import init as vertex_init
from vertexai.preview.language_models import TextEmbeddingModel

from .chunk import load_docs, chunk_text

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")

INDEX_DISPLAY_NAME_BASE = os.getenv("INDEX_DISPLAY_NAME", "agentops-mock-index")
ENDPOINT_DISPLAY_NAME   = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
DOCS_DIR                = os.getenv("DOCS_DIR", "mocks/data/docs")
EMBED_MODEL             = os.getenv("EMBED_MODEL", "text-embedding-004")

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
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    for idx in aiplatform.MatchingEngineIndex.list():
        if idx.display_name == display_name:
            return idx.resource_name
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=display_name,
        dimensions=dimensions,
        distance_measure_type="COSINE_DISTANCE",
        leaf_node_embedding_count=1000,
        leaf_nodes_to_search_percent=7,
        approximate_neighbors_count=10,
        index_update_method="STREAM_UPDATE",
        description=f"Tree-AH ({dimensions}d, STREAM_UPDATE)",
    )
    index.wait()
    return index.resource_name

def _ensure_endpoint_and_deploy(index_name: str, deployed_index_id_base: str) -> Tuple[str, str]:
    """
    Returns (endpoint_resource_name, deployed_index_id_in_use).
    Handles conflicts by generating a unique deployed_index_id when needed.
    """
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    # Find or create public endpoint
    endpoint = None
    for ep in aiplatform.MatchingEngineIndexEndpoint.list():
        if ep.display_name == ENDPOINT_DISPLAY_NAME:
            endpoint = ep
            break
    if endpoint is None:
        endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
            display_name=ENDPOINT_DISPLAY_NAME,
            description="Public endpoint for AgentOps demo",
            public_endpoint_enabled=True,
        )
        endpoint.wait()

    # If this index already deployed → reuse
    for d in endpoint.deployed_indexes:
        if d.index == index_name:
            # Already deployed; return existing deployedIndexId
            return endpoint.resource_name, d.id

    # Otherwise, try deploy with base ID; if conflicting, add a short suffix
    deployed_id = deployed_index_id_base
    try:
        idx_obj = aiplatform.MatchingEngineIndex(index_name)
        endpoint.deploy_index(index=idx_obj, deployed_index_id=deployed_id)
        time.sleep(10)
        return endpoint.resource_name, deployed_id
    except Exception as e:
        message = str(e)
        if "already exists a DeployedIndex with same ID" in message or "ALREADY_EXISTS" in message:
            short = uuid.uuid4().hex[:6]
            deployed_id = f"{deployed_index_id_base}-{short}"
            idx_obj = aiplatform.MatchingEngineIndex(index_name)
            endpoint.deploy_index(index=idx_obj, deployed_index_id=deployed_id)
            time.sleep(10)
            return endpoint.resource_name, deployed_id
        raise

def run_upsert() -> Dict:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Load & chunk docs
    docs: List[Tuple[str, str]] = load_docs(DOCS_DIR)
    records = []
    for title, text in docs:
        for ix, ch in enumerate(chunk_text(text)):
            records.append({"id": str(uuid.uuid4()), "title": title, "chunk_ix": ix, "text": ch})
    if not records:
        return {"ok": False, "reason": "no docs/chunks"}

    # Embed first to know the true dim
    vectors = _embed_texts([r["text"] for r in records])
    embed_dim = len(vectors[0])
    index_display_name = f"{INDEX_DISPLAY_NAME_BASE}-{embed_dim}d"
    deployed_index_id_base = f"agentops-{embed_dim}d"

    # Ensure index + endpoint deploy
    index_name = _ensure_index(embed_dim, index_display_name)
    endpoint_name, deployed_index_id = _ensure_endpoint_and_deploy(index_name, deployed_index_id_base)

    # Upsert via GAPIC
    idx_client = aiplatform_v1.IndexServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    )
    datapoints = [
        aiplatform_v1.IndexDatapoint(datapoint_id=r["id"], feature_vector=v)
        for r, v in zip(records, vectors)
    ]
    req = aiplatform_v1.UpsertDatapointsRequest(index=index_name, datapoints=datapoints)
    idx_client.upsert_datapoints(request=req)

    # Write catalog
    os.makedirs(".artifacts", exist_ok=True)
    catalog = {r["id"]: {"title": r["title"], "chunk_ix": r["chunk_ix"], "text": r["text"]} for r in records}
    with open(".artifacts/catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "index": index_name,
        "endpoint": endpoint_name,
        "count": len(records),
        "dim": embed_dim,
        "index_display_name": index_display_name,
        "deployed_index_id": deployed_index_id,
    }

if __name__ == "__main__":
    out = run_upsert()
    print(json.dumps(out, indent=2))
