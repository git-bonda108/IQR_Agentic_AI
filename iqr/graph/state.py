"""Typed LangGraph state. The evidence graph and findings flow as structured
state - never as re-dumped prompt text. Findings from the parallel check
fan-out are reduced with list-append."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Finding, Verdict
from iqr.schemas.validation_plan import ValidationPlan


class IQRState(TypedDict, total=False):
    run_id: str
    package_ref: str
    plan: ValidationPlan
    evidence: EvidenceGraph
    matches: dict                 # evidence_id -> resolved artifact locators
    missing: list[str]            # required evidence ids not found (honest misses)
    unmatched_leaves: list[str]   # artifacts present but not expected (observations)
    anomalies: list[dict]         # sentinel pre-screen results (adversarial stage)
    findings: Annotated[list[Finding], operator.add]   # raw executor findings (fan-in)
    verified_findings: list[Finding]
    exceptions: list[str]         # citation-gate rejections + verifier disagreements
    verdict: Verdict


class CheckTask(TypedDict):
    """Input payload for one parallel check branch (via langgraph Send)."""
    check_id: str
    plan: ValidationPlan
    evidence: EvidenceGraph
    matches: dict
    run_id: str
