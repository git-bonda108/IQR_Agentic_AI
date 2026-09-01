"""Intake: bulk package understanding before any control is chosen."""
from fastapi.testclient import TestClient

from iqr.api.app import app
from iqr.intake import analyze_package

client = TestClient(app)


def test_intake_infers_the_right_control(plans, fixtures_root):
    result = analyze_package(str(fixtures_root / "C23024" / "package"))
    assert result["suggested_control"] == "C23024"
    assert result["confidence"] == 1.0                 # all required evidence present
    assert result["candidates"][0]["control_id"] == "C23024"
    assert result["summary"]["leaves"] > 0 and result["summary"]["cells"] > 0
    # the story is grounded in mechanical facts, not invented
    assert "C23024" in result["story"]
    assert not result["candidates"][0]["missing"]


def test_intake_reports_missing_evidence_upfront(plans, fixtures_root, tmp_path):
    import shutil
    pkg = tmp_path / "pkg"
    shutil.copytree(fixtures_root / "C23024" / "package", pkg)
    for eml in pkg.glob("*.eml"):
        eml.unlink()                                   # remove the approval email
    result = analyze_package(str(pkg))
    best = result["candidates"][0]
    assert best["control_id"] == "C23024"
    assert best["missing"]                             # flagged BEFORE any run
    assert best["coverage"] < 1.0


def test_intake_api_roundtrip(plans, fixtures_root):
    r = client.post("/api/intake",
                    json={"package_ref": str(fixtures_root / "C10075" / "package")})
    assert r.status_code == 200
    body = r.json()
    assert body["suggested_control"] == "C10075"
    assert body["story"]
    r = client.post("/api/intake", json={"package_ref": "/nope"})
    assert r.status_code == 400
