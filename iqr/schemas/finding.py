"""Runtime outputs: Citation, Finding, Verdict, and the audit-pack manifest.

The citation gate depends on Citation.resolves_against(graph): any claim whose
locator does not resolve is mechanically rejected before it can enter a
Verdict or an audit pack.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    kind: Literal["cell", "image", "email", "file", "doc"]
    file_hash: str
    # exactly one locator set is populated per kind:
    sheet: str | None = None
    cell: str | None = None                              # kind == "cell"
    image_hash: str | None = None                        # kind == "image"
    ocr_region: tuple[int, int, int, int] | None = None  # left, top, right, bottom
    email_message_id: str | None = None                  # kind == "email"
    line: int | None = None                              # 1-indexed body line
    paragraph: int | None = None                         # kind == "doc"

    def locator_str(self) -> str:
        if self.kind == "cell":
            return f"cell:{self.file_hash[:12]}:{self.sheet}!{self.cell}"
        if self.kind == "image":
            region = f":{self.ocr_region}" if self.ocr_region else ""
            return f"image:{(self.image_hash or self.file_hash)[:12]}{region}"
        if self.kind == "email":
            line = f":line{self.line}" if self.line else ""
            return f"email:{self.email_message_id}{line}"
        if self.kind == "doc":
            return f"doc:{self.file_hash[:12]}:para{self.paragraph}"
        return f"file:{self.file_hash[:12]}"

    def resolves_against(self, graph) -> bool:
        """MUST return True or the claim is rejected by the citation gate."""
        if self.kind == "cell":
            return graph.get_cell(self.file_hash, self.sheet or "", self.cell or "") is not None
        if self.kind == "image":
            img = graph.images.get(self.image_hash or self.file_hash)
            if img is None:
                return False
            if self.ocr_region is not None:
                left, top, right, bottom = self.ocr_region
                return 0 <= left < right <= img.width and 0 <= top < bottom <= img.height
            return True
        if self.kind == "email":
            em = graph.emails.get(self.email_message_id or "")
            if em is None or em.file_hash != self.file_hash:
                return False
            if self.line is not None:
                return 1 <= self.line <= max(len(em.lines), 1)
            return True
        if self.kind == "doc":
            doc = graph.docs.get(self.file_hash)
            if doc is None:
                return False
            if self.paragraph is not None:
                return 1 <= self.paragraph <= len(doc.paragraphs)
            return True
        return self.file_hash in graph.leaves


class Finding(BaseModel):
    check_id: str
    verdict: Literal["pass", "gap", "fail"]
    detail: str
    citations: list[Citation]        # >= 1; ALL must resolve
    computed_values: dict = Field(default_factory=dict)  # numbers came from tools; echoed for audit
    verified: bool = False           # set by the blinded verifier
    verifier_note: str = ""


class Verdict(BaseModel):
    control_id: str
    plan_version: str
    result: Literal["pass", "pass_with_gaps", "fail"]
    findings: list[Finding]
    gaps: list[str]
    exceptions: list[str] = Field(default_factory=list)  # routed to human queue
    run_id: str


class ChecklistItem(BaseModel):
    check_id: str
    description: str
    result: str
    evidence_refs: list[str]


class AuditPack(BaseModel):
    verdict: Verdict
    checklist: list[ChecklistItem]
    artifact_manifest: list[dict]    # every leaf: logical_path, hash, kind
    gaps_register: list[str]
    pack_path: str
