"""Embedding seat: semantic vectors for artifact <-> expected-evidence matching.

Real evidence arrives with names like `RE__Q226_EMR_Sing_off_request-JU.eml`
and `IPE_Webi_AFO_Workiva_reconciliations_Q226.xlsx`. Filename fuzz cannot
relate that to "certified quarterly EMR sign-off email" - meaning can. The
embedding seat turns an artifact's CONTENT SIGNALS (path, kind, sheet names,
email subject and opening lines, document paragraphs) and each plan item's
description into vectors; cosine similarity says what relates to what.

Two backends, same shape as every other model seat:
  - AzureFoundryEmbedding: the deployed embedding model (deterministic for a
    fixed model+input - reproducibility holds).
  - HashedEmbedding: dependency-free token-hash vectors, the permanent offline
    fallback. Weaker semantics, same interface, bit-reproducible.
Backend attribution is visible (`last_backend`), matching the platform rule
that fallback is never silent.
"""
from __future__ import annotations

import hashlib
import math
import re

import httpx

from iqr import config

DIM = 512   # hashed-fallback dimensionality


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class HashedEmbedding:
    """Deterministic hashed bag-of-tokens vectors (with bigrams). Offline-safe."""
    name = "hashed"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * DIM
            tokens = re.findall(r"[a-z0-9]+", t.lower())
            grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
            for g in grams:
                h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
                vec[h % DIM] += 1.0
            out.append(vec)
        return out


class AzureFoundryEmbedding:
    name = "foundry-embedding"

    def __init__(self, endpoint: str, api_key: str, deployment: str,
                 api_version: str = "2024-10-21"):
        self.url = (f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
                    f"/embeddings?api-version={api_version}")
        self.api_key = api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(self.url, headers={"api-key": self.api_key},
                          json={"input": texts}, timeout=60)
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


class Embedder:
    """The seat: Foundry embeddings when configured, hashed fallback always."""

    def __init__(self):
        self.hashed = HashedEmbedding()
        self.foundry = None
        if config.AZURE_FOUNDRY_ENDPOINT and config.AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT:
            self.foundry = AzureFoundryEmbedding(
                config.AZURE_FOUNDRY_ENDPOINT, config.AZURE_FOUNDRY_API_KEY,
                config.AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT,
                config.AZURE_FOUNDRY_API_VERSION)
        self.last_backend = ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.foundry is not None:
            try:
                vecs = self.foundry.embed(texts)
                self.last_backend = self.foundry.name
                return vecs
            except Exception:
                pass                       # visible fallback below, never silent
        self.last_backend = self.hashed.name
        return self.hashed.embed(texts)
