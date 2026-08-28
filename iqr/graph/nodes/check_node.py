"""Check fan-out: one branch per check in the frozen plan, dispatched by
check_type. The plan chose the checks at design time; runtime only executes."""
from __future__ import annotations

from langgraph.types import Send

from iqr.checks.base import gap_finding
from iqr.checks.dispatch import run_check
from iqr.ledger import RunLedger
from iqr.graph.state import CheckTask


def fan_out_checks(state: dict) -> list[Send]:
    plan = state["plan"]
    return [Send("check", CheckTask(check_id=c.id, plan=plan,
                                    evidence=state["evidence"],
                                    matches=state["matches"],
                                    run_id=state["run_id"]))
            for c in plan.checks]


def check_node(task: CheckTask) -> dict:
    plan = task["plan"]
    check = plan.check_by_id(task["check_id"])
    ledger = RunLedger(task["run_id"])
    ledger.log("check_start", check_id=check.id, check_type=check.check_type)
    try:
        finding = run_check(check, plan, task["evidence"], task["matches"], ledger)
    except Exception as e:
        # a crashed check must abstain loudly, not sink the whole run or be
        # mistaken for a pass; it surfaces as a gap + goes to the human queue
        finding = gap_finding(check, task["evidence"],
                              f"{check.id}: check execution error - "
                              f"{type(e).__name__}: {e}")
        ledger.log("check_error", check_id=check.id, error=str(e))
    ledger.log("check_done", check_id=check.id, verdict=finding.verdict)
    return {"findings": [finding]}
