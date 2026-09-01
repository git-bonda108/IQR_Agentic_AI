"""Invariant 3: same pack + same plan version -> identical Verdict (modulo run_id).
Also: runtime refuses unapproved plans; frozen plans are immutable."""
import json

import pytest

from iqr.graph.build_graph import run_control, topology_signature
from iqr.plan.review import PlanAlreadyFrozen, approve_and_freeze


def _fingerprint(verdict):
    return json.dumps(verdict.model_dump(exclude={"run_id"}), sort_keys=True, default=str)


def test_identical_verdict_across_runs(plans, fixtures_root):
    pkg = str(fixtures_root / "C23024" / "package")
    prints = {_fingerprint(run_control(plans["C23024"], pkg, run_id=f"repro-{i}"))
              for i in range(3)}
    assert len(prints) == 1


def test_topology_is_versioned_and_serializable():
    sig = topology_signature()
    assert sig["version"] and sig["sha256"]
    assert topology_signature() == sig


def test_runtime_refuses_unapproved_plan(plans, fixtures_root):
    draft = plans["C23024"].model_copy(update={"approved_by": None, "approved_at": None})
    with pytest.raises(PermissionError, match="not SME-approved"):
        run_control(draft, str(fixtures_root / "C23024" / "package"))


def test_frozen_plan_is_immutable(plans):
    with pytest.raises(PlanAlreadyFrozen):
        approve_and_freeze(plans["C23024"].model_copy(update={"approved_by": None}),
                           sme="someone-else")
