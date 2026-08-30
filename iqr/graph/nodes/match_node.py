"""Match node: map each expected-evidence item in the frozen plan to artifacts
in the Evidence Graph. Two mechanisms, both deterministic and both recorded:

  1. NAME match - fuzzy on the plan's match_hints vs the artifact path.
  2. SEMANTIC match - the embedding seat compares each artifact's CONTENT
     SIGNALS (path, kind, sheet names, email subject + opening lines, document
     paragraphs) against the plan item's meaning (description + hints + the
     checks that read it). This is what relates a real-world
     `RE__Q226_EMR_Sing_off_request-JU.eml` to "quarterly sign-off approval
     email" when no filename trick would.

Name match wins when it fires (it is exact-by-construction); semantics rescue
what names miss. Every match records its method and score in the ledger -
auditors see WHY an artifact was chosen. HONEST about misses: absent required
evidence becomes a gap, never a silent pass."""
from __future__ import annotations

import difflib

from iqr.knowledge.embeddings import Embedder, cosine
from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.validation_plan import ExpectedEvidence, ValidationPlan

# Cosine floor for a semantic rescue, per embedding backend: real embedding
# models produce higher cosines than the hashed offline fallback, and the
# kind constraint (below) already carries most of the precision.
SEMANTIC_MIN = {"foundry-embedding": 0.25, "hashed": 0.08}


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


def leaf_descriptor(leaf, graph: EvidenceGraph) -> str:
    """The artifact as text: what it is called, what kind it is, and what its
    CONTENT says it is - sheet names for workbooks, subject + sender + opening
    body lines for emails, leading paragraphs for documents."""
    parts = [leaf.logical_path.replace("!", " "), leaf.kind]
    if leaf.kind in ("xlsx", "xlsb"):
        sheets = {k.split("|")[1] for k in graph.cells if k.startswith(leaf.file_hash)}
        parts.extend(sorted(sheets)[:12])
    elif leaf.kind == "email":
        for em in graph.emails.values():
            if em.file_hash == leaf.file_hash:
                parts.extend([em.subject, em.sender, " ".join(em.lines[:5])])
                break
    elif leaf.kind == "docx":
        doc = graph.docs.get(leaf.file_hash)
        if doc:
            parts.append(" ".join(doc.paragraphs[:8])[:600])
    return " ".join(str(p) for p in parts if p)


def _evidence_descriptor(ev: ExpectedEvidence, plan: ValidationPlan) -> str:
    linked = [c.description for c in plan.checks if ev.id in c.inputs]
    return " ".join([ev.description, *ev.match_hints, *linked])


def _allowed_kinds(ev: ExpectedEvidence, plan: ValidationPlan) -> set[str]:
    """What KIND of artifact can satisfy this evidence? The checks that read
    it say so deterministically: a sign-off/temporal check's approval email
    must be an email; a numeric/vision check's cell source must be a workbook.
    This is reasoning from the plan, not filename guessing."""
    kinds: set[str] = set()
    for c in plan.checks:
        if ev.id not in c.inputs:
            continue
        p = c.params
        if p.get("approval_email_evidence") == ev.id or p.get("later_email_evidence") == ev.id:
            kinds.add("email")
        if p.get("image_evidence") == ev.id:
            kinds.update({"image", "xlsx", "docx"})   # screenshots live in workbooks/docs too
        for slot in ("source", "target", "earlier", "prepared_at"):
            ref = p.get(slot)
            if isinstance(ref, dict) and ref.get("evidence") == ev.id:
                kinds.update({"xlsx", "xlsb"})
    if not kinds:   # fall back to the description's own vocabulary
        text = (ev.description + " " + " ".join(ev.match_hints)).lower()
        if any(w in text for w in ("email", ".msg", ".eml", "approval", "sign-off", "signoff")):
            kinds.add("email")
        if any(w in text for w in ("workbook", "extract", "tb", "xls", "report", "recon", "ipe")):
            kinds.update({"xlsx", "xlsb"})
        if any(w in text for w in ("screenshot", "image", "slide")):
            kinds.update({"image", "xlsx", "docx"})
    return kinds or {"xlsx", "xlsb", "email", "docx", "image", "pdf", "other"}


def _semantic_scores(plan: ValidationPlan, unresolved: list[ExpectedEvidence],
                     leaves: list, graph: EvidenceGraph):
    """One embedding batch: unresolved plan items x candidate artifacts."""
    embedder = Embedder()
    texts = ([_evidence_descriptor(ev, plan) for ev in unresolved]
             + [leaf_descriptor(l, graph) for l in leaves])
    vecs = embedder.embed(texts)
    ev_vecs, leaf_vecs = vecs[:len(unresolved)], vecs[len(unresolved):]
    return ev_vecs, leaf_vecs, embedder.last_backend


def match_evidence(plan: ValidationPlan, graph: EvidenceGraph) -> tuple[dict, list[str], list[str]]:
    matches: dict = {}
    missing: list[str] = []
    matched_hashes: set[str] = set()

    # ---- pass 1: name match (exact-by-construction when it fires)
    unresolved: list[ExpectedEvidence] = []
    for ev in plan.expected_evidence:
        image_hits = [img.file_hash for img in sorted(graph.images.values(),
                                                      key=lambda i: i.logical_path)
                      if any(_score(h, img.logical_path) >= 0.6 for h in ev.match_hints)]
        leaf, _ = _best_leaf(ev, graph)
        if leaf is None and not image_hits:
            unresolved.append(ev)
            continue
        entry: dict = {"method": "name"}
        if leaf is not None:
            entry.update(file_hash=leaf.file_hash, logical_path=leaf.logical_path,
                         kind=leaf.kind)
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

    # ---- pass 2: semantic rescue for what names missed. Kind-constrained
    # (the plan's checks say what kind of artifact can satisfy each item) and
    # assigned globally best-pair-first, so a chatty email cannot steal the
    # workbook's slot just because it mentions the same topic.
    if unresolved:
        candidates = [l for l in sorted(graph.leaves.values(),
                                        key=lambda l: l.logical_path)
                      if l.kind != "zip" and l.file_hash not in matched_hashes]
        if candidates:
            ev_vecs, leaf_vecs, backend = _semantic_scores(
                plan, unresolved, candidates, graph)
            kinds = {ev.id: _allowed_kinds(ev, plan) for ev in unresolved}
            pairs = sorted(
                ((cosine(ev_vec, lv), ev, leaf)
                 for ev, ev_vec in zip(unresolved, ev_vecs)
                 for lv, leaf in zip(leaf_vecs, candidates)
                 if leaf.kind in kinds[ev.id]),
                key=lambda s: -s[0])
            taken: set[str] = set()
            floor = SEMANTIC_MIN.get(backend, 0.25)
            for score, ev, leaf in pairs:
                if score < floor:
                    break
                if ev.id in matches or leaf.file_hash in taken:
                    continue
                entry = {"method": "semantic", "score": round(score, 3),
                         "embedding_backend": backend,
                         "file_hash": leaf.file_hash,
                         "logical_path": leaf.logical_path, "kind": leaf.kind}
                if leaf.kind == "email":
                    for mid, em in graph.emails.items():
                        if em.file_hash == leaf.file_hash:
                            entry["message_id"] = mid
                            break
                matches[ev.id] = entry
                matched_hashes.add(leaf.file_hash)
                taken.add(leaf.file_hash)
    for ev in plan.expected_evidence:
        if ev.id not in matches and ev.required:
            missing.append(ev.id)

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
