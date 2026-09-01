"""Invariants 4 (honest missing), 5 (scope respected), 6 (blinded verify)."""
import shutil
from pathlib import Path

from iqr.eval.seed_defects import copy_package, remove_artifact
from iqr.graph.build_graph import run_control
from iqr.graph.nodes.match_node import match_evidence
from iqr.graph.nodes.verify_node import VerifierInput, blinded_verify
from iqr.ingest.graph_builder import build_evidence_graph
from iqr.pack.assemble import assemble_pack


def test_honest_missing_never_pass(plans, fixtures_root, tmp_path):
    """Invariant 4: required evidence absent -> gap, never pass, never invented."""
    pkg = copy_package(fixtures_root / "C23024" / "package", tmp_path / "no_signoff")
    remove_artifact(pkg, "approval_C23024.eml")
    verdict = run_control(plans["C23024"], str(pkg), run_id="test-missing")
    s1 = next(f for f in verdict.findings if f.check_id == "s1")
    assert s1.verdict == "gap"
    assert verdict.result != "pass"
    assert any("e_approval" in g for g in verdict.gaps)


def test_scope_exclusion_never_flagged(plans, graphs, fixtures_root, tmp_path):
    """Invariant 5: the IC-elims workbook (nonzero open items!) is in the pack,
    but the SME-approved exclusion means it is never an observation or finding -
    while a genuinely unexpected artifact IS surfaced."""
    plan = plans["C10032"]
    g = graphs["C10032"]
    _m, _missing, unmatched = match_evidence(plan, g)
    assert not any("ic_elims" in u for u in unmatched)

    pkg = copy_package(fixtures_root / "C10032" / "package", tmp_path / "stray")
    (pkg / "stray_unexplained_extract.xlsx").write_bytes(
        (fixtures_root / "C10032" / "package" / "consolidation_recon_May2026.xlsx").read_bytes())
    g2 = build_evidence_graph(str(pkg))
    _m2, _missing2, unmatched2 = match_evidence(plan, g2)
    assert any("stray_unexplained_extract" in u for u in unmatched2)


def test_verifier_input_is_structurally_blind():
    """Invariant 6: the verifier's input type cannot even represent the
    executor's reasoning - no detail, no observations, no transcript."""
    fields = set(VerifierInput.model_fields)
    assert fields == {"check", "claimed_verdict", "citations"}


def test_verifier_catches_tampered_verdict(plans, graphs, fixtures_root):
    """Flip an executor verdict; the blinded re-performance must disagree."""
    from iqr.checks.dispatch import run_check
    plan = plans["C23024"]
    g = graphs["C23024"]
    matches, _, _ = match_evidence(plan, g)
    f = run_check(plan.check_by_id("n1"), plan, g, matches)
    tampered = f.model_copy(update={"verdict": "fail"})
    agree, note = blinded_verify(tampered, plan.check_by_id("n1"), g, matches)
    assert not agree and "CONTRADICTS" in note


def test_verifier_disagreement_routes_to_exception_queue(plans, fixtures_root, tmp_path, monkeypatch):
    """End-to-end: a disagreement lands in the human exception queue, and the
    control verdict is not a clean pass."""
    import iqr.graph.nodes.verify_node as vn
    real = vn.blinded_verify
    def sabotage(finding, check, graph, matches, ledger=None):
        if finding.check_id == "n1":
            return False, "forced disagreement (test)"
        return real(finding, check, graph, matches, ledger)
    monkeypatch.setattr(vn, "blinded_verify", sabotage)
    verdict = run_control(plans["C23024"], str(fixtures_root / "C23024" / "package"),
                          run_id="test-disagree")
    assert any("disagreement" in e for e in verdict.exceptions)
    assert verdict.result == "pass_with_gaps"
