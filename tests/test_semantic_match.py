"""Semantic matching: artifacts relate to expected evidence by CONTENT, not
filename luck. Offline (hashed embedding fallback) - the Azure embedding seat
strengthens this further but the mechanism must work with no keys at all."""
import shutil

from iqr.graph.nodes.match_node import leaf_descriptor, match_evidence
from iqr.ingest.graph_builder import build_evidence_graph


def _renamed_package(src, tmp_path, mapping):
    pkg = tmp_path / "pkg"
    shutil.copytree(src, pkg)
    for old, new in mapping.items():
        for f in pkg.glob(old):
            f.rename(pkg / new)
    return pkg


def test_descriptor_carries_content_signals(plans, fixtures_root):
    graph = build_evidence_graph(str(fixtures_root / "C10032" / "package"))
    descs = {l.logical_path: leaf_descriptor(l, graph) for l in graph.leaves.values()}
    # a workbook's descriptor includes its SHEET NAMES, not just its filename
    wb = next(d for p, d in descs.items() if "consolidation_recon" in p)
    assert "Recon" in wb and "Meta" in wb
    # an email's descriptor includes subject, sender, and body opening
    em = next(d for p, d in descs.items() if p.endswith(".eml"))
    assert "@" in em and ("approv" in em.lower() or "consolidation" in em.lower())


def test_semantic_rescue_when_filenames_lie(plans, fixtures_root, tmp_path):
    """Rename every artifact to something a name-matcher cannot use. The
    matcher must still relate them by content - and record HOW it matched."""
    pkg = _renamed_package(
        fixtures_root / "C23024" / "package", tmp_path,
        {"*.xlsx": "workbook_a1.xlsx", "*.eml": "message_0001.eml"})
    plan = plans["C23024"]
    graph = build_evidence_graph(str(pkg))
    matches, missing, unmatched = match_evidence(plan, graph)
    assert not missing, f"semantic rescue failed: {missing}"
    for mid, m in matches.items():
        assert m["method"] in ("name", "semantic")
    # at least one item needed semantics (names were destroyed), and it says so
    sem = [m for m in matches.values() if m["method"] == "semantic"]
    assert sem and all("embedding_backend" in m and m["score"] > 0 for m in sem)
    # the email still resolves to a message id (sign-off check depends on it)
    assert any("message_id" in m for m in matches.values())


def test_name_match_still_wins_when_names_are_good(plans, fixtures_root):
    graph = build_evidence_graph(str(fixtures_root / "C23024" / "package"))
    matches, missing, _ = match_evidence(plans["C23024"], graph)
    assert not missing
    assert all(m["method"] == "name" for m in matches.values())
