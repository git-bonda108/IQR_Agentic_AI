"""The Evidence Graph: every fact in the GRC package, hashed and addressable.

Built once per run by deterministic Python (no model). Every leaf carries a
SHA-256 hash (chain of custody); every extractable fact has a locator that a
Citation can resolve against.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LeafKind = Literal["docx", "xlsx", "xlsb", "image", "email", "zip", "pdf", "link", "other"]


class EvidenceLeaf(BaseModel):
    file_hash: str            # SHA-256 of the leaf bytes
    logical_path: str         # e.g. "approval.eml!recon.zip!recon_checklist.docx"
    kind: LeafKind
    size: int
    parent_hash: str | None = None   # containment: zip/email that held this leaf
    stored_path: str | None = None   # path in the immutable evidence store


class CellFact(BaseModel):
    file_hash: str
    sheet: str
    cell: str                 # "B7"
    value: str | float | int | None
    is_formula: bool = False
    formula: str | None = None


class EmailFact(BaseModel):
    file_hash: str
    message_id: str
    sender: str
    to: list[str]
    date_raw: str             # raw Date header (tz preserved for temporal checks)
    subject: str
    lines: list[str]          # body lines, 1-indexed via position+1
    attachment_hashes: list[str] = Field(default_factory=list)


class ImageFact(BaseModel):
    file_hash: str            # hash of the image bytes = image_hash in citations
    logical_path: str
    width: int
    height: int
    stored_path: str


class DocFact(BaseModel):
    file_hash: str
    paragraphs: list[str]


class EvidenceGraph(BaseModel):
    """Serializable, addressable evidence structure. This IS the typed state
    the LangGraph nodes read - never a re-dumped blob of raw text."""
    package_id: str
    leaves: dict[str, EvidenceLeaf] = Field(default_factory=dict)          # by file_hash
    cells: dict[str, CellFact] = Field(default_factory=dict)               # key: f"{hash}|{sheet}|{cell}"
    emails: dict[str, EmailFact] = Field(default_factory=dict)             # by message_id
    images: dict[str, ImageFact] = Field(default_factory=dict)             # by image hash
    docs: dict[str, DocFact] = Field(default_factory=dict)                 # by file_hash
    errors: list[str] = Field(default_factory=list)   # unreadable/corrupt artifacts (surfaced as gaps, never hidden)

    # ---- addressing helpers (used by tools and the citation gate) ----
    @staticmethod
    def cell_key(file_hash: str, sheet: str, cell: str) -> str:
        return f"{file_hash}|{sheet}|{cell}"

    def get_cell(self, file_hash: str, sheet: str, cell: str) -> CellFact | None:
        return self.cells.get(self.cell_key(file_hash, sheet, cell))

    def leaf_by_name(self, name_fragment: str) -> list[EvidenceLeaf]:
        frag = name_fragment.lower()
        return [l for l in self.leaves.values() if frag in l.logical_path.lower()]
