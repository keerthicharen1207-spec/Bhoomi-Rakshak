from fastapi.testclient import TestClient

from backend.main import app


def test_risk_scores_returns_seeded_zones(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.get("/risk-scores")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 14
    assert {zone["risk_level"] for zone in zones} >= {"Normal", "Watch"}
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
    assert updated["risk_level"] in {"Warning", "Evacuate"}


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
    from backend.alerts import last_alert_time
    last_alert_time.clear()
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        # Use Sohra district which starts at Watch and escalates to Warning on 200mm rainfall
        zone = next(z for z in client.get("/risk-scores").json() if "Sohra" in z["name"])
        first = client.post(
            "/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0}
        ).json()
        assert first["risk_level"] == "Warning"

        alerts = client.get("/alerts").json()
        assert len(alerts) == 1
        assert alerts[0]["zone_id"] == zone["id"]
        assert alerts[0]["zone_name"] == zone["name"]
        assert alerts[0]["level"] == "Warning"
        assert set(alerts[0]["messages"]["community"]) == {"en", "as", "nl"}

        client.post("/simulate-rainfall", json={"zone_id": zone["id"], "rainfall_mm": 200.0})
        assert len(client.get("/alerts").json()) == 1


def test_escalation_to_severe_adds_severe_alert_without_duplicates(tmp_path, monkeypatch):
    from backend.alerts import last_alert_time
    last_alert_time.clear()
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        sohra = next(z for z in client.get("/risk-scores").json() if "Sohra" in z["name"])
        for _ in range(8):
            last_alert_time.clear()  # simulate passing cooldown for escalating alert test
            response = client.post(
                "/simulate-rainfall", json={"zone_id": sohra["id"], "rainfall_mm": 200.0}
            )
        assert response.json()["risk_level"] == "Evacuate"

        alerts = client.get("/alerts").json()
        assert [alert["level"] for alert in alerts] == ["Evacuate", "Warning"]

        client.post("/simulate-rainfall", json={"zone_id": sohra["id"], "rainfall_mm": 200.0})
        assert len(client.get("/alerts").json()) == 2


def test_submit_citizen_report_starts_pending(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "lat": 25.27,
                "lng": 91.73,
                "description": "Cracks widening on the slope face",
                "photo_url": "https://example.com/photo.jpg",
                "source": "citizen",
            },
        )

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "pending"
    assert report["description"] == "Cracks widening on the slope face"
    assert report["photo_url"] == "https://example.com/photo.jpg"
    assert report["id"] == 1
    assert report["created_at"]


def test_submit_field_official_report_is_auto_verified(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "lat": 25.45,
                "lng": 92.20,
                "description": "Roadside slump blocking half the carriageway",
                "photo_url": "",
                "source": "field_official",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "verified"


def test_reports_listed_newest_first(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        client.post("/reports", json={"lat": 25.27, "lng": 91.73, "description": "First report", "photo_url": "", "source": "citizen"})
        client.post("/reports", json={"lat": 25.67, "lng": 94.11, "description": "Second report", "photo_url": "", "source": "field_official"})

        reports = client.get("/reports").json()

    assert [report["id"] for report in reports] == [2, 1]


def test_report_rejects_invalid_payloads(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    with TestClient(app) as client:
        bad_latitude = client.post(
            "/reports", json={"lat": 200.0, "lng": 91.73, "description": "x", "photo_url": "", "source": "citizen"}
        )
        bad_source = client.post(
            "/reports", json={"lat": 25.27, "lng": 91.73, "description": "x", "photo_url": "", "source": "drone"}
        )
        empty_description = client.post(
            "/reports", json={"lat": 25.27, "lng": 91.73, "description": "", "photo_url": "", "source": "citizen"}
        )

    assert bad_latitude.status_code == 422
    assert bad_source.status_code == 422
    assert empty_description.status_code == 422
