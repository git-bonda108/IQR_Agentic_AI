"""Parse an email chain from the Evidence Graph -> participants, order, sign-off facts."""
from __future__ import annotations

from dataclasses import dataclass, field

from iqr.schemas.evidence_graph import EmailFact, EvidenceGraph
from iqr.schemas.finding import Citation
from iqr.tools.citation import email_citation
from iqr.tools.timestamp import parse_timestamp


class EmailNotFound(Exception):
    pass


@dataclass
class SignoffFacts:
    message_id: str
    sender: str
    date_utc: str
    subject: str
    approval_line: int | None      # 1-indexed body line containing the approval language
    approval_text: str | None
    citations: list[Citation] = field(default_factory=list)


_APPROVAL_MARKERS = ("approved", "approve", "sign-off", "signed off", "reviewed and approved")


def email_parse(graph: EvidenceGraph, message_id: str) -> tuple[SignoffFacts, EmailFact]:
    em = graph.emails.get(message_id)
    if em is None:
        raise EmailNotFound(f"email {message_id} not in evidence graph")
    approval_line, approval_text = None, None
    for i, line in enumerate(em.lines, start=1):
        if any(m in line.lower() for m in _APPROVAL_MARKERS):
            approval_line, approval_text = i, line.strip()
            break
    cites = [email_citation(em.file_hash, em.message_id, approval_line)]
    date_utc = parse_timestamp(em.date_raw).isoformat() if em.date_raw else ""
    return SignoffFacts(message_id=em.message_id, sender=em.sender, date_utc=date_utc,
                        subject=em.subject, approval_line=approval_line,
                        approval_text=approval_text, citations=cites), em


def find_email_by_subject(graph: EvidenceGraph, subject_fragment: str) -> str | None:
    frag = subject_fragment.lower()
    for mid, em in sorted(graph.emails.items()):
        if frag in em.subject.lower():
            return mid
    return None
