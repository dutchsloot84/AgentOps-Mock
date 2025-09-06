# app/retriever/chunk.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Iterable

def load_docs(root_dir: str = "mocks/data/docs") -> List[Tuple[str, str]]:
    """Load all .md files from root_dir -> list of (filename, text)."""
    root = Path(root_dir)
    docs: List[Tuple[str, str]] = []
    for path in sorted(root.glob("*.md")):
        docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs

def chunk_text(text: str, size: int = 1100, overlap: int = 150) -> Iterable[str]:
    """Simple word-based chunker with overlap."""
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(words):
        end = min(len(words), start + size)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks
