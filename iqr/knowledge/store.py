"""Vector store interface + a dependency-free local implementation.

The local store is a deterministic hashed bag-of-words cosine index - enough
to run retrieval locally. Swap LocalVectorStore for the approved vendor by
implementing VectorStore; nothing above this interface changes.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path


class VectorStore:
    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        raise NotImplementedError

    def search(self, query: str, k: int = 3) -> list[dict]:
        raise NotImplementedError


class LocalVectorStore(VectorStore):
    def __init__(self, path: Path):
        self.path = path
        self.docs: dict[str, dict] = {}
        if path.exists():
            self.docs = json.loads(path.read_text())

    @staticmethod
    def _vec(text: str) -> dict[str, int]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return dict(Counter(tokens))

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        self.docs[doc_id] = {"text": text, "vec": self._vec(text),
                             "metadata": metadata or {}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.docs))

    def search(self, query: str, k: int = 3) -> list[dict]:
        qv = self._vec(query)
        qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0
        scored = []
        for doc_id, doc in sorted(self.docs.items()):
            dv = doc["vec"]
            dot = sum(qv.get(t, 0) * c for t, c in dv.items())
            dn = math.sqrt(sum(v * v for v in dv.values())) or 1.0
            scored.append((dot / (qn * dn), doc_id, doc))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [{"doc_id": did, "score": sc, "text": d["text"],
                 "metadata": d["metadata"]} for sc, did, d in scored[:k] if sc > 0]
