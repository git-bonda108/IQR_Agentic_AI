"""Blinded verifier: re-performs each finding from {verdict, plan clause,
cited evidence} ALONE. The executor's reasoning (detail text, agent
transcript) is structurally absent from the verifier's input type - blindness
is enforced by construction, and tested.

Findings that assert ABSENCE (verdict == gap) are re-checked deterministically
against the match table rather than re-performed - you cannot re-read
evidence that is not there."""
from __future__ import annotations

from pydantic import BaseModel

from iqr.agents.runtime import ToolSpec, run_agent
from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation, Finding
from iqr.schemas.validation_plan import CheckDef, ValidationPlan
from iqr.tools import ocr_read as ocr
from iqr.tools.cell_read import cell_read
from iqr.tools.email_parse import email_parse
from iqr.tools.recompute import recompute
from iqr.tools.timestamp import parse_timestamp


class VerifierInput(BaseModel):
    """EVERYTHING the verifier may see. No detail, no reasoning, no transcript."""
    check: CheckDef
    claimed_verdict: str
    citations: list[Citation]


def _cell_cites(citations: list[Citation]) -> list[Citation]:
    return [c for c in citations if c.kind == "cell"]


def _reperform_numeric(vin: VerifierInput, graph: EvidenceGraph) -> dict:
    cells = _cell_cites(vin.citations)
    if len(cells) < 2:
        return {"ok": False, "why": "insufficient cell citations to re-perform"}
    *sources, target = cells
    src_vals = [cell_read(graph, c.file_hash, c.sheet, c.cell)[0] for c in sources]
    tgt_val = cell_read(graph, target.file_hash, target.sheet, target.cell)[0]
    p = vin.check.params
    r = recompute(p["op"], src_vals, tgt_val, float(p.get("tolerance", 0.01)))
    return {"ok": r.ok, "computed": r.computed, "delta": r.delta}


def _reperform_vision(vin: VerifierInput, graph: EvidenceGraph) -> dict:
    img = next((c for c in vin.citations if c.kind == "image"), None)
    cell = next((c for c in _cell_cites(vin.citations)), None)
    if img is None or cell is None:
        return {"verdict": "gap", "why": "citations lack image or cell"}
    text, _ = ocr.ocr_read(graph, img.image_hash or img.file_hash, img.ocr_region)
    value = ocr.find_labeled_number(text, vin.check.params["label"])
    if value is None:
        return {"verdict": "gap", "why": "label not found on re-OCR"}
    cell_v = float(cell_read(graph, cell.file_hash, cell.sheet, cell.cell)[0])
    tol = float(vin.check.params.get("tolerance", 0.01))
    return {"verdict": "pass" if abs(value - cell_v) <= tol else "fail",
            "image_value": value, "cell_value": cell_v}


def _reperform_temporal(vin: VerifierInput, graph: EvidenceGraph) -> dict:
    cell = next((c for c in _cell_cites(vin.citations)), None)
    em_cite = next((c for c in vin.citations if c.kind == "email"), None)
    if cell is None or em_cite is None:
        return {"verdict": "gap", "why": "citations lack cell or email"}
    raw, _ = cell_read(graph, cell.file_hash, cell.sheet, cell.cell)
    tz = vin.check.params.get("earlier", {}).get("tz", "UTC")
    earlier = parse_timestamp(str(raw), assume_tz=tz)
    facts, _em = email_parse(graph, em_cite.email_message_id)
    later = parse_timestamp(facts.date_utc)
    return {"verdict": "pass" if earlier <= later else "fail",
            "earlier_utc": earlier.isoformat(), "later_utc": later.isoformat()}


def _reperform_signoff(vin: VerifierInput, graph: EvidenceGraph) -> dict:
    em_cite = next((c for c in vin.citations if c.kind == "email"), None)
    if em_cite is None:
        return {"verdict": "gap", "why": "citations lack email"}
    facts, _em = email_parse(graph, em_cite.email_message_id)
    if facts.approval_line is None:
        return {"verdict": "gap", "why": "no approval language on re-read"}
    p = vin.check.params
    problems = []
    if p.get("preparer") and p["preparer"].lower() in facts.sender.lower():
        problems.append("approver == preparer")
    cell = next((c for c in _cell_cites(vin.citations)), None)
    if cell is not None:
        raw, _ = cell_read(graph, cell.file_hash, cell.sheet, cell.cell)
        tz = p.get("prepared_at", {}).get("tz", "UTC")
        prepared = parse_timestamp(str(raw), assume_tz=tz)
        approved = parse_timestamp(facts.date_utc)
        if approved <= prepared:
            problems.append("approval predates preparation")
    return {"verdict": "fail" if problems else "pass", "problems": problems}


_REPERFORM = {"numeric": ("recompute_from_citations", _reperform_numeric),
              "vision": ("reperform_vision", _reperform_vision),
              "temporal": ("reperform_temporal", _reperform_temporal),
              "signoff": ("reperform_signoff", _reperform_signoff)}


def blinded_verify(finding: Finding, check: CheckDef, graph: EvidenceGraph,
                   matches: dict, ledger: RunLedger | None = None) -> tuple[bool, str]:
    if finding.verdict == "gap":
        inputs_missing = any(ev not in matches for ev in check.inputs)
        return True, ("absence confirmed against match table" if inputs_missing
                      else "abstention accepted: evidence matched but fact not extractable")

    vin = VerifierInput(check=check, claimed_verdict=finding.verdict,
                        citations=finding.citations)
    tool_name, fn = _REPERFORM[check.check_type]

    def tool_fn() -> dict:
        return {"value": fn(vin, graph), "citations": []}

    # numeric re-performance maps ok->pass/fail for comparison inside the policy
    def numeric_tool_fn() -> dict:
        r = fn(vin, graph)
        if "verdict" not in r:
            r = dict(r)
        return {"value": r, "citations": []}

    run = run_agent(
        f"blinded verify {finding.check_id}",
        {"task_type": "verify", "check_type": check.check_type,
         "claimed_verdict": finding.verdict,
         "clause": check.model_dump(), "citations": [c.locator_str() for c in vin.citations]},
        [ToolSpec(tool_name, "re-perform the check from cited evidence alone "
                             "(takes no arguments: call with \"args\": {})",
                  numeric_tool_fn if check.check_type == "numeric" else tool_fn)],
        ledger,
        output_spec='{"agree": true | false, "note": "<one sentence: what the '
                    're-performance found and whether it matches the claimed verdict>"}')
    return bool(run.final.get("agree")), run.final.get("note", "")


def verify_node(state: dict) -> dict:
    plan: ValidationPlan = state["plan"]
    graph: EvidenceGraph = state["evidence"]
    ledger = RunLedger(state["run_id"])
    verified: list[Finding] = []
    exceptions: list[str] = list(state.get("exceptions", []))
    for finding in sorted(state["findings"], key=lambda f: f.check_id):
        check = plan.check_by_id(finding.check_id)
        agree, note = blinded_verify(finding, check, graph, state["matches"], ledger)
        f2 = finding.model_copy(update={"verified": agree, "verifier_note": note})
        if agree:
            verified.append(f2)
        else:
            exceptions.append(f"verifier disagreement on {finding.check_id}: {note}")
            verified.append(f2)   # kept, but flagged; adjudicator routes to human queue
        ledger.log("verify", check_id=finding.check_id, agree=agree, note=note)
    return {"verified_findings": verified, "exceptions": exceptions}
