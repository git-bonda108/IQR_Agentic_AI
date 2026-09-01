"""The eval harness: run every golden pack and every seeded variant, score the
five gate metrics. This is the regression gate for governed learning - no plan
amendment or exemplar ships unless this passes.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from iqr.eval.metrics import EvalReport
from iqr.eval.seed_defects import build_variants
from iqr.graph.build_graph import run_control
from iqr.ingest.graph_builder import build_evidence_graph
from iqr.schemas.finding import Verdict
from iqr.schemas.validation_plan import ValidationPlan
from iqr.tools.citation import resolve

REPRO_RUNS = 2


def _verdict_fingerprint(v: Verdict) -> str:
    """The semantic verdict that must be identical run over run: the result,
    each check's verdict, and the deduplicated set of evidence it cites.
    Excluded on purpose: run_id; free-text `detail` (a live model phrases the
    same grounded conclusion differently); citation ORDER and the
    path-numbered computed_values keys (an agent may read the same cells in a
    different order - same facts, different traversal). The reproducibility
    law binds the verdict and its evidence base, not the walk that got there."""
    findings = sorted(
        ({"check_id": f.check_id, "verdict": f.verdict,
          "evidence": sorted({c.locator_str() for c in f.citations})}
         for f in v.findings), key=lambda f: f["check_id"])
    payload = {"control_id": v.control_id, "plan_version": v.plan_version,
               "result": v.result, "findings": findings, "gaps": sorted(v.gaps)}
    return json.dumps(payload, sort_keys=True, default=str)


def run_eval(plans: dict[str, ValidationPlan], fixtures_root: Path,
             variants_root: Path | None = None) -> EvalReport:
    variants_root = variants_root or Path(tempfile.mkdtemp(prefix="iqr_variants_"))
    details: dict = {"clean": {}, "variants": {}}

    total_citations = valid_citations = 0
    clean_checks = clean_flagged = 0
    repro_ok = repro_total = 0

    # ---- clean packs: no false exceptions; reproducible; citations resolve
    for control_id, plan in sorted(plans.items()):
        pkg = fixtures_root / control_id / "package"
        prints = []
        for i in range(REPRO_RUNS):
            verdict = run_control(plan, str(pkg), run_id=f"eval-{control_id}-clean-{i}-{uuid.uuid4().hex[:6]}")
            prints.append(_verdict_fingerprint(verdict))
            if i == 0:
                graph = build_evidence_graph(str(pkg))
                for f in verdict.findings:
                    clean_checks += 1
                    if f.verdict != "pass":
                        clean_flagged += 1
                    for c in f.citations:
                        total_citations += 1
                        valid_citations += int(resolve(c, graph))
                details["clean"][control_id] = {
                    "result": verdict.result,
                    "checks": {f.check_id: f.verdict for f in verdict.findings}}
        repro_total += 1
        repro_ok += int(len(set(prints)) == 1)

    # ---- seeded variants: planted defects caught; absences declared honestly
    specs = build_variants(fixtures_root, variants_root)
    defects_total = defects_caught = 0
    abst_total = abst_correct = 0
    for spec in specs:
        plan = plans[spec["control_id"]]
        verdict = run_control(plan, spec["package"],
                              run_id=f"eval-{spec['control_id']}-{spec['variant']}-{uuid.uuid4().hex[:6]}")
        graph = build_evidence_graph(spec["package"])
        for f in verdict.findings:
            for c in f.citations:
                total_citations += 1
                valid_citations += int(resolve(c, graph))
        got = {f.check_id: f.verdict for f in verdict.findings}
        outcome = {}
        for check_id, expected in spec["expect"].items():
            actual = got.get(check_id, "absent")
            outcome[check_id] = {"expected": expected, "actual": actual}
            if spec["kind"] == "defect":
                defects_total += 1
                defects_caught += int(actual == expected)
            else:
                abst_total += 1
                abst_correct += int(actual == expected)
        details["variants"][spec["variant"]] = {"result": verdict.result, **outcome}

    return EvalReport(
        defect_recall=defects_caught / defects_total if defects_total else 1.0,
        false_exception_rate=clean_flagged / clean_checks if clean_checks else 0.0,
        citation_validity=valid_citations / total_citations if total_citations else 0.0,
        abstention_correctness=abst_correct / abst_total if abst_total else 1.0,
        reproducibility=repro_ok / repro_total if repro_total else 0.0,
        details=details)
