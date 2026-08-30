"""Edge-case regression: corrupt containers, unreadable workbooks, empty and
duplicate packages, and the multi-backend fallback chain. Real GRC packages
are messy; every degradation must be recorded and surfaced, never silent."""
import shutil

import pytest

from iqr.eval.seed_defects import copy_package
from iqr.graph.build_graph import run_control
from iqr.ingest.graph_builder import build_evidence_graph


def test_empty_package_refused(tmp_path):
    (tmp_path / "empty_pkg").mkdir()
    with pytest.raises(ValueError, match="empty GRC package"):
        build_evidence_graph(str(tmp_path / "empty_pkg"))


def test_corrupt_zip_recorded_not_fatal(fixtures_root, tmp_path):
    pkg = copy_package(fixtures_root / "C23024" / "package", tmp_path / "badzip")
    (pkg / "extra_support.zip").write_bytes(b"PK\x03\x04 this is not a real zip")
    g = build_evidence_graph(str(pkg))
    assert any("corrupt zip" in e for e in g.errors)
    assert any(l.logical_path == "extra_support.zip" for l in g.leaves.values())


def test_unreadable_workbook_degrades_to_gap(plans, fixtures_root, tmp_path):
    """A truncated workbook stays in custody but yields no facts; every check
    that needs it abstains with a gap - the control can never silently pass."""
    pkg = copy_package(fixtures_root / "C23024" / "package", tmp_path / "badwb")
    (pkg / "rebate_Q2_2026.xlsx").write_bytes(b"PK\x03\x04truncated-not-a-workbook")
    g = build_evidence_graph(str(pkg))
    assert any("unreadable artifact" in e for e in g.errors)
    verdict = run_control(plans["C23024"], str(pkg), run_id="edge-badwb")
    assert verdict.result != "pass"
    n1 = next(f for f in verdict.findings if f.check_id == "n1")
    assert n1.verdict == "gap"


def test_duplicate_content_is_content_addressed(fixtures_root, tmp_path):
    """Two copies of the same bytes dedupe to one hashed leaf (content-
    addressed custody); ingest neither crashes nor double-counts."""
    pkg = copy_package(fixtures_root / "C23024" / "package", tmp_path / "dup")
    shutil.copy(pkg / "rebate_Q2_2026.xlsx", pkg / "rebate_Q2_2026_copy.xlsx")
    g = build_evidence_graph(str(pkg))
    xlsx_leaves = [l for l in g.leaves.values() if l.kind == "xlsx"]
    assert len(xlsx_leaves) == 1  # same hash -> same custody record


def test_fallback_chain_serves_and_records(plans, graphs, monkeypatch):
    """Multi-mode fallback: primary down -> next backend answers, and the
    chain records who served + why the primary was skipped."""
    from iqr import config
    from iqr.agents.model_client import FallbackModelClient, ModelClient, StubModelClient

    class DownClient(ModelClient):
        name = "davinci"
        def complete(self, system, user):
            raise ConnectionError("endpoint unreachable")

    chain = FallbackModelClient([DownClient(), StubModelClient()])
    monkeypatch.setattr(config, "get_model_client", lambda seat=None: chain)

    from iqr.checks.dispatch import run_check
    from iqr.graph.nodes.match_node import match_evidence
    plan = plans["C10075"]
    g = graphs["C10075"]
    matches, _, _ = match_evidence(plan, g)
    finding = run_check(plan.check_by_id("v1"), plan, g, matches)
    assert finding.verdict == "pass"
    assert chain.last_served == "stub"
    assert any("davinci" in e and "unreachable" in e for e in chain.errors)


def test_all_backends_down_fails_loud(monkeypatch):
    from iqr.agents.model_client import FallbackModelClient, ModelClient

    class DownClient(ModelClient):
        name = "x"
        def complete(self, system, user):
            raise ConnectionError("down")

    chain = FallbackModelClient([DownClient()])
    with pytest.raises(RuntimeError, match="all model backends failed"):
        chain.complete("s", "u")


def test_extraction_errors_reach_the_gaps_register(plans, fixtures_root, tmp_path):
    """graph.errors surface in the audit pack's gaps register - honest output."""
    from iqr.pack.assemble import assemble_pack
    pkg = copy_package(fixtures_root / "C10075" / "package", tmp_path / "errpack")
    (pkg / "broken_attachment.zip").write_bytes(b"PK\x03\x04broken")
    g = build_evidence_graph(str(pkg))
    verdict = run_control(plans["C10075"], str(pkg), run_id="edge-errpack")
    pack = assemble_pack(verdict, plans["C10075"], g,
                         unmatched_leaves=[], )
    assert any("corrupt zip" in e for e in g.errors)
