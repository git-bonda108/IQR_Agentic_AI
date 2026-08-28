"""Dispatch a frozen CheckDef to its executor. Runtime never chooses checks -
the compiled plan already did."""
from __future__ import annotations

from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Finding
from iqr.schemas.validation_plan import CheckDef, ValidationPlan
from iqr.checks.agent_checks import run_signoff_check, run_temporal_check, run_vision_check
from iqr.checks.numeric import run_numeric_check


def run_check(check: CheckDef, plan: ValidationPlan, graph: EvidenceGraph,
              matches: dict, ledger: RunLedger | None = None) -> Finding:
    if check.check_type == "numeric":
        return run_numeric_check(check, graph, matches, ledger)
    if check.check_type == "vision":
        return run_vision_check(check, graph, matches, ledger)
    if check.check_type == "temporal":
        return run_temporal_check(check, graph, matches, ledger)
    if check.check_type == "signoff":
        return run_signoff_check(check, graph, matches, plan.signoff, ledger)
    raise ValueError(f"unknown check_type {check.check_type}")
