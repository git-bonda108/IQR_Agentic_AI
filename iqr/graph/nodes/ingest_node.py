"""Ingest node: deterministic Python, no model. Builds the Evidence Graph."""
from __future__ import annotations

from iqr.ingest.graph_builder import build_evidence_graph
from iqr.ledger import RunLedger


def ingest_node(state: dict) -> dict:
    graph = build_evidence_graph(state["package_ref"])
    RunLedger(state["run_id"]).log(
        "ingest", package=state["package_ref"], leaves=len(graph.leaves),
        cells=len(graph.cells), emails=len(graph.emails), images=len(graph.images),
        errors=graph.errors)
    return {"evidence": graph}
