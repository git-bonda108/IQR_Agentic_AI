"""Phase 7 acceptance: the harness runs all three controls + seeded variants
and every gate passes. Also the audit pack ships complete and cited."""
import zipfile

from iqr.eval.harness import run_eval
from iqr.graph.build_graph import run_control
from iqr.ingest.graph_builder import build_evidence_graph
from iqr.pack.assemble import assemble_pack


def test_all_gates_pass(plans, fixtures_root, tmp_path):
    report = run_eval(plans, fixtures_root, tmp_path / "variants")
    assert report.citation_validity == 1.0, report.summary()
    assert report.defect_recall == 1.0, report.summary()
    assert report.false_exception_rate == 0.0, report.summary()
    assert report.abstention_correctness == 1.0, report.summary()
    assert report.reproducibility == 1.0, report.summary()
    assert report.gates_passed


def test_audit_pack_contents(plans, fixtures_root):
    pkg = str(fixtures_root / "C10075" / "package")
    verdict = run_control(plans["C10075"], pkg, run_id="test-pack")
    graph = build_evidence_graph(pkg)
    pack = assemble_pack(verdict, plans["C10075"], graph, unmatched_leaves=[])
    with zipfile.ZipFile(pack.pack_path) as zf:
        names = set(zf.namelist())
        assert {"verdict.json", "checklist.md", "gaps_and_observations.md",
                "artifact_manifest.json", "citations.json", "plan.json"} <= names
        checklist = zf.read("checklist.md").decode()
    assert "v1" in checklist and "s1" in checklist
    assert all(item.result in ("pass", "gap", "fail") for item in pack.checklist)


def test_governed_learning_gate(tmp_path):
    """Phase 9: nothing ships to the Golden Library without eval + SME."""
    import pytest
    from iqr.knowledge.golden_library import GoldenLibrary
    from iqr.knowledge.store import LocalVectorStore
    lib = GoldenLibrary(store=LocalVectorStore(tmp_path / "gl.json"))
    ex = lib.record_adjudication("C23024", "n1", "rounding delta under half a cent",
                                 "pass", "immaterial rounding", "run-x")
    with pytest.raises(PermissionError, match="regression eval"):
        lib.release_exemplar(ex, eval_passed=False, sme="sme")
    with pytest.raises(PermissionError, match="SME sign-off"):
        lib.release_exemplar(ex, eval_passed=True, sme="")
    lib.release_exemplar(ex, eval_passed=True, sme="sme")
    hits = lib.similar_adjudications("rounding delta")
    assert hits and hits[0]["metadata"]["human_verdict"] == "pass"
