"""Sentinel node: adversarial pre-screening between match and the check
fan-out. Every detector runs deterministically; every anomaly is a ledger
event with citations. High-severity anomalies surface as exceptions in the
verdict - they never silently pass."""
from __future__ import annotations

from iqr.checks.sentinel import run_sentinel
from iqr.ledger import RunLedger


def sentinel_node(state: dict) -> dict:
    ledger = RunLedger(state["run_id"])
    anomalies = run_sentinel(state["evidence"], state["plan"])
    for a in anomalies:
        ledger.log("anomaly", detector=a.detector, severity=a.severity,
                   detail=a.detail,
                   citations=[c.model_dump(exclude_none=True) for c in a.citations])
    ledger.log("sentinel_done", total=len(anomalies),
               high=sum(1 for a in anomalies if a.severity == "high"),
               warn=sum(1 for a in anomalies if a.severity == "warn"))
    return {"anomalies": [a.model_dump() for a in anomalies]}
