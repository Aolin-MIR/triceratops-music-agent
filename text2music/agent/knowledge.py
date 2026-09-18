"""Small, dependency-free knowledge index for the local music agent."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
TOKEN_RE = re.compile(r"[a-z0-9_+#-]+|[\u3400-\u9fff]", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _chunks(text: str, *, size: int = 900, overlap: int = 120) -> Iterable[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            split = clean.rfind(" ", start + size // 2, end)
            if split > start:
                end = split
        yield clean[start:end]
        if end == len(clean):
            break
        start = max(start + 1, end - overlap)


class KnowledgeBase:
    """Persisted lexical RAG with source paths and deterministic ranking."""

    def __init__(self, index_path: Path, roots: Iterable[Path]) -> None:
        self.index_path = index_path
        self.roots = [Path(root) for root in roots]
        self.documents: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if data.get("version") == 1 and isinstance(data.get("documents"), list):
                self.documents = data["documents"]
        except (OSError, ValueError, TypeError):
            self.documents = []

    def rebuild(self) -> dict[str, int]:
        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.exists():
                continue
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue
                resolved = str(path.resolve())
                if resolved in seen or path.stat().st_size > 4_000_000:
                    continue
                seen.add(resolved)
                text = path.read_text(encoding="utf-8", errors="replace")
                for number, chunk in enumerate(_chunks(text)):
                    documents.append({
                        "id": hashlib.sha256(f"{resolved}:{number}:{chunk}".encode()).hexdigest()[:16],
                        "source": resolved,
                        "chunk": number,
                        "text": chunk,
                        "tokens": dict(Counter(_tokens(chunk))),
                    })
        self.documents = documents
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 1, "documents": documents}, ensure_ascii=False),
                             encoding="utf-8")
        temporary.replace(self.index_path)
        return {"sources": len(seen), "chunks": len(documents)}

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        # The indexed roots are intentionally small. Rebuilding here keeps
        # newly added project notes and corrected manuals visible immediately.
        self.rebuild()
        terms = Counter(_tokens(query))
        if not terms:
            return []
        document_frequency = Counter()
        for document in self.documents:
            document_frequency.update(set(document.get("tokens", {})))
        total = max(1, len(self.documents))
        ranked = []
        for document in self.documents:
            counts = document.get("tokens", {})
            length = max(1, sum(counts.values()))
            score = sum((counts.get(term, 0) / length) *
                        (1.0 + math.log((total + 1) / (document_frequency[term] + 1))) * weight
                        for term, weight in terms.items())
            if score > 0:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1]["source"], item[1]["chunk"]))
        return [{"source": item["source"], "chunk": item["chunk"], "text": item["text"],
                 "score": round(score, 6)} for score, item in ranked[:max(1, min(limit, 10))]]
