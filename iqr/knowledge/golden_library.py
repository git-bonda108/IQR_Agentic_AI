"""Golden Library: adjudicated exemplars - prior verdicts and human overrides.

Retrieval context for check/verify agents ("how was this pattern judged
before"), and the seed of the regression eval set. Nothing enters the runtime
path from here without passing the eval harness + SME sign-off
(governed learning, iqr/eval/harness.py gate).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from iqr import config
from iqr.knowledge.foundry_iq import knowledge_store
from iqr.knowledge.store import LocalVectorStore, VectorStore


class GoldenLibrary:
    def __init__(self, store: VectorStore | None = None):
        config.ensure_dirs()
        self.store = store or knowledge_store(
            LocalVectorStore(config.KNOWLEDGE_DIR / "golden_library.json"))
        self.overrides_path = config.KNOWLEDGE_DIR / "overrides.jsonl"

    def record_adjudication(self, control_id: str, check_id: str, pattern: str,
                            human_verdict: str, rationale: str, run_id: str,
                            iqr_verdict: str | None = None) -> dict:
        exemplar = {"control_id": control_id, "check_id": check_id,
                    "pattern": pattern, "human_verdict": human_verdict,
                    "iqr_verdict": iqr_verdict,   # reward signal for iqr.learn
                    "rationale": rationale, "run_id": run_id,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "released": False}
        with open(self.overrides_path, "a") as f:
            f.write(json.dumps(exemplar) + "\n")
        return exemplar

    def release_exemplar(self, exemplar: dict, eval_passed: bool, sme: str) -> None:
        """The governed-learning gate: eval green + SME sign-off, else refuse."""
        if not eval_passed:
            raise PermissionError("exemplar blocked: regression eval did not pass")
        if not sme:
            raise PermissionError("exemplar blocked: SME sign-off required")
        exemplar = dict(exemplar, released=True, released_by=sme)
        key = f"{exemplar['control_id']}:{exemplar['check_id']}:{exemplar['run_id']}"
        self.store.add(key, f"{exemplar['pattern']} -> {exemplar['human_verdict']}: "
                            f"{exemplar['rationale']}", exemplar)

    def similar_adjudications(self, pattern: str, k: int = 3) -> list[dict]:
        return self.store.search(pattern, k)

    def pending_overrides(self) -> list[dict]:
        if not self.overrides_path.exists():
            return []
        return [json.loads(l) for l in self.overrides_path.read_text().splitlines() if l]
