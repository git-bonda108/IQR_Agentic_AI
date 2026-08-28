"""Anomaly Sentinel: every detector fires on its seeded pattern and stays
silent on clean evidence. Deterministic - no model on this path."""
from __future__ import annotations

from iqr.checks.sentinel import run_sentinel
from iqr.schemas.evidence_graph import CellFact, EmailFact, EvidenceGraph, EvidenceLeaf
from iqr.schemas.validation_plan import (CheckDef, ExpectedEvidence, ScopeExclusion,
                                         SignoffRule, ValidationPlan)


def _leaf(h, path, kind="xlsx", size=100):
    return EvidenceLeaf(file_hash=h, logical_path=path, kind=kind, size=size,
                        parent_hash=None, stored_path=f"/tmp/{h}")


def _plan(**kw):
    base = dict(control_id="CTEST", version="1.0.0", frequency="quarterly",
                expected_evidence=[ExpectedEvidence(id="e1", description="wb",
                                                    match_hints=["recon"])],
                checks=[], scope_exclusions=[], signoff=None)
    base.update(kw)
    return ValidationPlan(**base)


def _graph(leaves, cells=(), emails=(), errors=()):
    g = EvidenceGraph(package_id="test")
    for l in leaves:
        g.leaves[l.file_hash] = l
    for c in cells:
        g.cells[EvidenceGraph.cell_key(c.file_hash, c.sheet, c.cell)] = c
    for e in emails:
        g.emails[e.message_id] = e
    g.errors.extend(errors)
    return g


def test_period_conflict_flags_recycled_quarter():
    g = _graph([_leaf("a" * 64, "Recon_Q226.xlsx"),
                _leaf("b" * 64, "IPE_Q226_summary.xlsx"),
                _leaf("c" * 64, "Validation_Q126_final.xlsx")])
    anomalies = run_sentinel(g, _plan())
    hits = [a for a in anomalies if a.detector == "period_conflict"]
    assert len(hits) == 1 and hits[0].severity == "warn"
    assert "Q126" in hits[0].detail and "Q226" in hits[0].detail


def test_period_conflict_respects_scope_exclusion():
    g = _graph([_leaf("a" * 64, "Recon_Q226.xlsx"),
                _leaf("b" * 64, "IPE_Q226_summary.xlsx"),
                _leaf("c" * 64, "prior_year_Q126_comparative.xlsx")])
    plan = _plan(scope_exclusions=[ScopeExclusion(id="x1", reason="comparative only",
                                                  match_hints=["prior_year"])])
    hits = [a for a in run_sentinel(g, plan) if a.detector == "period_conflict"]
    assert len(hits) == 1 and hits[0].severity == "info"
    assert "excluded from scope" in hits[0].detail


def test_duplicate_artifact_noted():
    g = _graph([_leaf("a" * 64, "loose/recon.xlsx"),
                _leaf("b" * 64, "other.xlsx")])
    # same hash, second location
    g.leaves["a" * 64] = _leaf("a" * 64, "loose/recon.xlsx")
    dup = _leaf("a" * 64, "mail.msg!recon.xlsx")
    # graph keyed by hash keeps one leaf; simulate the multi-path case the
    # detector sees when unpack records both paths before dedupe
    g2 = EvidenceGraph(package_id="test")
    g2.leaves["a" * 64] = _leaf("a" * 64, "loose/recon.xlsx")
    g2.leaves["d" * 64] = dup.model_copy(update={"file_hash": "d" * 64})
    # true duplicate case: two leaves, same hash is impossible in a dict -
    # detector works on hash collisions across paths, so feed it directly
    from iqr.checks.sentinel import detect_duplicate_artifacts
    class TwoPaths:
        leaves = {"k1": _leaf("a" * 64, "loose/recon.xlsx"),
                  "k2": _leaf("a" * 64, "mail.msg!recon.xlsx")}
    hits = detect_duplicate_artifacts(TwoPaths, _plan())
    assert len(hits) == 1 and "2 locations" in hits[0].detail


def test_placeholder_link_is_high():
    g = _graph([_leaf("a" * 64, "evidence.url", kind="link"),
                _leaf("b" * 64, "empty.xlsx", size=0)],
               errors=["unreadable artifact: x.xlsb (BadZipFile)"])
    hits = [a for a in run_sentinel(g, _plan()) if a.detector == "placeholder"]
    sev = sorted(a.severity for a in hits)
    assert sev == ["high", "high", "warn"]


def test_pasted_constant_on_numeric_target():
    cells = [CellFact(file_hash="a" * 64, sheet="Recon", cell="B5", value=0.0,
                      is_formula=False)]
    plan = _plan(checks=[CheckDef(id="d1", check_type="numeric", description="",
                                  inputs=["e1"],
                                  params={"op": "sum_equals",
                                          "source": {"evidence": "e1", "sheet": "Recon",
                                                     "cells": ["B2"]},
                                          "target": {"evidence": "e1", "sheet": "Recon",
                                                     "cell": "B5"},
                                          "tolerance": 0.01})])
    g = _graph([_leaf("a" * 64, "recon.xlsx")], cells=cells)
    hits = [a for a in run_sentinel(g, plan) if a.detector == "pasted_constant"]
    assert len(hits) == 1 and "constant" in hits[0].detail


def test_tolerance_edge_flagged():
    cells = [CellFact(file_hash="a" * 64, sheet="Recon", cell="D2", value=0.009,
                      is_formula=True)]
    plan = _plan(checks=[CheckDef(id="d1", check_type="numeric", description="",
                                  inputs=["e1"],
                                  params={"op": "delta_zero",
                                          "source": {"evidence": "e1", "sheet": "Recon",
                                                     "cells": ["D2", "I2"]},
                                          "target": {"evidence": "e1", "sheet": "Recon",
                                                     "cell": "D2"},
                                          "tolerance": 0.01})])
    g = _graph([_leaf("a" * 64, "recon.xlsx")], cells=cells)
    hits = [a for a in run_sentinel(g, plan) if a.detector == "tolerance_edge"]
    assert len(hits) == 1 and "barely" in hits[0].detail


def test_single_actor_chain_is_high():
    em = EmailFact(file_hash="a" * 64, message_id="<m1@x>", sender="Prep Arer <prep@hp.com>",
                   to=["boss@hp.com"], date_raw="2026-05-01", subject="Approval",
                   lines=["approved"], attachment_hashes=[])
    plan = _plan(checks=[CheckDef(id="s1", check_type="signoff", description="",
                                  inputs=["e1"],
                                  params={"approval_email_evidence": "e1",
                                          "preparer": "prep@hp.com"})],
                 signoff=SignoffRule(preparer_role="p", approver_role="a"))
    g = _graph([_leaf("a" * 64, "mail.eml", kind="email")], emails=[em])
    hits = [a for a in run_sentinel(g, plan) if a.detector == "single_actor"]
    assert len(hits) == 1 and hits[0].severity == "high"


def test_clean_pack_is_quiet():
    cells = [CellFact(file_hash="a" * 64, sheet="Recon", cell="B5", value=0.0,
                      is_formula=True)]
    g = _graph([_leaf("a" * 64, "Recon_Q226.xlsx"),
                _leaf("b" * 64, "IPE_Q226.xlsx")], cells=cells)
    anomalies = run_sentinel(g, _plan())
    assert [a for a in anomalies if a.severity in ("warn", "high")] == []
