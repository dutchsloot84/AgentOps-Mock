import os
from pathlib import Path
from typing import List, Tuple

DOCS_DIR = Path(os.getenv("DOCS_DIR", "mocks/data/docs"))


def load_docs() -> List[Tuple[str, str]]:
    docs: List[Tuple[str, str]] = []
    for path in DOCS_DIR.glob("*.md"):
        with open(path, "r", encoding="utf-8") as f:
            docs.append((path.name, f.read()))
    return docs


def chunk_text(text: str, size: int = 1100, overlap: int = 150) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = start + size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks
