"""The five gate metrics. Citation validity is a HARD gate: anything under
100% fails the whole evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalReport:
    defect_recall: float
    false_exception_rate: float
    citation_validity: float          # must be 1.0
    abstention_correctness: float
    reproducibility: float
    details: dict = field(default_factory=dict)

    @property
    def gates_passed(self) -> bool:
        return (self.citation_validity == 1.0
                and self.defect_recall == 1.0
                and self.false_exception_rate == 0.0
                and self.abstention_correctness == 1.0
                and self.reproducibility == 1.0)

    def summary(self) -> str:
        rows = [("defect recall", self.defect_recall, "EXISTENTIAL"),
                ("false-exception rate", self.false_exception_rate, "REVIEWER TRUST"),
                ("citation validity", self.citation_validity, "100% HARD GATE"),
                ("abstention correctness", self.abstention_correctness, "HONESTY"),
                ("reproducibility", self.reproducibility, "CONSISTENCY")]
        lines = [f"  {name:<24} {value:>7.1%}   ({tag})" for name, value, tag in rows]
        lines.append(f"  {'ALL GATES':<24} {'PASS' if self.gates_passed else 'FAIL':>7}")
        return "\n".join(lines)
