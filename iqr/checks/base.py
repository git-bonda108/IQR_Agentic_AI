"""Shared helpers for check execution.

A check receives the frozen CheckDef, the Evidence Graph, and the match table
(evidence_id -> resolved artifact). It returns a Finding whose computed_values
and citations come exclusively from deterministic tools.
"""
from __future__ import annotations

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation, Finding
from iqr.schemas.validation_plan import CheckDef
from iqr.tools.citation import doc_citation, file_citation


def requirement_citation(graph: EvidenceGraph) -> Citation:
    """Ground a missing-evidence claim in the 404 process document that states
    the requirement (it is part of the package tree); fall back to the package
    leaf listing. The citation MUST resolve - a gap finding that the citation
    gate rejects would silently vanish from the human queue."""
    for file_hash in sorted(graph.docs):
        if graph.docs[file_hash].paragraphs:  # table-only docs have none
            return doc_citation(file_hash, 1)
    first = sorted(graph.leaves)[0]
    return file_citation(first)


def gap_finding(check: CheckDef, graph: EvidenceGraph, detail: str) -> Finding:
    return Finding(check_id=check.id, verdict="gap", detail=detail,
                   citations=[requirement_citation(graph)])


def missing_inputs(check: CheckDef, matches: dict) -> list[str]:
    return [ev_id for ev_id in check.inputs if ev_id not in matches]
