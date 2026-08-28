"""Control Knowledge Base: 404s and their compiled plans, vector-indexed.
Retrieval context for the Plan Compiler ("how are controls like this structured")."""
from __future__ import annotations

from iqr import config
from iqr.knowledge.store import LocalVectorStore, VectorStore
from iqr.schemas.validation_plan import ValidationPlan


class ControlKB:
    def __init__(self, store: VectorStore | None = None):
        config.ensure_dirs()
        self.store = store or LocalVectorStore(config.KNOWLEDGE_DIR / "control_kb.json")

    def index_plan(self, plan: ValidationPlan, doc_text: str) -> None:
        self.store.add(f"{plan.control_id}:{plan.version}",
                       f"{plan.description}\n{doc_text}",
                       {"control_id": plan.control_id, "version": plan.version,
                        "checks": [c.check_type for c in plan.checks]})

    def retrieve_context(self, query: str, k: int = 2) -> list[dict]:
        return self.store.search(query, k)
