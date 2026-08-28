"""Match node: map each expected-evidence item in the frozen plan to artifacts
in the Evidence Graph. Fuzzy on names/paths; HONEST about misses - absent
required evidence becomes a gap, never a silent pass."""
from __future__ import annotations

import difflib

from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.validation_plan import ExpectedEvidence, ValidationPlan


def _score(hint: str, path: str) -> float:
    h, p = hint.lower(), path.lower()
    if h in p:
        return 1.0
    return difflib.SequenceMatcher(None, h, p.rsplit("/", 1)[-1]).ratio()


def _best_leaf(ev: ExpectedEvidence, graph: EvidenceGraph):
    best, best_score = None, 0.0
    for leaf in graph.leaves.values():
        if leaf.kind == "zip":
            continue  # containers are custody nodes, not evidence themselves
        s = max((_score(h, leaf.logical_path) for h in ev.match_hints), default=0.0)
        if s > best_score:
            best, best_score = leaf, s
    return (best, best_score) if best_score >= 0.6 else (None, best_score)


def match_evidence(plan: ValidationPlan, graph: EvidenceGraph) -> tuple[dict, list[str], list[str]]:
    matches: dict = {}
    missing: list[str] = []
    matched_hashes: set[str] = set()

    for ev in plan.expected_evidence:
        image_hits = [img.file_hash for img in sorted(graph.images.values(),
                                                      key=lambda i: i.logical_path)
                      if any(_score(h, img.logical_path) >= 0.6 for h in ev.match_hints)]
        leaf, _ = _best_leaf(ev, graph)
        if leaf is None and not image_hits:
            if ev.required:
                missing.append(ev.id)
            continue
        entry: dict = {}
        if leaf is not None:
            entry["file_hash"] = leaf.file_hash
            entry["logical_path"] = leaf.logical_path
            entry["kind"] = leaf.kind
            matched_hashes.add(leaf.file_hash)
            if leaf.kind == "email":
                for mid, em in graph.emails.items():
                    if em.file_hash == leaf.file_hash:
                        entry["message_id"] = mid
                        break
        if image_hits:
            entry["image_hashes"] = image_hits
            matched_hashes.update(image_hits)
        matches[ev.id] = entry

    # artifacts present but not expected -> observations, EXCEPT scope-excluded
    # items, which must never be flagged (invariant: scope respected).
    excluded_hints = [h for ex in plan.scope_exclusions for h in ex.match_hints]
    unmatched = []
    for leaf in sorted(graph.leaves.values(), key=lambda l: l.logical_path):
        if leaf.file_hash in matched_hashes or leaf.kind in ("zip", "docx"):
            continue
        if any(_score(h, leaf.logical_path) >= 0.6 for h in excluded_hints):
            continue  # out of scope by SME-approved plan: not an observation
        if not any(leaf.file_hash == m.get("file_hash") for m in matches.values()):
            unmatched.append(leaf.logical_path)
    return matches, missing, unmatched


def match_node(state: dict) -> dict:
    plan: ValidationPlan = state["plan"]
    graph: EvidenceGraph = state["evidence"]
    matches, missing, unmatched = match_evidence(plan, graph)
    RunLedger(state["run_id"]).log(
        "match", matched=sorted(matches), missing=missing, unmatched=unmatched,
        resolution={eid: {"path": m.get("logical_path"),
                          "message_id": m.get("message_id")}
                    for eid, m in sorted(matches.items())})
    return {"matches": matches, "missing": missing, "unmatched_leaves": unmatched}
