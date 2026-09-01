"""Anomaly Sentinel: adversarial screening that runs BEFORE the checks.

The blinded verifier attacks findings after they exist; the sentinel attacks
the evidence package itself - hunting the patterns a well-formed package uses
to hide problems: period mismatches, recycled artifacts, link placeholders
posing as attachments, pasted constants where formulas should be, deltas that
sit suspiciously close to tolerance, and single-actor sign-off chains.

Same golden rule as everything else: every detector is deterministic Python
over the Evidence Graph and the frozen plan. No model invents an anomaly;
every anomaly carries citations that resolve.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation
from iqr.schemas.validation_plan import ValidationPlan

Severity = Literal["info", "warn", "high"]


class Anomaly(BaseModel):
    detector: str
    severity: Severity
    detail: str
    citations: list[Citation] = Field(default_factory=list)


# fiscal-period tokens as they appear in corporate GRC artifacts: Q226, Q2'26, P06 FY26, FY26
_PERIOD_RE = re.compile(
    r"(?:Q(?P<q>[1-4])\s*[-' ]?\s*(?P<qy>\d{2})(?!\d)|P(?P<p>\d{2})[-_ ]?FY[-_ ]?(?P<py>\d{2}))",
    re.IGNORECASE)


def _period_tokens(text: str) -> set[str]:
    out = set()
    for m in _PERIOD_RE.finditer(text):
        if m.group("q"):
            out.add(f"Q{m.group('q')}{m.group('qy')}")
        elif m.group("p"):
            out.add(f"P{m.group('p')}FY{m.group('py')}")
    return out


def _file_cite(leaf) -> Citation:
    return Citation(kind="file", file_hash=leaf.file_hash)


def detect_period_conflicts(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """Artifacts whose fiscal-period token disagrees with the package's
    dominant period - prior-quarter evidence recycled into this period's pack."""
    per_leaf: dict[str, set[str]] = {}
    for leaf in graph.leaves.values():
        toks = _period_tokens(leaf.logical_path)
        if toks:
            per_leaf[leaf.file_hash] = toks
    votes = Counter(t for toks in per_leaf.values() for t in toks)
    quarters = {t for t in votes if t.startswith("Q")}
    if not quarters:
        return []
    dominant = max(quarters, key=lambda t: votes[t])
    out = []
    excluded = [h.lower() for ex in plan.scope_exclusions for h in ex.match_hints]
    for fh, toks in sorted(per_leaf.items()):
        leaf = graph.leaves[fh]
        others = {t for t in toks if t.startswith("Q")} - {dominant}
        if not others:
            continue
        if any(h in leaf.logical_path.lower() for h in excluded):
            out.append(Anomaly(detector="period_conflict", severity="info",
                               detail=f"{leaf.logical_path}: period {sorted(others)} vs dominant "
                                      f"{dominant}, but excluded from scope by the approved plan",
                               citations=[_file_cite(leaf)]))
        else:
            out.append(Anomaly(detector="period_conflict", severity="warn",
                               detail=f"{leaf.logical_path}: carries period {sorted(others)} but this "
                                      f"package's dominant period is {dominant} - verify this is an "
                                      f"intended comparative, not recycled prior-period evidence",
                               citations=[_file_cite(leaf)]))
    return out


def detect_duplicate_artifacts(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """The same bytes appearing under multiple names. Within one package this
    is usually custody (a file both loose and inside the approval email) but
    it must be on the record: identical hashes mean nobody re-ran anything."""
    by_path: dict[str, list[str]] = defaultdict(list)
    for leaf in graph.leaves.values():
        by_path[leaf.file_hash].append(leaf.logical_path)
    out = []
    for fh, paths in sorted(by_path.items()):
        if len(paths) > 1:
            out.append(Anomaly(detector="duplicate_artifact", severity="info",
                               detail=f"identical bytes at {len(paths)} locations: "
                                      f"{' | '.join(sorted(paths)[:3])}",
                               citations=[Citation(kind="file", file_hash=fh)]))
    return out


def detect_placeholders(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """Evidence that is not actually in the package: SharePoint .url/.lnk
    stubs, zero-byte leaves, and containers that failed to open."""
    out = []
    for leaf in sorted(graph.leaves.values(), key=lambda l: l.logical_path):
        if leaf.kind == "link":
            out.append(Anomaly(detector="placeholder", severity="high",
                               detail=f"{leaf.logical_path}: is a link, not the artifact - the "
                                      f"evidence itself is outside the package",
                               citations=[_file_cite(leaf)]))
        elif leaf.size == 0:
            out.append(Anomaly(detector="placeholder", severity="high",
                               detail=f"{leaf.logical_path}: zero bytes",
                               citations=[_file_cite(leaf)]))
    for err in graph.errors:
        out.append(Anomaly(detector="placeholder", severity="warn",
                           detail=f"unreadable artifact recorded at ingest: {err}"))
    return out


def detect_pasted_constants(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """Cells the plan's numeric checks rely on that hold hard values where a
    formula would be expected. A recon 'delta' that is a typed 0 instead of a
    computed difference is the classic way a reconciliation is faked."""
    out = []
    for check in plan.checks:
        if check.check_type != "numeric":
            continue
        p = check.params
        tgt = p.get("target")
        if not tgt:
            continue
        # locate by sheet+cell across matched files: the check node resolves
        # matches at runtime; here we scan every file having that sheet+cell
        for cf in graph.cells.values():
            if cf.sheet == tgt.get("sheet") and cf.cell == tgt.get("cell"):
                if not getattr(cf, "is_formula", False):
                    out.append(Anomaly(
                        detector="pasted_constant", severity="warn",
                        detail=f"check {check.id}: target {cf.sheet}!{cf.cell} holds a constant "
                               f"({cf.value!r}), not a formula - if this is a recomputed total, "
                               f"it should compute, not assert",
                        citations=[Citation(kind="cell", file_hash=cf.file_hash,
                                            sheet=cf.sheet, cell=cf.cell)]))
    return out


def detect_tolerance_gaming(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """Delta values that pass, but only just: within [tol/10, tol] of the
    threshold. A genuine recon residue is orders of magnitude below tolerance;
    a value parked at 0.009 against tol 0.01 deserves a human eye."""
    out = []
    for check in plan.checks:
        if check.check_type != "numeric":
            continue
        p = check.params
        tol = float(p.get("tolerance", 0.01))
        src = p.get("source", {})
        for cellref in src.get("cells", []):
            for cf in graph.cells.values():
                if cf.sheet == src.get("sheet") and cf.cell == cellref:
                    try:
                        v = abs(float(cf.value))
                    except (TypeError, ValueError):
                        continue
                    if tol / 10 <= v <= tol:
                        out.append(Anomaly(
                            detector="tolerance_edge", severity="warn",
                            detail=f"check {check.id}: {cf.sheet}!{cf.cell} = {cf.value} sits "
                                   f"within a factor of 10 of tolerance {tol} - passes, but barely",
                            citations=[Citation(kind="cell", file_hash=cf.file_hash,
                                                sheet=cf.sheet, cell=cf.cell)]))
    return out


def detect_single_actor(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    """Sign-off chains where the declared preparer is also the sender of the
    approval - segregation of duties broken before the signoff check runs."""
    preparers = set()
    for check in plan.checks:
        if check.check_type == "signoff" and "preparer" in check.params:
            preparers.add(check.params["preparer"].lower())
    out = []
    for mid, em in sorted(graph.emails.items()):
        sender = (em.sender or "").lower()
        for prep in preparers:
            if prep and prep in sender:
                out.append(Anomaly(
                    detector="single_actor", severity="high",
                    detail=f"approval email {em.subject!r} sent by the declared preparer "
                           f"({em.sender}) - preparer and approver collapse to one person",
                    citations=[Citation(kind="email", file_hash=em.file_hash,
                                        email_message_id=mid, line=1)]))
    return out


DETECTORS = [detect_period_conflicts, detect_duplicate_artifacts, detect_placeholders,
             detect_pasted_constants, detect_tolerance_gaming, detect_single_actor]


def run_sentinel(graph: EvidenceGraph, plan: ValidationPlan) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for det in DETECTORS:
        anomalies.extend(det(graph, plan))
    return anomalies
