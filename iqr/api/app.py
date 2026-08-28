"""Thin API over the platform: control roster, package upload, async runs with
live ledger streaming, eval harness, plan approval, exception adjudication,
audit-pack download. The web console is a static client over these endpoints -
all logic stays in the engine, and the server binds 127.0.0.1 only."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from iqr import config
from iqr.graph.build_graph import run_control_full, topology_signature
from iqr.knowledge.golden_library import GoldenLibrary
from iqr.ledger import RunLedger
from iqr.pack.assemble import assemble_pack
from iqr.plan.compiler import compile_plan
from iqr.plan.review import approve_and_freeze, latest_version, load_plan
from iqr.schemas.validation_plan import ValidationPlan

app = FastAPI(title="IQR - SOX 404 validation platform", version="0.2.0")


class CompileRequest(BaseModel):
    doc_path: str
    control_id: str
    frequency: str


class ApproveRequest(BaseModel):
    sme: str


class RunRequest(BaseModel):
    control_id: str
    package_ref: str
    plan_version: str | None = None


class AdjudicationRequest(BaseModel):
    control_id: str
    check_id: str
    pattern: str
    human_verdict: str
    rationale: str
    run_id: str


_drafts: dict[str, ValidationPlan] = {}
_runs: dict[str, dict] = {}       # run_id -> {status, control_id, verdict?, pack?, error?}
_eval_state: dict = {"status": "idle"}


# ---------------------------------------------------------------- controls

@app.get("/api/controls")
def api_controls():
    """The roster the console's home screen is built from: every approved
    control, its latest plan, and - crucially for users - exactly what
    evidence the plan expects them to provide."""
    out = []
    plans_dir = config.PLAN_STORE_DIR
    if plans_dir.is_dir():
        for d in sorted(plans_dir.iterdir()):
            if not d.is_dir():
                continue
            version = latest_version(d.name)
            if version is None:
                continue
            plan = load_plan(d.name, version)
            out.append({
                "control_id": plan.control_id,
                "version": plan.version,
                "frequency": plan.frequency,
                "description": plan.description,
                "approved_by": plan.approved_by,
                "expected_evidence": [
                    {"id": e.id, "description": e.description,
                     "match_hints": e.match_hints, "required": e.required}
                    for e in plan.expected_evidence],
                "checks": [{"id": c.id, "type": c.check_type,
                            "description": c.description} for c in plan.checks],
                "scope_exclusions": [{"id": x.id, "reason": x.reason}
                                     for x in plan.scope_exclusions],
            })
    return out


@app.get("/api/topology")
def get_topology():
    return topology_signature()


# ---------------------------------------------------------------- upload

@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    """Receive a GRC package as individual files (or one .zip); store under
    data/input/uploads/<id>/ and return the package_ref to run against."""
    pkg_id = f"pkg-{uuid.uuid4().hex[:8]}"
    dest = config.DATA_DIR / "input" / "uploads" / pkg_id
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        name = Path(f.filename or "artifact.bin").name  # strip any path tricks
        target = dest / name
        with open(target, "wb") as out:
            while chunk := await f.read(4 * 1024 * 1024):
                out.write(chunk)
        saved.append(name)
    return {"package_ref": str(dest), "files": saved}


# ---------------------------------------------------------------- plans

@app.post("/api/plans/compile")
def api_compile(req: CompileRequest):
    plan = compile_plan(req.doc_path, req.control_id, req.frequency)
    _drafts[req.control_id] = plan
    return plan.model_dump()


@app.post("/api/plans/{control_id}/approve")
def api_approve(control_id: str, req: ApproveRequest):
    draft = _drafts.get(control_id)
    if draft is None:
        raise HTTPException(404, f"no draft plan for {control_id}; compile first")
    approved = approve_and_freeze(draft, sme=req.sme)
    del _drafts[control_id]
    return approved.model_dump()


@app.get("/api/plans/{control_id}")
def api_get_plan(control_id: str):
    version = latest_version(control_id)
    if version is None:
        raise HTTPException(404, f"no approved plan for {control_id}")
    return load_plan(control_id, version).model_dump()


# ---------------------------------------------------------------- runs (async)

def _run_worker(run_id: str, plan: ValidationPlan, package_ref: str) -> None:
    try:
        verdict, graph = run_control_full(plan, package_ref, run_id=run_id)
        pack = assemble_pack(verdict, plan, graph)
        _runs[run_id].update(status="done", verdict=verdict.model_dump(),
                             pack_path=pack.pack_path)
    except Exception as e:  # surface, never swallow
        _runs[run_id].update(status="error", error=f"{type(e).__name__}: {e}")


@app.post("/api/runs")
def api_run(req: RunRequest):
    version = req.plan_version or latest_version(req.control_id)
    if version is None:
        raise HTTPException(404, f"no approved plan for {req.control_id}")
    if not Path(req.package_ref).is_dir():
        raise HTTPException(400, f"package_ref is not a directory: {req.package_ref}")
    plan = load_plan(req.control_id, version)
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    _runs[run_id] = {"status": "running", "control_id": req.control_id,
                     "plan_version": version, "package_ref": req.package_ref}
    threading.Thread(target=_run_worker, args=(run_id, plan, req.package_ref),
                     daemon=True).start()
    return {"run_id": run_id, "status": "running"}


@app.get("/api/runs/{run_id}")
def api_run_status(run_id: str):
    st = _runs.get(run_id)
    if st is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return st


@app.get("/api/runs/{run_id}/ledger")
def api_ledger(run_id: str, after: int = 0):
    """Live progress: the console polls with ?after=<n> and renders new events."""
    events = RunLedger(run_id).read()
    return events[after:]


@app.get("/api/runs/{run_id}/pack")
def api_pack(run_id: str):
    path = config.PACK_DIR / f"{run_id}.zip"
    if not path.exists():
        raise HTTPException(404, f"no pack for {run_id}")
    return FileResponse(path, filename=f"audit_pack_{run_id}.zip")


# ---------------------------------------------------------------- eval

def _eval_worker() -> None:
    try:
        from tests.fixtures.build_fixtures import FIXTURES, build_all
        from iqr.eval.harness import run_eval
        build_all()
        plans = {}
        for cid in ("C23024", "C10032", "C10075"):
            v = latest_version(cid)
            if v is None:
                _eval_state.update(status="error",
                                   error=f"no approved plan for {cid}")
                return
            plans[cid] = load_plan(cid, v)
        report = run_eval(plans, FIXTURES)
        _eval_state.update(status="done", gates_passed=report.gates_passed,
                           summary=report.summary(),
                           metrics=getattr(report, "model_dump", lambda: vars(report))())
    except Exception as e:
        _eval_state.update(status="error", error=f"{type(e).__name__}: {e}")


@app.post("/api/eval")
def api_eval_start():
    if _eval_state.get("status") == "running":
        return _eval_state
    _eval_state.clear()
    _eval_state.update(status="running")
    threading.Thread(target=_eval_worker, daemon=True).start()
    return _eval_state


@app.get("/api/eval")
def api_eval_status():
    return _eval_state


# ---------------------------------------------------------------- governance

@app.get("/api/exceptions")
def api_exceptions():
    return GoldenLibrary().pending_overrides()


@app.post("/api/exceptions/adjudicate")
def api_adjudicate(req: AdjudicationRequest):
    return GoldenLibrary().record_adjudication(
        req.control_id, req.check_id, req.pattern,
        req.human_verdict, req.rationale, req.run_id)


@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).resolve().parent.parent.parent / "webapp" / "index.html"
    return html.read_text() if html.exists() else "<h1>IQR</h1>"
