from fastapi.testclient import TestClient

from backend.main import app


def test_risk_scores_returns_seeded_zones(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.get("/risk-scores")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 5
    assert {zone["risk_level"] for zone in zones} >= {"Low", "Medium"}
    assert all(0 <= zone["risk_score"] <= 100 for zone in zones)
