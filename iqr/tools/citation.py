"""Build and resolve citation locators. The citation gate lives on top of this."""
from __future__ import annotations

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation, Finding


def cell_citation(file_hash: str, sheet: str, cell: str) -> Citation:
    return Citation(kind="cell", file_hash=file_hash, sheet=sheet, cell=cell)


def image_citation(image_hash: str, region: tuple[int, int, int, int] | None = None) -> Citation:
    return Citation(kind="image", file_hash=image_hash, image_hash=image_hash, ocr_region=region)


def email_citation(file_hash: str, message_id: str, line: int | None = None) -> Citation:
    return Citation(kind="email", file_hash=file_hash, email_message_id=message_id, line=line)


def file_citation(file_hash: str) -> Citation:
    return Citation(kind="file", file_hash=file_hash)


def doc_citation(file_hash: str, paragraph: int) -> Citation:
    return Citation(kind="doc", file_hash=file_hash, paragraph=paragraph)


def resolve(citation: Citation, graph: EvidenceGraph) -> bool:
    return citation.resolves_against(graph)


def gate_finding(finding: Finding, graph: EvidenceGraph) -> tuple[bool, list[str]]:
    """The mechanical citation gate: every claim must carry >=1 resolving citation."""
    problems: list[str] = []
    if not finding.citations:
        problems.append(f"{finding.check_id}: finding carries no citations")
    for c in finding.citations:
        if not resolve(c, graph):
            problems.append(f"{finding.check_id}: citation does not resolve: {c.locator_str()}")
    return (not problems), problems
