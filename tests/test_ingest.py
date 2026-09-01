"""Phase 1 acceptance + invariant 7 (chain of custody)."""
from pathlib import Path

from iqr.ingest.graph_builder import build_evidence_graph


def test_nested_tree_fully_unpacked(graphs):
    g = graphs["C10032"]
    paths = {l.logical_path for l in g.leaves.values()}
    assert "approval_C10032.eml!recon_support.zip" in paths
    assert "approval_C10032.eml!recon_support.zip!ic_elims_summary.xlsx" in paths
    assert "approval_C10032.eml!recon_support.zip!recon_checklist.docx" in paths
    # the nested workbook's cells are addressable facts
    nested_wb = next(l for l in g.leaves.values()
                     if l.logical_path.endswith("ic_elims_summary.xlsx"))
    assert g.get_cell(nested_wb.file_hash, "Elims", "B5").value == 17200.0


def test_every_fact_is_addressable(graphs):
    g = graphs["C23024"]
    wb = next(l for l in g.leaves.values() if l.kind == "xlsx")
    assert g.get_cell(wb.file_hash, "Sales", "B7").value == 454000.0
    assert len(g.emails) == 1
    em = next(iter(g.emails.values()))
    assert em.attachment_hashes == []  # C23024 email has no attachments


def test_chain_of_custody_reingest_identical_hashes(fixtures_root):
    """Invariant 7: re-ingest yields byte-identical hashes for every leaf."""
    a = build_evidence_graph(str(fixtures_root / "C10032" / "package"))
    b = build_evidence_graph(str(fixtures_root / "C10032" / "package"))
    assert set(a.leaves) == set(b.leaves)
    assert {l.logical_path for l in a.leaves.values()} == \
           {l.logical_path for l in b.leaves.values()}
    # containment (email -> zip -> workbook) is recorded and stable
    assert {l.parent_hash for l in a.leaves.values()} == \
           {l.parent_hash for l in b.leaves.values()}


def test_hashes_present_in_citations(plans, graphs, fixtures_root):
    """Every citation carries the leaf's SHA-256 (custody appears in output)."""
    from iqr.graph.build_graph import run_control
    verdict = run_control(plans["C23024"], str(fixtures_root / "C23024" / "package"),
                          run_id="test-custody")
    g = graphs["C23024"]
    for f in verdict.findings:
        for c in f.citations:
            assert c.file_hash in g.leaves or c.file_hash in g.images
