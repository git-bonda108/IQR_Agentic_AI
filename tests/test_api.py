"""Phase 8 acceptance: run a control, adjudicate, download the pack - via API."""
from fastapi.testclient import TestClient

from iqr.api.app import app

client = TestClient(app)


def test_run_and_download_pack(plans, fixtures_root):
    resp = client.post("/api/runs", json={"control_id": "C23024",
                                          "package_ref": str(fixtures_root / "C23024" / "package")})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["verdict"]["result"] == "pass"
    run_id = data["run_id"]

    pack = client.get(f"/api/runs/{run_id}/pack")
    assert pack.status_code == 200
    assert pack.headers["content-type"] == "application/zip"

    ledger = client.get(f"/api/runs/{run_id}/ledger")
    assert ledger.status_code == 200
    events = [e["event"] for e in ledger.json()]
    assert "run_start" in events and "adjudicate" in events


def test_exception_adjudication_flow(plans):
    resp = client.post("/api/exceptions/adjudicate", json={
        "control_id": "C10032", "check_id": "t1",
        "pattern": "WEBI stamp equals approval minute",
        "human_verdict": "pass", "rationale": "simultaneous stamps acceptable",
        "run_id": "run-test"})
    assert resp.status_code == 200
    pending = client.get("/api/exceptions").json()
    assert any(p["check_id"] == "t1" for p in pending)


def test_topology_endpoint():
    sig = client.get("/api/topology").json()
    assert sig["sha256"]
