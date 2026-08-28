"""Design-time output: the versioned, SME-approved Validation Plan.

The plan is compiled once per control, reviewed by an SME, then frozen.
Runtime NEVER decides which checks to run - it executes this artifact.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScopeExclusion(BaseModel):
    id: str
    reason: str  # e.g. "IC elims monitored separately under control 10033"
    match_hints: list[str] = Field(default_factory=list)  # names/labels that identify the excluded item


class ExpectedEvidence(BaseModel):
    id: str
    description: str          # "certified WEBI consolidated TB"
    match_hints: list[str]    # fuzzy names/paths for the matcher
    required: bool = True     # if True and missing -> gap, never pass


class CheckDef(BaseModel):
    id: str
    check_type: Literal["numeric", "vision", "temporal", "signoff"]
    description: str
    inputs: list[str]         # ExpectedEvidence ids this check reads
    params: dict              # tolerances, formulas, cell locators, tz rules
    parallelizable: bool = True


class SignoffRule(BaseModel):
    preparer_role: str
    approver_role: str
    require_distinct: bool = True   # segregation of duties
    require_order: bool = True      # approval must postdate IPE / preparation


class ValidationPlan(BaseModel):
    control_id: str
    version: str                    # semver; frozen once SME-approved
    frequency: Literal["quarterly", "monthly", "annual"]
    description: str = ""
    expected_evidence: list[ExpectedEvidence]
    checks: list[CheckDef]
    scope_exclusions: list[ScopeExclusion] = Field(default_factory=list)
    signoff: SignoffRule | None = None
    approved_by: str | None = None  # SME; None until approved
    approved_at: datetime | None = None

    @property
    def is_approved(self) -> bool:
        return self.approved_by is not None

    def check_by_id(self, check_id: str) -> CheckDef:
        for c in self.checks:
            if c.id == check_id:
                return c
        raise KeyError(check_id)
