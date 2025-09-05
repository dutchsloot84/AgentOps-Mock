import json
import os
import uuid
from pathlib import Path
from typing import List

from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel

from .chunk import load_docs, chunk_text

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
INDEX_DISPLAY_NAME = os.getenv("INDEX_DISPLAY_NAME", "agentops-mock-index")
ENDPOINT_DISPLAY_NAME = os.getenv("ENDPOINT_DISPLAY_NAME", "agentops-mock-endpoint")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
EMBED_DIM = int(os.getenv("EMBED_DIM", "3072"))
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", ".artifacts/catalog.json"))
TOP_K = int(os.getenv("TOP_K", "5"))


def _ensure_index() -> aiplatform.MatchingEngineIndex:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    indexes = aiplatform.MatchingEngineIndex.list(filter=f'display_name="{INDEX_DISPLAY_NAME}"')
    if indexes:
        return indexes[0]
    return aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=INDEX_DISPLAY_NAME,
        dimensions=EMBED_DIM,
    )


def _ensure_endpoint(index: aiplatform.MatchingEngineIndex) -> aiplatform.MatchingEngineIndexEndpoint:
    endpoints = aiplatform.MatchingEngineIndexEndpoint.list(filter=f'display_name="{ENDPOINT_DISPLAY_NAME}"')
    if endpoints:
        endpoint = endpoints[0]
    else:
        endpoint = aiplatform.MatchingEngineIndexEndpoint.create(display_name=ENDPOINT_DISPLAY_NAME)
    deployed_ids = [d.index for d in endpoint.deployed_indexes]
    if index.resource_name not in deployed_ids:
        endpoint.deploy(index=index, deployed_index_id=str(uuid.uuid4()).replace("-", "")[:32])
    return endpoint


def _embed_texts(texts: List[str]) -> List[List[float]]:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    embeddings = model.get_embeddings(texts)
    return [e.values for e in embeddings]


def run_upsert():
    docs = load_docs()
    chunks = []
    catalog = []
    for title, text in docs:
        for ix, chunk in enumerate(chunk_text(text)):
            chunk_id = f"{title}:{ix}"
            chunks.append((chunk_id, chunk))
            catalog.append({"id": chunk_id, "title": title, "chunk_ix": ix, "text": chunk})
    vectors = _embed_texts([c[1] for c in chunks])
    index = _ensure_index()
    datapoints = [
        aiplatform.MatchingEngineIndex.Datapoint(datapoint_id=cid, feature_vector=vec)
        for (cid, _), vec in zip(chunks, vectors)
    ]
    index.upsert_datapoints(datapoints=datapoints)
    endpoint = _ensure_endpoint(index)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f)
    return {"index": index.resource_name, "endpoint": endpoint.resource_name, "chunks": len(datapoints)}


if __name__ == "__main__":
    print(json.dumps(run_upsert(), indent=2))
