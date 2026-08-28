"""Invariant 2: a fabricated locator can never enter a Verdict or a pack."""
import pytest

from iqr.graph.nodes.adjudicate_node import adjudicate
from iqr.pack.assemble import assemble_pack
from iqr.schemas.finding import Citation, Finding, Verdict
from iqr.tools.citation import gate_finding


def _fabricated_finding():
    return Finding(check_id="nX", verdict="pass", detail="fabricated claim",
                   citations=[Citation(kind="cell", file_hash="0" * 64,
                                       sheet="Nowhere", cell="Z99")])


def test_fabricated_citation_does_not_resolve(graphs):
    ok, problems = gate_finding(_fabricated_finding(), graphs["C23024"])
    assert not ok and "does not resolve" in problems[0]


def test_real_citation_resolves(graphs):
    g = graphs["C23024"]
    wb = next(l for l in g.leaves.values() if l.kind == "xlsx")
    f = Finding(check_id="n1", verdict="pass", detail="real",
                citations=[Citation(kind="cell", file_hash=wb.file_hash,
                                    sheet="Sales", cell="B7")])
    ok, _ = gate_finding(f, g)
    assert ok


def test_adjudicator_rejects_uncited_claim(plans, graphs):
    verdict = adjudicate(plans["C23024"], graphs["C23024"],
                         [_fabricated_finding()], [], [], "test-gate")
    assert verdict.findings == []                       # claim never entered
    assert any("CITATION GATE" in e for e in verdict.exceptions)


def test_pack_assembly_blocks_unresolved_citation(plans, graphs):
    bad = Verdict(control_id="C23024", plan_version="1.0.0", result="pass",
                  findings=[_fabricated_finding()], gaps=[], run_id="test-bad")
    with pytest.raises(ValueError, match="citation gate"):
        assemble_pack(bad, plans["C23024"], graphs["C23024"])


def test_finding_without_citations_rejected(graphs):
    f = Finding(check_id="n1", verdict="pass", detail="claim", citations=[])
    ok, problems = gate_finding(f, graphs["C23024"])
    assert not ok and "no citations" in problems[0]
