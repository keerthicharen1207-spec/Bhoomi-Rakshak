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


def test_simulate_rainfall_updates_zone_risk(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        zone = client.get("/risk-scores").json()[0]
        response = client.post(
            "/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0}
        )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == zone["id"]
    assert updated["rainfall_24h_norm"] == 1.0
    assert updated["risk_score"] > zone["risk_score"]
    assert updated["risk_level"] == "High"


def test_simulate_rainfall_persists_recomputed_zone(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        zone = client.get("/risk-scores").json()[0]
        client.post("/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0})
        refreshed = client.get("/risk-scores").json()

    stored = next(item for item in refreshed if item["id"] == zone["id"])
    assert stored["rainfall_24h_norm"] == 1.0
    assert stored["risk_score"] > zone["risk_score"]


def test_simulate_rainfall_rejects_unknown_zone(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.post("/simulate-rainfall", json={"zone_id": 999, "rainfall_mm": 50.0})

    assert response.status_code == 404


def test_simulate_rainfall_rejects_negative_rainfall(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.post("/simulate-rainfall", json={"zone_id": 1, "rainfall_mm": -5.0})

    assert response.status_code == 422


def test_alerts_feed_starts_empty(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        assert client.get("/alerts").json() == []


def test_threshold_crossing_creates_exactly_one_alert(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        zone = client.get("/risk-scores").json()[0]
        first = client.post(
            "/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0}
        ).json()
        assert first["risk_level"] == "High"

        alerts = client.get("/alerts").json()
        assert len(alerts) == 1
        assert alerts[0]["zone_id"] == zone["id"]
        assert alerts[0]["zone_name"] == zone["name"]
        assert alerts[0]["level"] == "High"
        assert set(alerts[0]["messages"]["community"]) == {"en", "as", "nl"}
        assert "NH2" in alerts[0]["messages"]["community"]["en"]

        client.post("/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0})
        assert len(client.get("/alerts").json()) == 1


def test_escalation_to_severe_adds_severe_alert_without_duplicates(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        sohra = next(z for z in client.get("/risk-scores").json() if z["name"] == "Sohra")
        for _ in range(8):
            response = client.post(
                "/simulate-rainfall", json={"zone_id": sohra["id"], "rainfall_mm": 200.0}
            )
        assert response.json()["risk_level"] == "Severe"

        alerts = client.get("/alerts").json()
        assert [alert["level"] for alert in alerts] == ["Severe", "High"]

        client.post("/simulate-rainfall", json={"zone_id": sohra["id"], "rainfall_mm": 200.0})
        assert len(client.get("/alerts").json()) == 2
