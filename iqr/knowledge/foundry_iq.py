"""Foundry IQ retrieval behind the VectorStore interface.

Foundry IQ (Azure AI Foundry's knowledge layer) serves agentic retrieval over
a knowledge base. This store keeps the platform's contract intact: callers
still speak VectorStore, and the local hashed index remains the always-on
mirror, so retrieval works offline and every add() is durable on local disk.

When FOUNDRY_IQ_ENDPOINT / FOUNDRY_IQ_API_KEY / FOUNDRY_IQ_KNOWLEDGE_BASE are
configured, search() asks the knowledge base first (agentic retrieval REST)
and falls back to the local mirror on any error - loudly, via `last_backend`,
never silently. add() always writes the local mirror; pushing documents into
the knowledge base itself is done through Foundry's own ingestion sources
(blob storage, SharePoint, Fabric), not from the runtime.
"""
from __future__ import annotations

import httpx

from iqr import config
from iqr.knowledge.store import VectorStore

FOUNDRY_IQ_API_VERSION = "2025-08-01-preview"


class FoundryIQStore(VectorStore):
    def __init__(self, local_mirror: VectorStore,
                 endpoint: str = "", api_key: str = "", knowledge_base: str = ""):
        self.local = local_mirror
        self.endpoint = (endpoint or config.FOUNDRY_IQ_ENDPOINT).rstrip("/")
        self.api_key = api_key or config.FOUNDRY_IQ_API_KEY
        self.knowledge_base = knowledge_base or config.FOUNDRY_IQ_KNOWLEDGE_BASE
        self.last_backend = ""          # "foundry-iq" | "local" - recorded per search

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.knowledge_base)

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        self.local.add(doc_id, text, metadata)

    def search(self, query: str, k: int = 3) -> list[dict]:
        if self.configured:
            try:
                results = self._retrieve(query, k)
                self.last_backend = "foundry-iq"
                return results
            except Exception:
                # Agentic retrieval needs a paid Search tier; a plain index
                # query over the same knowledge base is the next-best ground.
                try:
                    results = self._index_search(query, k)
                    self.last_backend = "foundry-iq-index"
                    return results
                except Exception:
                    pass                 # fall through to the local mirror
        self.last_backend = "local"
        return self.local.search(query, k)

    def _index_search(self, query: str, k: int) -> list[dict]:
        """Keyword search against the index backing the knowledge base."""
        url = (f"{self.endpoint}/indexes/{self.knowledge_base}/docs/search"
               f"?api-version=2024-07-01")
        resp = httpx.post(url, headers={"api-key": self.api_key},
                          json={"search": query, "top": k}, timeout=30)
        resp.raise_for_status()
        return [{"doc_id": d.get("doc_id", d.get("id", "")),
                 "score": d.get("@search.score", 0.0),
                 "text": d.get("text", ""),
                 "metadata": {"source": "foundry-iq-index",
                              "kind": d.get("kind", "")}}
                for d in resp.json().get("value", [])]

    def _retrieve(self, query: str, k: int) -> list[dict]:
        """Agentic retrieval against the knowledge base (Azure AI Search wire)."""
        url = (f"{self.endpoint}/knowledgeBases/{self.knowledge_base}/retrieve"
               f"?api-version={FOUNDRY_IQ_API_VERSION}")
        resp = httpx.post(
            url,
            headers={"api-key": self.api_key},
            json={"messages": [{"role": "user",
                               "content": [{"type": "text", "text": query}]}],
                  "top": k},
            timeout=60)
        resp.raise_for_status()
        body = resp.json()
        out = []
        for ref in body.get("references", [])[:k]:
            out.append({"doc_id": ref.get("id", ""),
                        "score": ref.get("rerankerScore", 0.0),
                        "text": ref.get("blob", {}).get("text",
                                ref.get("sourceData", {}).get("text", "")),
                        "metadata": {"source": "foundry-iq",
                                     "docKey": ref.get("docKey", "")}})
        return out


def knowledge_store(local_mirror: VectorStore) -> VectorStore:
    """Factory the KB classes use: Foundry IQ when configured, local otherwise."""
    store = FoundryIQStore(local_mirror)
    return store if store.configured else local_mirror
