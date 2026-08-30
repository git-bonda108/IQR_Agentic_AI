"""CLI: compile/approve plans, run controls, run the eval harness.

  python -m iqr.cli compile <404.docx> <control_id> <frequency>
  python -m iqr.cli approve <control_id> <sme>
  python -m iqr.cli run <control_id> <package_dir>
  python -m iqr.cli eval
  python -m iqr.cli testmodel     # verify API keys / fallback chain
  python -m iqr.cli explain <run_id>   # replay a run's ledger (XAI trace)
  python -m iqr.cli serve
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd, rest = args[0], args[1:]

    if cmd == "compile":
        from iqr.plan.compiler import compile_plan
        doc, cid, freq = rest
        plan = compile_plan(doc, cid, freq)
        draft = Path(f"{cid}_draft_plan.json")
        draft.write_text(plan.model_dump_json(indent=2))
        print(f"draft written to {draft} - review, then: python -m iqr.cli approve {cid} <sme>")
        return 0
    if cmd == "approve":
        from iqr.plan.review import approve_and_freeze
        from iqr.schemas.validation_plan import ValidationPlan
        cid, sme = rest
        plan = ValidationPlan.model_validate_json(Path(f"{cid}_draft_plan.json").read_text())
        approved = approve_and_freeze(plan, sme=sme)
        print(f"frozen: {approved.control_id} v{approved.version} approved by {sme}")
        return 0
    if cmd == "run":
        from iqr.graph.build_graph import run_control_full
        from iqr.pack.assemble import assemble_pack
        from iqr.plan.review import latest_version, load_plan
        cid, pkg = rest
        plan = load_plan(cid, latest_version(cid))
        verdict, graph = run_control_full(plan, pkg)
        pack = assemble_pack(verdict, plan, graph)
        print(f"{cid}: {verdict.result}  (run {verdict.run_id})")
        for f in verdict.findings:
            print(f"  {f.check_id} [{f.verdict}] {f.detail}")
        for g in verdict.gaps:
            print(f"  GAP: {g}")
        print(f"audit pack: {pack.pack_path}")
        return 0
    if cmd == "eval":
        from tests.fixtures.build_fixtures import FIXTURES, build_all
        from iqr.eval.harness import run_eval
        from iqr.plan.review import load_plan
        build_all()
        plans = {}
        # The harness runs the synthesized golden fixtures, so it must use the
        # fixture-matched 1.0.0 plans - not a later plan frozen for real packages.
        for cid in ("C23024", "C10032", "C10075"):
            try:
                plans[cid] = load_plan(cid, "1.0.0")
            except FileNotFoundError:
                print(f"no approved 1.0.0 plan for {cid}; compile+approve first"); return 1
        if rest[:1] == ["--batch"]:
            from iqr.eval.batch import run_eval_batch
            n = int(rest[1]) if len(rest) > 1 else 3
            report = run_eval_batch(plans, FIXTURES, n=n)
            print(report.summary())
            return 0 if report.batch_gates_passed else 1
        report = run_eval(plans, FIXTURES)
        print(report.summary())
        return 0 if report.gates_passed else 1
    if cmd == "learn":
        from iqr.learn.reinforce import learn_from_adjudications
        result = learn_from_adjudications()
        print(f"applied {result['applied']} new adjudication(s) across {result['arms']} check(s)")
        for r in result["priorities"][:10]:
            print(f"  {r['control_id']}/{r['check_id']}: confidence {r['confidence']:.2f} "
                  f"({r['observations']} obs) - review priority {r['uncertainty']:.4f}")
        return 0
    if cmd == "testmodel":
        import json as _json
        from iqr import config
        client = config.get_model_client()
        print(f"model mode: {config.MODEL_NAME}  |  chain: {client.name}")
        probe = ('TASK: connectivity probe\nSTATE_JSON: ' +
                 _json.dumps({"task": "probe", "context": {"task_type": "probe"},
                              "observations": []}))
        try:
            reply = client.complete("Respond with exactly one JSON object.", probe)
            served = getattr(client, "last_served", "") or client.name
            print(f"answered by: {served}")
            print(f"reply (truncated): {reply[:200]}")
            errors = getattr(client, "errors", [])
            for e in errors:
                print(f"  fell back past: {e}")
            return 0
        except Exception as e:
            print(f"FAILED: {e}")
            return 1
    if cmd == "explain":
        import json as _json
        from iqr.ledger import RunLedger
        (run_id,) = rest
        events = RunLedger(run_id).read()
        if not events:
            print(f"no ledger for {run_id}")
            return 1
        for ev in events:
            name = ev["event"]
            if name == "run_start":
                print(f"[{ev['ts']}] RUN START {ev['control_id']} plan v{ev['plan_version']} "
                      f"model={ev.get('model')} topology={ev['topology']['sha256'][:12]}")
            elif name == "ingest":
                print(f"  INGEST leaves={ev['leaves']} cells={ev['cells']} "
                      f"emails={ev['emails']} images={ev['images']}")
            elif name == "match":
                print(f"  MATCH matched={ev['matched']} missing={ev['missing']}")
            elif name == "check_start":
                print(f"  CHECK {ev['check_id']} ({ev['check_type']})")
            elif name == "tool_call":
                print(f"    tool {ev['tool']} args={_json.dumps(ev['args'])[:100]} "
                      f"-> {_json.dumps(ev.get('result'))[:120]}")
            elif name == "agent_final":
                print(f"    agent[{ev.get('model')}] concluded in {ev['steps']} steps: "
                      f"{_json.dumps(ev.get('output'))[:140]}")
            elif name == "check_done":
                print(f"  CHECK {ev['check_id']} -> {ev['verdict']}")
            elif name == "verify":
                print(f"  VERIFY {ev['check_id']} agree={ev['agree']}: {ev['note'][:100]}")
            elif name == "adjudicate":
                print(f"  ADJUDICATE result={ev['result']} gaps={ev['gaps']} "
                      f"exceptions={ev['exceptions']}")
            elif name == "run_end":
                print(f"[{ev['ts']}] RUN END -> {ev['result']}")
        return 0
    if cmd == "serve":
        import uvicorn
        uvicorn.run("iqr.api.app:app", host="127.0.0.1", port=8400)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
