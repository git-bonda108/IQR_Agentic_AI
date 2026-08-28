"""Deterministic numeric recompute + tolerance compare. NO model, ever.

Supported operations cover the three fixture controls:
  sum_equals      sum(source cells) == target ± tol
  product_equals  a * b == target ± tol        (rebate = base x rate)
  delta_zero      |a - b| <= tol               (recon zero-delta)
  equals          a == b ± tol
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecomputeResult:
    ok: bool
    computed: float
    expected: float
    delta: float
    op: str


def _num(v, label: str = "value") -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError(f"non-numeric {label}: {v!r}")
    if isinstance(v, str):
        v = v.replace(",", "").replace("$", "").strip()
    return float(v)


def recompute(op: str, sources: list, target, tolerance: float = 0.01) -> RecomputeResult:
    nums = [_num(s, f"source[{i}]") for i, s in enumerate(sources)]
    if op == "sum_equals":
        computed = sum(nums)
    elif op == "product_equals":
        computed = 1.0
        for n in nums:
            computed *= n
    elif op == "delta_zero":
        if len(nums) != 2:
            raise ValueError("delta_zero needs exactly two sources")
        computed = nums[0] - nums[1]
        return RecomputeResult(abs(computed) <= tolerance, computed, 0.0, abs(computed), op)
    elif op == "equals":
        computed = nums[0]
    else:
        raise ValueError(f"unknown recompute op: {op}")
    expected = _num(target, "target")
    delta = abs(computed - expected)
    return RecomputeResult(delta <= tolerance, computed, expected, delta, op)
