"""Central configuration: model chain, paths, pinned parameters.

All model calls go through get_model_client() so the model stack is decided in
exactly one place, with parameters (temperature 0) pinned centrally.

API keys & endpoints come from environment variables, or from a local `.env`
file at the repo root (gitignored - NEVER commit it). See .env.example.

Model modes (IQR_MODEL):
  stub     - deterministic offline policy engine (default; no network, no keys)
  davinci  - DaVinci API only; fails hard if unreachable
  auto     - fallback chain: DaVinci -> secondary endpoint (if configured)
             -> stub (unless IQR_STUB_FALLBACK=0). Each completion tries the
             chain in order and records which backend answered in the ledger.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (no extra dependency): KEY=VALUE lines, # comments.
    Real environment variables always win over .env values."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.environ.get("IQR_DATA_DIR", REPO_ROOT / "data"))
EVIDENCE_STORE_DIR = DATA_DIR / "evidence_store"   # immutable blob store
PLAN_STORE_DIR = DATA_DIR / "plans"                # versioned, frozen plans
RUN_LEDGER_DIR = DATA_DIR / "runs"                 # replayable run ledgers
KNOWLEDGE_DIR = DATA_DIR / "knowledge"             # vector store persistence
PACK_DIR = DATA_DIR / "packs"                      # assembled audit packs

MODEL_NAME = os.environ.get("IQR_MODEL", "stub")   # "stub" | "davinci" | "foundry" | "auto"
DAVINCI_API_URL = os.environ.get("DAVINCI_API_URL", "")
DAVINCI_API_KEY = os.environ.get("DAVINCI_API_KEY", "")
SECONDARY_API_URL = os.environ.get("IQR_SECONDARY_API_URL", "")
SECONDARY_API_KEY = os.environ.get("IQR_SECONDARY_API_KEY", "")

# Azure AI Foundry: model seat (chat-completions deployment) ...
AZURE_FOUNDRY_ENDPOINT = os.environ.get("AZURE_FOUNDRY_ENDPOINT", "")
AZURE_FOUNDRY_API_KEY = os.environ.get("AZURE_FOUNDRY_API_KEY", "")
AZURE_FOUNDRY_DEPLOYMENT = os.environ.get("AZURE_FOUNDRY_DEPLOYMENT", "")
AZURE_FOUNDRY_API_VERSION = os.environ.get("AZURE_FOUNDRY_API_VERSION", "2024-10-21")
AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT", "")
# ... and Foundry IQ: agentic knowledge retrieval over a knowledge base.
FOUNDRY_IQ_ENDPOINT = os.environ.get("FOUNDRY_IQ_ENDPOINT", "")
FOUNDRY_IQ_API_KEY = os.environ.get("FOUNDRY_IQ_API_KEY", "")
FOUNDRY_IQ_KNOWLEDGE_BASE = os.environ.get("FOUNDRY_IQ_KNOWLEDGE_BASE", "")
STUB_FALLBACK = os.environ.get("IQR_STUB_FALLBACK", "1") != "0"
MODEL_TEMPERATURE = 0.0                            # pinned; never override
MODEL_MAX_TOKENS = 2048
AGENT_MAX_STEPS = 12                               # hard cap on agent tool loops

# Numeric checks must never touch a model. The model client increments this
# counter on every completion; the numeric check path asserts it is unchanged.
_model_call_counter = {"count": 0}


def ensure_dirs() -> None:
    for d in (EVIDENCE_STORE_DIR, PLAN_STORE_DIR, RUN_LEDGER_DIR, KNOWLEDGE_DIR, PACK_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_model_client(seat: str | None = None):
    """The single factory for model access. Import this, never a client directly.

    `seat` is the agent seat asking (plan_compile, vision, temporal, signoff,
    verify). Per-seat routing lets each newly security-approved model earn a
    specific seat once it passes the five eval gates, without touching code:

      IQR_MODEL_VERIFY=davinci            # mode override for one seat
      IQR_FOUNDRY_DEPLOYMENT_PLAN_COMPILE=gpt-5-chat   # stronger model, one seat

    Unset seats inherit the global IQR_MODEL / AZURE_FOUNDRY_DEPLOYMENT. The
    ledger already records which backend answered every call, so a per-seat
    assignment is fully attributable run over run.
    """
    from iqr.agents.model_client import (AzureFoundryClient, DaVinciClient,
                                         FallbackModelClient, StubModelClient)

    key = seat.upper().replace("-", "_") if seat else ""
    mode = os.environ.get(f"IQR_MODEL_{key}", MODEL_NAME) if key else MODEL_NAME
    deployment = (os.environ.get(f"IQR_FOUNDRY_DEPLOYMENT_{key}", AZURE_FOUNDRY_DEPLOYMENT)
                  if key else AZURE_FOUNDRY_DEPLOYMENT)

    if mode == "davinci":
        return DaVinciClient(DAVINCI_API_URL, DAVINCI_API_KEY,
                             temperature=MODEL_TEMPERATURE, max_tokens=MODEL_MAX_TOKENS,
                             name="davinci")
    if mode == "foundry":
        return AzureFoundryClient(AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_API_KEY,
                                  deployment, AZURE_FOUNDRY_API_VERSION,
                                  temperature=MODEL_TEMPERATURE,
                                  max_tokens=MODEL_MAX_TOKENS)
    if mode == "auto":
        chain = []
        if AZURE_FOUNDRY_ENDPOINT:
            chain.append(AzureFoundryClient(AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_API_KEY,
                                            deployment, AZURE_FOUNDRY_API_VERSION,
                                            temperature=MODEL_TEMPERATURE,
                                            max_tokens=MODEL_MAX_TOKENS))
        if DAVINCI_API_URL:
            chain.append(DaVinciClient(DAVINCI_API_URL, DAVINCI_API_KEY,
                                       temperature=MODEL_TEMPERATURE,
                                       max_tokens=MODEL_MAX_TOKENS, name="davinci"))
        if SECONDARY_API_URL:
            chain.append(DaVinciClient(SECONDARY_API_URL, SECONDARY_API_KEY,
                                       temperature=MODEL_TEMPERATURE,
                                       max_tokens=MODEL_MAX_TOKENS, name="secondary"))
        if STUB_FALLBACK or not chain:
            chain.append(StubModelClient())
        return FallbackModelClient(chain)
    return StubModelClient()


def model_call_count() -> int:
    return _model_call_counter["count"]


def record_model_call() -> None:
    _model_call_counter["count"] += 1
