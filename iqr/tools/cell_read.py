"""Read a workbook cell from the Evidence Graph -> (value, Citation)."""
from __future__ import annotations

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation
from iqr.tools.citation import cell_citation


class CellNotFound(Exception):
    pass


def cell_read(graph: EvidenceGraph, file_hash: str, sheet: str, cell: str):
    fact = graph.get_cell(file_hash, sheet, cell)
    if fact is None:
        raise CellNotFound(f"{sheet}!{cell} not present in workbook {file_hash[:12]}")
    return fact.value, cell_citation(file_hash, sheet, cell)


def range_read(graph: EvidenceGraph, file_hash: str, sheet: str,
               cells: list[str]) -> tuple[list, list[Citation]]:
    values, cites = [], []
    for c in cells:
        v, cite = cell_read(graph, file_hash, sheet, c)
        values.append(v)
        cites.append(cite)
    return values, cites
