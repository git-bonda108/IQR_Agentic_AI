"""Intake: understand a package BEFORE anything is chosen or run.

The real process starts with a pile of evidence, not a dropdown. A performer
bulk-uploads whatever the period produced - workbooks, approval emails, ZIPs,
screenshots, in any mix - and IQR works out the rest:

  1. INGEST the tree deterministically (hash, extract, address every fact).
  2. INFER the control: score every approved plan's expected-evidence register
     against what is actually present (required-evidence coverage, computed
     mechanically by the same matcher the runtime uses - no model opinion).
  3. NARRATE: an intake agent turns the mechanical facts into the package's
     story - what this appears to be, what will be validated, what is already
     missing. Grounded: every fact in the story comes from the graph and the
     plan; the model only phrases it.

The result feeds the console's intake screen; "Run validation" then executes
the frozen plan exactly as always. Inference RANKS candidates - a human
confirms the control before anything runs (plans stay the law).
"""
from __future__ import annotations

from collections import Counter

from iqr.agents.runtime import run_agent
from iqr.graph.nodes.match_node import match_evidence
from iqr.ingest.graph_builder import build_evidence_graph
from iqr.plan.review import latest_version, load_plan
from iqr import config

INTAKE_OUTPUT_SPEC = ('{"story": "<3-6 sentences: what this package appears to be, '
                      'what evidence is present and how it nests, what the suggested '
                      "control's checks will validate, and any evidence already "
                      'missing>", "caveats": ["<anything a reviewer should know>"]}')


def _plan_candidates(graph) -> list[dict]:
    """Score EVERY frozen plan version and keep, per control, the version the
    package fits best - packages from different periods legitimately match
    different plan versions, and intake should say which one."""
    out = []
    for d in sorted(config.PLAN_STORE_DIR.glob("*/")):
        cid = d.name
        best = None
        for pf in sorted(d.glob("*.json")):
            plan = load_plan(cid, pf.stem)
            matches, missing, unmatched = match_evidence(plan, graph)
            required = [e.id for e in plan.expected_evidence if e.required]
            matched_required = [r for r in required if r in matches]
            coverage = len(matched_required) / len(required) if required else 0.0
            cand = {
                "control_id": cid, "version": plan.version,
                "description": plan.description,
                "coverage": round(coverage, 3),
                "matched": {mid: matches[mid].get("logical_path", "(images)")
                            for mid in sorted(matches)},
                "missing": missing,
                "checks": [{"id": c.id, "type": c.check_type,
                            "description": c.description} for c in plan.checks]}
            if best is None or cand["coverage"] >= best["coverage"]:
                best = cand    # >= : on a coverage tie the NEWER version wins
        if best is not None:
            out.append(best)
    out.sort(key=lambda c: (-c["coverage"], c["control_id"]))
    return out


def analyze_package(package_ref: str) -> dict:
    """Ingest + infer + narrate. Deterministic facts; model-phrased story."""
    graph = build_evidence_graph(package_ref)
    formats = Counter(l.kind for l in graph.leaves.values())
    summary = {
        "leaves": len(graph.leaves),
        "cells": len(graph.cells),
        "emails": len(graph.emails),
        "images": len(graph.images),
        "errors": list(graph.errors),
        "formats": dict(sorted(formats.items())),
        "tree": sorted(l.logical_path for l in graph.leaves.values())[:40],
    }
    candidates = _plan_candidates(graph)
    best = candidates[0] if candidates else None

    context = {"task_type": "intake", "summary": summary,
               "best_candidate": best and {
                   "control_id": best["control_id"],
                   "description": best["description"],
                   "coverage": best["coverage"],
                   "missing": best["missing"],
                   "checks": best["checks"]},
               "other_candidates": [{"control_id": c["control_id"],
                                     "coverage": c["coverage"]}
                                    for c in candidates[1:3]]}
    run = run_agent("intake analysis", context, tools=[],
                    output_spec=INTAKE_OUTPUT_SPEC)
    return {"package_ref": package_ref, "summary": summary,
            "candidates": candidates,
            "suggested_control": best["control_id"] if best else None,
            "confidence": best["coverage"] if best else 0.0,
            "story": run.final.get("story", ""),
            "caveats": run.final.get("caveats", [])}
