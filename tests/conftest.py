import os
import tempfile
from pathlib import Path

os.environ.setdefault("IQR_DATA_DIR", tempfile.mkdtemp(prefix="iqr_test_data_"))
os.environ.setdefault("IQR_MODEL", "stub")

import pytest

from tests.fixtures.build_fixtures import FIXTURES, build_all

CONTROLS = [("C23024", "quarterly"), ("C10032", "monthly"), ("C10075", "quarterly")]


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    if not (FIXTURES / "C23024").exists():
        build_all()
    return FIXTURES


@pytest.fixture(scope="session")
def plans(fixtures_root):
    from iqr.plan.compiler import compile_plan
    from iqr.plan.review import approve_and_freeze, load_plan, latest_version

    result = {}
    for cid, freq in CONTROLS:
        version = latest_version(cid)
        if version:
            result[cid] = load_plan(cid, version)
            continue
        plan = compile_plan(str(fixtures_root / cid / f"404_{cid}.docx"), cid, freq)
        result[cid] = approve_and_freeze(plan, sme="test-sme")
    return result


@pytest.fixture(scope="session")
def graphs(fixtures_root):
    from iqr.ingest.graph_builder import build_evidence_graph
    return {cid: build_evidence_graph(str(fixtures_root / cid / "package"))
            for cid, _ in CONTROLS}
