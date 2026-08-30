"""IQR as an MCP server: the platform's operations exposed as typed tools and
resources so any MCP client - an Azure AI Foundry agent, Claude, an IDE - can
drive validation runs without touching the machinery.

The three laws still hold on this surface: tools execute the same frozen
plans through the same graph, every verdict carries the same citations, and
nothing here bypasses the SME approval gate.

Run it:
  .venv/bin/python -m iqr.mcp_server                 # stdio (default)
  IQR_MCP_TRANSPORT=streamable-http \
      .venv/bin/python -m iqr.mcp_server             # HTTP for remote agents

Wire it into Azure AI Foundry: add an MCP tool to your Foundry agent pointing
at the streamable-http endpoint (see docs/AZURE_FOUNDRY.md).
"""
from __future__ import annotations

import json
import os

from mcp.server.mcpserver import MCPServer

from iqr import config

mcp = MCPServer(
    "iqr",
    instructions=(
        "IQR validates SOX 404 control evidence packages against frozen, "
        "SME-approved validation plans. Every claim carries a resolvable "
        "citation; numbers come from deterministic Python, never a model. "
        "Start with list_controls, then run_control on an evidence folder."))


# ------------------------------------------------------------------- tools

@mcp.tool()
def list_controls() -> list[dict]:
    """List every control with an approved (frozen) validation plan, with its
    available plan versions and check roster."""
    out = []
    for d in sorted(config.PLAN_STORE_DIR.glob("*/")):
        versions = sorted(p.stem for p in d.glob("*.json"))
        if not versions:
            continue
        plan = json.loads((d / f"{versions[-1]}.json").read_text())
        out.append({"control_id": d.name, "versions": versions,
                    "latest": versions[-1],
                    "description": plan.get("description", ""),
                    "frequency": plan.get("frequency", ""),
                    "checks": [{"check_id": c["id"], "type": c["check_type"]}
                               for c in plan.get("checks", [])]})
    return out


@mcp.tool()
def get_plan(control_id: str, version: str | None = None) -> dict:
    """Fetch a frozen validation plan (latest version unless one is given).
    The plan states exactly what evidence is expected and what is checked."""
    from iqr.plan.review import latest_version, load_plan
    v = version or latest_version(control_id)
    if v is None:
        raise ValueError(f"no approved plan for {control_id}")
    return load_plan(control_id, v).model_dump(mode="json")


@mcp.tool()
def run_control(control_id: str, package_dir: str,
                plan_version: str | None = None) -> dict:
    """Validate an evidence package folder against a control's frozen plan.
    Returns the verdict with findings, gaps, exceptions, run_id, and the
    audit-pack path. Every finding cites the exact cell/email line/image."""
    from iqr.graph.build_graph import run_control_full
    from iqr.pack.assemble import assemble_pack
    from iqr.plan.review import latest_version, load_plan
    v = plan_version or latest_version(control_id)
    if v is None:
        raise ValueError(f"no approved plan for {control_id}")
    plan = load_plan(control_id, v)
    verdict, graph = run_control_full(plan, package_dir)
    pack = assemble_pack(verdict, plan, graph)
    out = verdict.model_dump(mode="json")
    out["pack_path"] = str(pack.pack_path)
    return out


@mcp.tool()
def get_run_ledger(run_id: str, tail: int | None = None) -> list[dict]:
    """Replay a run's append-only ledger (the explainability trail): every
    node event, tool call with args and results, agent conclusion with the
    backend that produced it, verification, and adjudication."""
    from iqr.ledger import RunLedger
    events = RunLedger(run_id).read()
    if not events:
        raise ValueError(f"no ledger for {run_id}")
    return events[-tail:] if tail else events


@mcp.tool()
def run_eval() -> dict:
    """Run the five-gate evaluation harness (defect recall, false-exception
    rate, citation validity, abstention correctness, reproducibility) against
    the golden fixture controls. Returns per-gate metrics and pass/fail."""
    from tests.fixtures.build_fixtures import FIXTURES, build_all
    from iqr.eval.harness import run_eval as _run_eval
    from iqr.plan.review import load_plan
    build_all()
    plans = {cid: load_plan(cid, "1.0.0")
             for cid in ("C23024", "C10032", "C10075")}
    report = _run_eval(plans, FIXTURES)
    return {"gates_passed": report.gates_passed, "summary": report.summary()}


@mcp.tool()
def compile_plan(doc_path: str, control_id: str, frequency: str) -> dict:
    """Draft a validation plan from a SOX 404 document (design-time step).
    The draft is NOT runnable until an SME approves and freezes it - the
    runtime refuses unapproved plans."""
    from iqr.plan.compiler import compile_plan as _compile
    plan = _compile(doc_path, control_id, frequency)
    return {"draft": plan.model_dump(mode="json"),
            "note": "review, then approve via the console or "
                    f"`python -m iqr.cli approve {control_id} <sme>`"}


@mcp.tool()
def similar_adjudications(pattern: str, k: int = 3) -> list[dict]:
    """Search the Golden Library (released, SME-signed adjudication exemplars)
    for how a pattern was judged before. Uses Foundry IQ retrieval when
    configured, the local index otherwise."""
    from iqr.knowledge.golden_library import GoldenLibrary
    return GoldenLibrary().similar_adjudications(pattern, k)


@mcp.tool()
def pending_exceptions() -> list[dict]:
    """List adjudications waiting in the governed-learning intake - human
    overrides that have not yet passed the eval gate + SME sign-off."""
    from iqr.knowledge.golden_library import GoldenLibrary
    return GoldenLibrary().pending_overrides()


# ---------------------------------------------------------------- resources

@mcp.resource("iqr://plans/{control_id}/{version}",
              description="A frozen validation plan as JSON")
def plan_resource(control_id: str, version: str) -> str:
    from iqr.plan.review import load_plan
    return load_plan(control_id, version).model_dump_json(indent=2)


@mcp.resource("iqr://runs/{run_id}/ledger",
              description="A run's replayable JSONL ledger")
def ledger_resource(run_id: str) -> str:
    from iqr.ledger import RunLedger
    return json.dumps(RunLedger(run_id).read(), indent=2)


@mcp.resource("iqr://topology",
              description="The versioned LangGraph topology signature")
def topology_resource() -> str:
    from iqr.graph.build_graph import topology_signature
    return json.dumps(topology_signature())


def main() -> None:
    transport = os.environ.get("IQR_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
