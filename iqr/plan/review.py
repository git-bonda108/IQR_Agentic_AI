"""SME approval and freezing. Approved plans are immutable and versioned:
writing the same control+version twice is an error, and runtime refuses any
plan that has not been through this gate."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from iqr import config
from iqr.schemas.validation_plan import ValidationPlan


class PlanAlreadyFrozen(Exception):
    pass


def approve_and_freeze(plan: ValidationPlan, sme: str) -> ValidationPlan:
    approved = plan.model_copy(update={"approved_by": sme,
                                       "approved_at": datetime.now(timezone.utc)})
    config.ensure_dirs()
    d = config.PLAN_STORE_DIR / plan.control_id
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{plan.version}.json"
    if path.exists():
        raise PlanAlreadyFrozen(
            f"{plan.control_id} v{plan.version} is frozen; bump the version and "
            "re-approve instead of mutating an approved plan")
    path.write_text(approved.model_dump_json(indent=2))
    return approved


def load_plan(control_id: str, version: str) -> ValidationPlan:
    path = config.PLAN_STORE_DIR / control_id / f"{version}.json"
    return ValidationPlan.model_validate_json(path.read_text())


def latest_version(control_id: str) -> str | None:
    d = config.PLAN_STORE_DIR / control_id
    if not d.is_dir():
        return None
    versions = sorted(p.stem for p in d.glob("*.json"))
    return versions[-1] if versions else None
