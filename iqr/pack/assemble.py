"""Assemble the audit-ready pack: one downloadable .zip the auditor receives.

Contents: validated output per check, auto-completed reviewer checklist,
artifact manifest (every leaf + hash), explicit gaps-and-observations
register, and the citation index. Every claim inside has already passed the
citation gate; assembly re-asserts it as a belt-and-braces final gate.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from iqr import config
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import AuditPack, ChecklistItem, Verdict
from iqr.schemas.validation_plan import ValidationPlan
from iqr.tools.citation import gate_finding


def assemble_pack(verdict: Verdict, plan: ValidationPlan, graph: EvidenceGraph,
                  unmatched_leaves: list[str] | None = None) -> AuditPack:
    config.ensure_dirs()
    for f in verdict.findings:  # final gate: nothing uncited ships
        ok, problems = gate_finding(f, graph)
        if not ok:
            raise ValueError(f"pack assembly blocked by citation gate: {problems}")

    checklist = [ChecklistItem(
        check_id=c.id, description=c.description,
        result=next((f.verdict for f in verdict.findings if f.check_id == c.id), "not-run"),
        evidence_refs=[cite.locator_str() for f in verdict.findings
                       if f.check_id == c.id for cite in f.citations])
        for c in plan.checks]

    manifest = [{"logical_path": l.logical_path, "sha256": l.file_hash,
                 "kind": l.kind, "size": l.size, "contained_in": l.parent_hash}
                for l in sorted(graph.leaves.values(), key=lambda l: l.logical_path)]

    gaps_register = list(verdict.gaps)
    for path in (unmatched_leaves or []):
        gaps_register.append(f"observation: artifact present but not expected by plan: {path}")

    pack_path = config.PACK_DIR / f"{verdict.run_id}.zip"
    with zipfile.ZipFile(pack_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("verdict.json", verdict.model_dump_json(indent=2))
        zf.writestr("checklist.md", _checklist_md(plan, verdict, checklist))
        zf.writestr("gaps_and_observations.md",
                    "\n".join(f"- {g}" for g in gaps_register) or "- none\n")
        zf.writestr("artifact_manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("citations.json", json.dumps(
            [{"check_id": f.check_id, "verdict": f.verdict,
              "citations": [c.locator_str() for c in f.citations]}
             for f in verdict.findings], indent=2))
        zf.writestr("plan.json", plan.model_dump_json(indent=2))
    return AuditPack(verdict=verdict, checklist=checklist, artifact_manifest=manifest,
                     gaps_register=gaps_register, pack_path=str(pack_path))


def _checklist_md(plan: ValidationPlan, verdict: Verdict,
                  checklist: list[ChecklistItem]) -> str:
    lines = [f"# Reviewer checklist - {plan.control_id} (plan v{plan.version})",
             f"Run: {verdict.run_id}  |  Control verdict: **{verdict.result}**", ""]
    mark = {"pass": "[x]", "gap": "[ ] GAP", "fail": "[ ] FAIL", "not-run": "[ ] NOT RUN"}
    for item in checklist:
        lines.append(f"- {mark.get(item.result, '[ ]')} {item.check_id}: {item.description}")
        for ref in item.evidence_refs:
            lines.append(f"    - evidence: {ref}")
    lines += ["", "Every claim above carries a citation that resolves against the "
                  "hashed evidence graph in artifact_manifest.json."]
    return "\n".join(lines)
