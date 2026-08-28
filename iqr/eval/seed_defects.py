"""Inject planted defects into a clean golden pack -> the traps the eval
harness uses to measure defect recall and abstention correctness.

Each seeder copies the clean package and mutates exactly one thing, exactly
the way real defects present: an altered total, an inverted approval date, a
missing sign-off, a preparer approving their own work, a screenshot that no
longer ties.
"""
from __future__ import annotations

import email
import email.policy
import shutil
from email.utils import format_datetime
from pathlib import Path

import openpyxl


def copy_package(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def alter_cell(pkg: Path, workbook: str, sheet: str, cell: str, value) -> None:
    path = pkg / workbook
    wb = openpyxl.load_workbook(path)
    wb[sheet][cell] = value
    wb.save(path)


def shift_email_date(pkg: Path, eml_name: str, new_date) -> None:
    path = pkg / eml_name
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    msg.replace_header("Date", format_datetime(new_date))
    path.write_bytes(msg.as_bytes())


def set_email_sender(pkg: Path, eml_name: str, sender: str) -> None:
    path = pkg / eml_name
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    msg.replace_header("From", sender)
    path.write_bytes(msg.as_bytes())


def remove_artifact(pkg: Path, name: str) -> None:
    (pkg / name).unlink()


def build_variants(fixtures_root: Path, out_root: Path) -> list[dict]:
    """Create every seeded variant; return the expectation table the harness
    scores against: which check must catch what, or which gap must be declared."""
    from datetime import datetime, timezone, timedelta
    specs = []

    p = copy_package(fixtures_root / "C23024" / "package",
                     out_root / "C23024_altered_total")
    alter_cell(p, "rebate_Q2_2026.xlsx", "Sales", "B7", 462000.0)
    specs.append({"control_id": "C23024", "variant": "altered_total", "package": str(p),
                  "expect": {"n1": "fail"}, "kind": "defect"})

    p = copy_package(fixtures_root / "C23024" / "package",
                     out_root / "C23024_missing_signoff")
    remove_artifact(p, "approval_C23024.eml")
    specs.append({"control_id": "C23024", "variant": "missing_signoff", "package": str(p),
                  "expect": {"s1": "gap"}, "kind": "abstention"})

    p = copy_package(fixtures_root / "C10032" / "package",
                     out_root / "C10032_inverted_timestamps")
    shift_email_date(p, "approval_C10032.eml",
                     datetime(2026, 6, 3, 3, 0, tzinfo=timezone(timedelta(hours=-5))))
    specs.append({"control_id": "C10032", "variant": "inverted_timestamps", "package": str(p),
                  "expect": {"t1": "fail"}, "kind": "defect"})

    p = copy_package(fixtures_root / "C10075" / "package",
                     out_root / "C10075_preparer_equals_reviewer")
    set_email_sender(p, "approval_C10075.eml", "dana.wu@hp.com")
    specs.append({"control_id": "C10075", "variant": "preparer_equals_reviewer",
                  "package": str(p), "expect": {"s1": "fail"}, "kind": "defect"})

    p = copy_package(fixtures_root / "C10075" / "package",
                     out_root / "C10075_screenshot_mismatch")
    alter_cell(p, "emr_workbook_Q2_2026.xlsx", "EMR", "C7", 4821)
    specs.append({"control_id": "C10075", "variant": "screenshot_mismatch",
                  "package": str(p), "expect": {"v1": "fail"}, "kind": "defect"})
    return specs
