"""The fixed, versioned LangGraph topology. Same shape every run:

    ingest -> match -> [check x N in parallel] -> verify -> adjudicate

The topology itself is a versioned audit artifact: topology_signature()
serializes it so a release can pin and diff it.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from langgraph.graph import END, START, StateGraph

from iqr import config
from iqr.graph.nodes.adjudicate_node import adjudicate_node
from iqr.graph.nodes.check_node import check_node, fan_out_checks
from iqr.graph.nodes.ingest_node import ingest_node
from iqr.graph.nodes.match_node import match_node
from iqr.graph.nodes.sentinel_node import sentinel_node
from iqr.graph.nodes.verify_node import verify_node
from iqr.graph.state import IQRState
from iqr.ledger import RunLedger
from iqr.schemas.finding import Verdict
from iqr.schemas.validation_plan import ValidationPlan

TOPOLOGY_VERSION = "1.1.0"


def build_graph():
    g = StateGraph(IQRState)
    g.add_node("ingest", ingest_node)
    g.add_node("match", match_node)
    g.add_node("sentinel", sentinel_node)
    g.add_node("check", check_node)
    g.add_node("verify", verify_node)
    g.add_node("adjudicate", adjudicate_node)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "match")
    g.add_edge("match", "sentinel")
    g.add_conditional_edges("sentinel", fan_out_checks, ["check"])
    g.add_edge("check", "verify")
    g.add_edge("verify", "adjudicate")
    g.add_edge("adjudicate", END)
    return g.compile()


def topology_signature() -> dict:
    edges = [["START", "ingest"], ["ingest", "match"],
             ["match", "sentinel (adversarial pre-screen)"],
             ["sentinel", "check*N (fan-out per plan check)"],
             ["check", "verify"], ["verify", "adjudicate"], ["adjudicate", "END"]]
    payload = json.dumps({"version": TOPOLOGY_VERSION, "edges": edges}, sort_keys=True)
    return {"version": TOPOLOGY_VERSION, "edges": edges,
            "sha256": hashlib.sha256(payload.encode()).hexdigest()}


def run_control(plan: ValidationPlan, package_ref: str,
                run_id: str | None = None, _return_state: bool = False):
    """Execute the frozen plan against a GRC package. Refuses unapproved plans."""
    if not plan.is_approved:
        raise PermissionError(
            f"plan {plan.control_id} v{plan.version} is not SME-approved; runtime "
            "executes approved plans only")
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    ledger = RunLedger(run_id)
    ledger.log("run_start", control_id=plan.control_id, plan_version=plan.version,
               topology=topology_signature(), model=config.MODEL_NAME,
               temperature=config.MODEL_TEMPERATURE)
    app = build_graph()
    out = app.invoke({"run_id": run_id, "package_ref": package_ref,
                      "plan": plan, "findings": [], "exceptions": []})
    verdict: Verdict = out["verdict"]
    ledger.log("run_end", result=verdict.result)
    if _return_state:
        return verdict, out
    return verdict


def run_control_full(plan: ValidationPlan, package_ref: str,
                     run_id: str | None = None):
    """Run and return (verdict, evidence_graph) - lets callers assemble the
    audit pack without ingesting the package a second time."""
    verdict, state = run_control(plan, package_ref, run_id, _return_state=True)
    return verdict, state["evidence"]
