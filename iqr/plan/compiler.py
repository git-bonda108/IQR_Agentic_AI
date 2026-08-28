"""Design-time Plan Compiler: an agent reads a 404 process document and drafts
a Validation Plan. The draft is NOT executable until an SME approves and
freezes it (plan/review.py). This is the only place agent judgment shapes
WHICH checks run - and it happens once, under human review, never at runtime.

The heuristic parser below handles the structured attribute listing a 404
carries; in DaVinci mode the same agent task prompts the model to emit the
identical schema from free text, grounded by Control-KB retrieval.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from iqr.agents.runtime import run_agent
from iqr.schemas.validation_plan import (CheckDef, ExpectedEvidence, ScopeExclusion,
                                         SignoffRule, ValidationPlan)


def compile_plan(doc_path: str, control_id: str, frequency: str,
                 kb=None) -> ValidationPlan:
    import docx as docx_mod
    d = docx_mod.Document(doc_path)
    paragraphs = [p.text for p in d.paragraphs if p.text.strip()]

    context = {"task_type": "plan_compile", "control_id": control_id,
               "frequency": frequency, "doc_paragraphs": paragraphs}
    if kb is not None:
        context["kb_context"] = kb.retrieve_context(" ".join(paragraphs[:3]))
    run = run_agent(f"compile validation plan for {control_id}", context, tools=[])
    draft = ValidationPlan.model_validate(run.final)
    return draft


def heuristic_plan_from_404(control_id: str, frequency: str,
                            paragraphs: list[str]) -> dict:
    """Deterministic structuring of a 404's attribute listing into a plan draft."""
    evidence: list[dict] = []
    checks: list[dict] = []
    exclusions: list[dict] = []
    signoff: dict | None = None
    description = paragraphs[0] if paragraphs else ""
    section = None
    for para in paragraphs:
        t = para.strip()
        upper = t.upper()
        if upper.startswith("EXPECTED EVIDENCE"):
            section = "evidence"; continue
        if upper.startswith("CHECKS"):
            section = "checks"; continue
        if upper.startswith("SCOPE EXCLUSIONS"):
            section = "exclusions"; continue
        if upper.startswith("SIGNOFF:"):
            signoff = _parse_signoff(t[len("SIGNOFF:"):]); section = None; continue
        if not t.startswith("-"):
            continue
        body = t[1:].strip()
        if section == "evidence":
            parts = [p.strip() for p in body.split("|")]
            evidence.append({"id": parts[0], "description": parts[1],
                             "match_hints": [h.strip() for h in parts[2].removeprefix("hints:").split(",")],
                             "required": parts[3].lower() == "required"})
        elif section == "checks":
            parts = [p.strip() for p in body.split("|", 3)]
            params = json.loads(parts[3])
            checks.append({"id": parts[0], "check_type": parts[1],
                           "description": parts[2], "params": params,
                           "inputs": sorted({v["evidence"] for v in _evidence_refs(params)})})
        elif section == "exclusions":
            parts = [p.strip() for p in body.split("|")]
            exclusions.append({"id": parts[0], "reason": parts[1],
                               "match_hints": [h.strip() for h in parts[2].removeprefix("hints:").split(",")]})
    return {"control_id": control_id, "version": "1.0.0", "frequency": frequency,
            "description": description, "expected_evidence": evidence,
            "checks": checks, "scope_exclusions": exclusions, "signoff": signoff}


def _evidence_refs(obj) -> list[dict]:
    found = []
    if isinstance(obj, dict):
        if "evidence" in obj and isinstance(obj["evidence"], str):
            found.append(obj)
        for k, v in obj.items():
            if k.endswith("_evidence") and isinstance(v, str):
                found.append({"evidence": v})
            else:
                found.extend(_evidence_refs(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_evidence_refs(v))
    return found


def _parse_signoff(spec: str) -> dict:
    kv = dict(re.findall(r"(\w+)\s*=\s*([^;]+)", spec))
    return {"preparer_role": kv.get("preparer", "").strip(),
            "approver_role": kv.get("approver", "").strip(),
            "require_distinct": kv.get("distinct", "true").strip().lower() == "true",
            "require_order": kv.get("order", "true").strip().lower() == "true"}
