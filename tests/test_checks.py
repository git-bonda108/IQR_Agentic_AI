"""Phase 3 acceptance + invariant 1 (no model math)."""
import pytest

from iqr import config
from iqr.checks.dispatch import run_check
from iqr.graph.nodes.match_node import match_evidence


def _run(plans, graphs, cid, check_id):
    plan = plans[cid]
    graph = graphs[cid]
    matches, _missing, _ = match_evidence(plan, graph)
    return run_check(plan.check_by_id(check_id), plan, graph, matches)


def test_numeric_path_makes_zero_model_calls(plans, graphs):
    """Invariant 1: numeric checks are pure Python - no model, ever."""
    before = config.model_call_count()
    f1 = _run(plans, graphs, "C23024", "n1")
    f2 = _run(plans, graphs, "C23024", "n2")
    f3 = _run(plans, graphs, "C10032", "d1")
    assert config.model_call_count() == before, "a model was invoked on a numeric path"
    assert [f.verdict for f in (f1, f2, f3)] == ["pass", "pass", "pass"]


def test_vision_check_reads_screenshot(plans, graphs):
    f = _run(plans, graphs, "C10075", "v1")
    assert f.verdict == "pass"
    assert any(c.kind == "image" for c in f.citations)
    assert any(c.kind == "cell" for c in f.citations)


def test_temporal_check_normalizes_gmt_vs_cdt(plans, graphs):
    f = _run(plans, graphs, "C10032", "t1")
    assert f.verdict == "pass"
    assert "2026-06-03T09:15:00+00:00" in f.detail       # GMT cell -> UTC
    assert "2026-06-03T13:45:00+00:00" in f.detail       # CDT email -> UTC


def test_signoff_check_sod_and_order(plans, graphs):
    f = _run(plans, graphs, "C23024", "s1")
    assert f.verdict == "pass"
    assert "ravi.mehta" in f.detail
    assert any(c.kind == "email" for c in f.citations)


def test_computed_values_come_from_tools(plans, graphs):
    """Numbers in a finding are echoes of tool output, never model-generated."""
    f = _run(plans, graphs, "C23024", "n1")
    assert f.computed_values["sources"] == [125000.0, 98000.0, 143000.0, 88000.0]
    assert f.computed_values["computed"] == 454000.0
