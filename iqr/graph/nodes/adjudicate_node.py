"""Adjudicator: mechanical citation gate, then aggregation to the control-level
verdict. No claim enters the Verdict unless every one of its citations resolves
against the Evidence Graph."""
from __future__ import annotations

from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Finding, Verdict
from iqr.schemas.validation_plan import ValidationPlan
from iqr.tools.citation import gate_finding


def adjudicate(plan: ValidationPlan, graph: EvidenceGraph, findings: list[Finding],
               missing: list[str], exceptions: list[str], run_id: str) -> Verdict:
    gated: list[Finding] = []
    exceptions = list(exceptions)
    for f in sorted(findings, key=lambda f: f.check_id):
        ok, problems = gate_finding(f, graph)
        if not ok:
            exceptions.extend([f"CITATION GATE: {p}" for p in problems])
            continue  # mechanically rejected: cannot enter the verdict
        gated.append(f)

    gaps = [f"required evidence not found: {ev_id}" for ev_id in missing]
    gaps += [f"ingestion: {e}" for e in graph.errors]
    gaps += [f"{f.check_id}: {f.detail}" for f in gated if f.verdict == "gap"]

    unverified = [f for f in gated if not f.verified]
    if unverified:
        exceptions.extend([f"awaiting human adjudication: {f.check_id}" for f in unverified])

    if any(f.verdict == "fail" for f in gated):
        result = "fail"
    elif gaps or exceptions:
        result = "pass_with_gaps"
    else:
        result = "pass"
    return Verdict(control_id=plan.control_id, plan_version=plan.version,
                   result=result, findings=gated, gaps=gaps,
                   exceptions=exceptions, run_id=run_id)


def adjudicate_node(state: dict) -> dict:
    exceptions = list(state.get("exceptions", []))
    for a in state.get("anomalies", []):
        if a.get("severity") == "high":
            exceptions.append(f"ANOMALY[{a['detector']}]: {a['detail']}")
    verdict = adjudicate(state["plan"], state["evidence"],
                         state.get("verified_findings", []),
                         state.get("missing", []),
                         exceptions,
                         state["run_id"])
    RunLedger(state["run_id"]).log("adjudicate", result=verdict.result,
                                   findings=len(verdict.findings),
                                   gaps=verdict.gaps, exceptions=verdict.exceptions)
    return {"verdict": verdict}
