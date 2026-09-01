"""Seed the Foundry IQ knowledge index with IQR's knowledge layer.

Creates the `iqr-knowledge` index on the configured Azure AI Search service
and uploads the semantic corpus: every frozen plan (what each control expects
and checks), the real-corpus validation lessons, and any released Golden
Library exemplars. This is the ground the Plan Compiler and check/verify
agents retrieve against - meaning over bytes.

Run:  .venv/bin/python scripts/azure/seed_knowledge.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from iqr import config  # noqa: E402  (loads .env)

API = "2024-07-01"
INDEX = config.FOUNDRY_IQ_KNOWLEDGE_BASE or "iqr-knowledge"
HEADERS = {"api-key": config.FOUNDRY_IQ_API_KEY, "Content-Type": "application/json"}

SCHEMA = {
    "name": INDEX,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "doc_id", "type": "Edm.String", "filterable": True},
        {"name": "kind", "type": "Edm.String", "filterable": True, "facetable": True},
        {"name": "control_id", "type": "Edm.String", "filterable": True},
        {"name": "text", "type": "Edm.String", "searchable": True},
    ],
}


def collect_docs() -> list[dict]:
    docs: list[dict] = []
    # 1. Frozen plans: the compiled semantics of each control.
    for pf in sorted(config.PLAN_STORE_DIR.glob("*/*.json")):
        plan = json.loads(pf.read_text())
        checks = "; ".join(f"{c['id']} ({c['check_type']}): {c['description']}"
                           for c in plan.get("checks", []))
        evidence = "; ".join(f"{e['id']}: {e['description']}"
                             for e in plan.get("expected_evidence", []))
        text = (f"Control {plan['control_id']} v{plan['version']} "
                f"({plan.get('frequency', '')}). {plan.get('description', '')} "
                f"Expected evidence: {evidence}. Checks: {checks}.")
        docs.append({"id": f"plan-{plan['control_id']}-{plan['version']}".replace(".", "-"),
                     "doc_id": f"{plan['control_id']}:{plan['version']}",
                     "kind": "plan", "control_id": plan["control_id"], "text": text})
    # 2. Real-corpus validation lessons (SME-grade domain knowledge).
    real = config.REPO_ROOT / "docs" / "REAL_VALIDATION.md"
    if real.exists():
        for i, section in enumerate(real.read_text().split("\n## ")):
            title = section.split("\n", 1)[0].strip("# ")
            docs.append({"id": f"lesson-{i}", "doc_id": f"REAL_VALIDATION#{i}",
                         "kind": "lesson", "control_id": "",
                         "text": f"{title}: {section[:6000]}"})
    # 3. Released Golden Library exemplars (adjudicated judgments).
    gl = config.KNOWLEDGE_DIR / "golden_library.json"
    if gl.exists():
        for doc_id, doc in json.loads(gl.read_text()).items():
            docs.append({"id": "gl-" + "".join(ch if ch.isalnum() else "-" for ch in doc_id),
                         "doc_id": doc_id, "kind": "golden_exemplar",
                         "control_id": doc.get("metadata", {}).get("control_id", ""),
                         "text": doc["text"]})
    return docs


def main() -> int:
    if not (config.FOUNDRY_IQ_ENDPOINT and config.FOUNDRY_IQ_API_KEY):
        print("FOUNDRY_IQ_ENDPOINT / FOUNDRY_IQ_API_KEY not configured")
        return 1
    base = config.FOUNDRY_IQ_ENDPOINT.rstrip("/")
    r = httpx.put(f"{base}/indexes/{INDEX}?api-version={API}",
                  headers=HEADERS, json=SCHEMA, timeout=60)
    if r.status_code not in (200, 201, 204):
        print(f"index create failed: {r.status_code} {r.text[:300]}")
        return 1
    docs = collect_docs()
    for d in docs:
        d["@search.action"] = "mergeOrUpload"
    r = httpx.post(f"{base}/indexes/{INDEX}/docs/index?api-version={API}",
                   headers=HEADERS, json={"value": docs}, timeout=120)
    r.raise_for_status()
    ok = sum(1 for v in r.json()["value"] if v["status"])
    print(f"index '{INDEX}': {ok}/{len(docs)} documents indexed "
          f"({sum(1 for d in docs if d['kind']=='plan')} plans, "
          f"{sum(1 for d in docs if d['kind']=='lesson')} lessons, "
          f"{sum(1 for d in docs if d['kind']=='golden_exemplar')} exemplars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
