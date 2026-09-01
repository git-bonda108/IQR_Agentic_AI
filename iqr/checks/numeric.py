"""Numeric checks: pure deterministic Python. NO model in the loop - the
invariant test asserts the model-call counter is untouched on this path."""
from __future__ import annotations

from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Finding
from iqr.schemas.validation_plan import CheckDef
from iqr.checks.base import gap_finding, missing_inputs
from iqr.tools.cell_read import CellNotFound, cell_read, range_read
from iqr.tools.recompute import recompute


def run_numeric_check(check: CheckDef, graph: EvidenceGraph, matches: dict,
                      ledger: RunLedger | None = None) -> Finding:
    missing = missing_inputs(check, matches)
    if missing:
        return gap_finding(check, graph,
                           f"required evidence missing for {check.id}: {', '.join(missing)}")
    p = check.params
    try:
        src = p["source"]
        src_hash = matches[src["evidence"]]["file_hash"]
        source_values, cites = range_read(graph, src_hash, src["sheet"], src["cells"])

        tgt = p["target"]
        tgt_hash = matches[tgt["evidence"]]["file_hash"]
        target_value, tcite = cell_read(graph, tgt_hash, tgt["sheet"], tgt["cell"])
        cites = cites + [tcite]
    except CellNotFound as e:
        return gap_finding(check, graph, f"{check.id}: expected cell absent - {e}")

    result = recompute(p["op"], source_values, target_value, float(p.get("tolerance", 0.01)))
    if ledger:
        ledger.log("tool_call", task=check.id, tool="recompute",
                   args={"op": p["op"], "sources": source_values, "target": target_value},
                   result={"ok": result.ok, "computed": result.computed, "delta": result.delta})
    verdict = "pass" if result.ok else "fail"
    detail = (f"{p['op']}: recomputed {result.computed:,.4f} vs recorded "
              f"{result.expected:,.4f} (delta {result.delta:,.4f}, "
              f"tol {p.get('tolerance', 0.01)}) -> {verdict}")
    return Finding(check_id=check.id, verdict=verdict, detail=detail, citations=cites,
                   computed_values={"sources": source_values, "target": target_value,
                                    "computed": result.computed, "delta": result.delta,
                                    "op": p["op"]})
