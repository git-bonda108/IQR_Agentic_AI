"""Vision, temporal, and sign-off checks: tool-using agents.

The agent reasons about where the answer is and what it means; deterministic
tools do ALL extraction and computation. The runtime accumulates the tool
citations, so the Finding cites exactly what was read.
"""
from __future__ import annotations

from iqr.ledger import RunLedger
from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Finding
from iqr.schemas.validation_plan import CheckDef, SignoffRule
from iqr.agents.runtime import ToolSpec, run_agent
from iqr.checks.base import gap_finding, missing_inputs, requirement_citation
from iqr.tools import email_parse as ep
from iqr.tools import ocr_read as ocr
from iqr.tools.cell_read import CellNotFound, cell_read
from iqr.tools.timestamp import parse_timestamp

# Real models need the output contract stated; the stub encodes it implicitly.
CHECK_OUTPUT_SPEC = ('{"verdict": "pass" | "fail" | "gap", "detail": "<one factual '
                     'sentence stating the tool-obtained values behind the verdict>"}'
                     ' - use "gap" when required evidence is missing or unreadable, '
                     'never invent a value')


def _tool_cell_read(graph):
    def fn(file_hash: str, sheet: str, cell: str) -> dict:
        value, cite = cell_read(graph, file_hash, sheet, cell)
        return {"value": value, "citations": [cite]}
    return ToolSpec("cell_read", "Read one workbook cell -> value + citation", fn)


def _tool_ocr_labeled_number(graph):
    def fn(image_hash: str, label: str) -> dict:
        text, cite = ocr.ocr_read(graph, image_hash)
        value = ocr.find_labeled_number(text, label)
        return {"value": value, "ocr_text": text[:400], "citations": [cite] if value is not None else []}
    return ToolSpec("ocr_labeled_number",
                    "OCR a screenshot and extract the number following a label", fn)


def _tool_email_signoff_facts(graph):
    def fn(message_id: str) -> dict:
        facts, _em = ep.email_parse(graph, message_id)
        return {"value": {"sender": facts.sender, "date_utc": facts.date_utc,
                          "subject": facts.subject, "approval_line": facts.approval_line,
                          "approval_text": facts.approval_text},
                "citations": facts.citations}
    return ToolSpec("email_signoff_facts",
                    "Parse an approval email -> sender, UTC date, approval line + citation", fn)


def _tool_timestamp_order():
    def fn(earlier_raw: str, earlier_tz: str, later_raw: str, later_tz: str) -> dict:
        earlier = parse_timestamp(earlier_raw, assume_tz=earlier_tz)
        later = parse_timestamp(later_raw, assume_tz=later_tz)
        return {"value": {"in_order": earlier <= later,
                          "earlier_utc": earlier.isoformat(),
                          "later_utc": later.isoformat()},
                "citations": []}
    return ToolSpec("timestamp_order",
                    "Normalize two timestamps to UTC and report their ordering", fn)


def run_vision_check(check: CheckDef, graph: EvidenceGraph, matches: dict,
                     ledger: RunLedger | None = None) -> Finding:
    missing = missing_inputs(check, matches)
    if missing:
        return gap_finding(check, graph,
                           f"required evidence missing for {check.id}: {', '.join(missing)}")
    p = check.params
    image_hashes = matches[p["image_evidence"]].get("image_hashes", [])
    if not image_hashes:
        return gap_finding(check, graph, f"{check.id}: no screenshot images resolved")
    tgt = p["target"]
    context = {"task_type": "vision", "label": p["label"], "images": image_hashes,
               "target": {"file_hash": matches[tgt["evidence"]]["file_hash"],
                          "sheet": tgt["sheet"], "cell": tgt["cell"]},
               "tolerance": p.get("tolerance", 0.01)}
    run = run_agent(f"vision tie-out {check.id}", context,
                    [_tool_ocr_labeled_number(graph), _tool_cell_read(graph)], ledger,
                    output_spec=CHECK_OUTPUT_SPEC)
    return _finding_from_agent(check, run, graph)


def run_temporal_check(check: CheckDef, graph: EvidenceGraph, matches: dict,
                       ledger: RunLedger | None = None) -> Finding:
    missing = missing_inputs(check, matches)
    if missing:
        return gap_finding(check, graph,
                           f"required evidence missing for {check.id}: {', '.join(missing)}")
    p = check.params
    e = p["earlier"]
    later_match = matches[p["later_email_evidence"]]
    if "message_id" not in later_match:
        return gap_finding(check, graph, f"{check.id}: approval email not resolved")
    context = {"task_type": "temporal",
               "earlier_cell": {"file_hash": matches[e["evidence"]]["file_hash"],
                                "sheet": e["sheet"], "cell": e["cell"]},
               "earlier_tz": e.get("tz", "UTC"),
               "later_email_message_id": later_match["message_id"]}
    # The earlier stamp's locator is plan-pinned - nothing for the agent to
    # decide. Prefetch it deterministically and seed the observation, so the
    # agent's chain is email facts -> ordering only.
    try:
        value, cite = cell_read(graph, context["earlier_cell"]["file_hash"],
                                e["sheet"], e["cell"])
    except CellNotFound as err:
        return gap_finding(check, graph,
                           f"{check.id}: IPE timestamp cell unreadable - {err}")
    seed = [{"tool": "cell_read",
             "args": {"file_hash": context["earlier_cell"]["file_hash"],
                      "sheet": e["sheet"], "cell": e["cell"]},
             "result": {"value": value}}]
    run = run_agent(f"temporal ordering {check.id}", context,
                    [_tool_cell_read(graph), _tool_email_signoff_facts(graph),
                     _tool_timestamp_order()], ledger, output_spec=CHECK_OUTPUT_SPEC,
                    seed_observations=seed, seed_citations=[cite])
    return _finding_from_agent(check, run, graph)


def run_signoff_check(check: CheckDef, graph: EvidenceGraph, matches: dict,
                      signoff_rule: SignoffRule | None,
                      ledger: RunLedger | None = None) -> Finding:
    missing = missing_inputs(check, matches)
    if missing:
        return gap_finding(check, graph,
                           f"required evidence missing for {check.id}: {', '.join(missing)}")
    p = check.params
    em_match = matches[p["approval_email_evidence"]]
    if "message_id" not in em_match:
        return gap_finding(check, graph, f"{check.id}: approval email not resolved")

    context = {"task_type": "signoff",
               "approval_email_message_id": em_match["message_id"],
               "preparer": p["preparer"],
               "require_distinct": signoff_rule.require_distinct if signoff_rule else True,
               "require_order": signoff_rule.require_order if signoff_rule else True}
    pre_cites = []
    if "prepared_at" in p:
        pa = p["prepared_at"]
        try:
            value, cite = cell_read(graph, matches[pa["evidence"]]["file_hash"],
                                    pa["sheet"], pa["cell"])
        except CellNotFound as e:
            return gap_finding(check, graph,
                               f"{check.id}: preparation timestamp unreadable - {e}")
        context["prepared_at_utc"] = parse_timestamp(str(value), assume_tz=pa.get("tz", "UTC")).isoformat()
        pre_cites.append(cite)
    run = run_agent(f"sign-off / SoD {check.id}", context,
                    [_tool_email_signoff_facts(graph)], ledger,
                    output_spec=CHECK_OUTPUT_SPEC)
    finding = _finding_from_agent(check, run, graph)
    finding.citations.extend(pre_cites)
    return finding


def _finding_from_agent(check: CheckDef, run, graph: EvidenceGraph) -> Finding:
    out = run.final
    computed = {}
    for o in run.observations:
        if "error" not in o["result"] and o["result"].get("value") is not None:
            computed[f"{o['tool']}#{len(computed)}"] = o["result"]["value"]
    citations = list(run.citations)
    if not citations:
        # an abstention still needs grounding: cite the 404 requirement it
        # abstained against
        citations = [requirement_citation(graph)]
    return Finding(check_id=check.id,
                   verdict=out.get("verdict", "gap"),
                   detail=out.get("detail", ""),
                   citations=citations,
                   computed_values=computed)
