"""Batch evaluation: repeat the five-gate harness N times and score it.

One harness run answers "does it pass right now?". A batch answers the
production questions: how STABLE is each gate under a live model, and how much
CONFIDENCE does each individual check deserve? Confidence here is earned
frequency, not model self-report - a check is HIGH confidence because it
produced the same verdict every time and its citations always resolved, never
because a model felt sure.

  .venv/bin/python -m iqr.cli eval --batch 5
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from iqr import config
from iqr.eval.harness import run_eval
from iqr.schemas.validation_plan import ValidationPlan

GATES = ("defect_recall", "false_exception_rate", "citation_validity",
         "abstention_correctness", "reproducibility")

# Confidence bands: stability of the verdict across the batch.
HIGH, MEDIUM = 1.0, 0.8


@dataclass
class BatchReport:
    runs: int
    gate_scores: dict            # gate -> {mean, min, max, per_run}
    check_confidence: dict       # "control/check" -> {verdict, stability, level}
    batch_gates_passed: bool
    started_at: str = ""
    details: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"  batch of {self.runs} eval runs"]
        for g in GATES:
            s = self.gate_scores[g]
            lines.append(f"  {g:<24} mean {s['mean']*100:6.1f}%   "
                         f"min {s['min']*100:6.1f}%   max {s['max']*100:6.1f}%")
        lines.append(f"  {'ALL GATES (every run)':<24} "
                     f"{'PASS' if self.batch_gates_passed else 'FAIL'}")
        lines.append("  per-check confidence (verdict stability across batch):")
        for key, c in sorted(self.check_confidence.items()):
            lines.append(f"    {key:<22} {c['modal_verdict']:<5} "
                         f"stability {c['stability']*100:5.1f}%  -> {c['level']}")
        return "\n".join(lines)


def confidence_level(stability: float) -> str:
    if stability >= HIGH:
        return "HIGH"
    if stability >= MEDIUM:
        return "MEDIUM"
    return "LOW"


def run_eval_batch(plans: dict[str, ValidationPlan], fixtures_root: Path,
                   n: int = 3) -> BatchReport:
    per_gate: dict[str, list[float]] = defaultdict(list)
    check_verdicts: dict[str, list[str]] = defaultdict(list)
    all_passed = True
    reports = []

    for _ in range(n):
        r = run_eval(plans, fixtures_root)
        reports.append(r)
        all_passed = all_passed and r.gates_passed
        for g in GATES:
            per_gate[g].append(getattr(r, g))
        for cid, clean in r.details.get("clean", {}).items():
            for check_id, verdict in clean.get("checks", {}).items():
                check_verdicts[f"{cid}/{check_id}"].append(verdict)

    gate_scores = {g: {"mean": sum(v) / len(v), "min": min(v), "max": max(v),
                       "per_run": v} for g, v in per_gate.items()}
    check_confidence = {}
    for key, verdicts in check_verdicts.items():
        modal, count = Counter(verdicts).most_common(1)[0]
        stability = count / len(verdicts)
        check_confidence[key] = {"modal_verdict": modal, "stability": stability,
                                 "level": confidence_level(stability),
                                 "verdicts": verdicts}

    report = BatchReport(runs=n, gate_scores=gate_scores,
                         check_confidence=check_confidence,
                         batch_gates_passed=all_passed,
                         started_at=datetime.now(timezone.utc).isoformat(),
                         details=[r.details for r in reports])
    out_dir = config.DATA_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.started_at.replace(":", "").replace("-", "")[:15]
    (out_dir / f"eval_batch_{stamp}.json").write_text(json.dumps({
        "runs": n, "gate_scores": gate_scores,
        "check_confidence": check_confidence,
        "batch_gates_passed": all_passed, "started_at": report.started_at},
        indent=2, default=str))
    return report
