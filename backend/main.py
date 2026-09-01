"""FastAPI application for the India Multi-Hazard Risk Monitor — District Edition."""

import json
import math
import os
import sqlite3
import uuid
from contextlib import closing, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from .alerts import build_messages, should_alert
    from .reports import status_for
    from .risk_engine import (
        apply_rainfall,
        calculate_risk_score,
        risk_level,
        evaluate_multihazard_zone_risk,
    )
    from .sms_service import broadcast_alert_sms
    from .weather_service import fetch_zone_live_weather, OPENWEATHER_API_KEY
except (ImportError, ValueError):
    from alerts import build_messages, should_alert
    from reports import status_for
    from risk_engine import (
        apply_rainfall,
        calculate_risk_score,
        risk_level,
        evaluate_multihazard_zone_risk,
    )
    from sms_service import broadcast_alert_sms
    from weather_service import fetch_zone_live_weather, OPENWEATHER_API_KEY

DATABASE_PATH = Path(os.getenv("NER_DATABASE_PATH", Path(__file__).with_name("ner.db")))
DISTRICTS_FILE = Path(__file__).parent / "data" / "india_districts.json"
REPORTS_UPLOAD_DIR = Path(__file__).parent / "uploads"
MAX_REPORT_FILE_SIZE = 8 * 1024 * 1024
ALLOWED_REPORT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
}


def _load_districts_file() -> list[dict]:
    if DISTRICTS_FILE.exists():
        with open(DISTRICTS_FILE) as f:
            return json.load(f)
    return []


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialise_database()
    scheduler = getattr(_app.state, "scheduler", None)
    if scheduler is None or not scheduler.running:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            sync_live_weather,
            "interval",
            minutes=15,
            id="live-weather-sync",
            replace_existing=True,
        )
        scheduler.start()
        _app.state.scheduler = scheduler
    yield
    scheduler = getattr(_app.state, "scheduler", None)
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
    _app.state.scheduler = None


app = FastAPI(title="Bhoomi-Rakshak India Multi-Hazard Risk Monitor", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    districts = _load_districts_file()

    with closing(connect()) as connection:
        # Districts table (replaces old zones; keeps 'zones' as alias for test compatibility)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL DEFAULT 'India',
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                slope_angle_norm REAL NOT NULL,
                historical_density_norm REAL NOT NULL,
                pop_density REAL NOT NULL DEFAULT 200.0,
                rainfall_24h_norm REAL NOT NULL,
                rainfall_7d_norm REAL NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL
            )
            """
        )
        # Add state & pop_density columns if DB was created without them (migration safety)
        for col_def in [("state", "TEXT NOT NULL DEFAULT 'India'"), ("pop_density", "REAL NOT NULL DEFAULT 200.0")]:
            try:
                connection.execute(f"ALTER TABLE zones ADD COLUMN {col_def[0]} {col_def[1]}")
            except sqlite3.OperationalError:
                pass  # column already exists

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                description TEXT NOT NULL,
                photo_url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                idempotency_key TEXT DEFAULT '',
                road_name TEXT NOT NULL DEFAULT '',
                road_status TEXT NOT NULL DEFAULT 'clear'
            )
            """
        )
        for col_def in [
            ("idempotency_key", "TEXT DEFAULT ''"),
            ("road_name", "TEXT NOT NULL DEFAULT ''"),
            ("road_status", "TEXT NOT NULL DEFAULT 'clear'"),
        ]:
            try:
                connection.execute(f"ALTER TABLE reports ADD COLUMN {col_def[0]} {col_def[1]}")
            except sqlite3.OperationalError:
                pass

        if districts:
            district_names = [d["name"] for d in districts]
            # Remove any zones not in current district list
            placeholders = ",".join(["?"] * len(district_names))
            connection.execute(f"DELETE FROM zones WHERE name NOT IN ({placeholders})", tuple(district_names))
            existing_names = {row["name"] for row in connection.execute("SELECT name FROM zones").fetchall()}
            for d in districts:
                if d["name"] not in existing_names:
                    score = calculate_risk_score(
                        d["slope_angle_norm"], d["rainfall_24h_norm"],
                        d["rainfall_7d_norm"], d["historical_density_norm"]
                    )
                    connection.execute(
                        """
                        INSERT INTO zones (
                            name, state, lat, lng, slope_angle_norm, historical_density_norm,
                            pop_density, rainfall_24h_norm, rainfall_7d_norm, risk_score, risk_level
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            d["name"], d["state"], d["lat"], d["lng"],
                            d["slope_angle_norm"], d["historical_density_norm"],
                            d.get("pop_density", 200.0),
                            d["rainfall_24h_norm"], d["rainfall_7d_norm"],
                            score, risk_level(score),
                        ),
                    )
        connection.commit()


ROAD_SEGMENTS = [
    {"name": "NH6", "lat": 25.27, "lng": 91.73, "zone": "East Khasi Hills (Sohra)"},
    {"name": "NH44", "lat": 25.48, "lng": 92.12, "zone": "West Jaintia Hills (Jowai)"},
    {"name": "NH27", "lat": 25.16, "lng": 93.03, "zone": "Dima Hasao (Haflong)"},
    {"name": "NH2", "lat": 25.67, "lng": 94.11, "zone": "Kohima District"},
    {"name": "NH29", "lat": 25.90, "lng": 93.73, "zone": "Dimapur District"},
    {"name": "NH415", "lat": 27.09, "lng": 93.62, "zone": "Papum Pare (Itanagar)"},
    {"name": "NH10", "lat": 27.33, "lng": 88.61, "zone": "East Sikkim (Gangtok)"},
    {"name": "NH110", "lat": 27.04, "lng": 88.26, "zone": "Darjeeling District"},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def nearest_road_segment(lat: float, lng: float) -> dict:
    closest = {"name": "", "distance_km": float("inf")}
    for segment in ROAD_SEGMENTS:
        distance = haversine_km(lat, lng, segment["lat"], segment["lng"])
        if distance < closest["distance_km"]:
            closest = {"name": segment["name"], "distance_km": distance, "zone": segment["zone"]}
    return closest


def infer_report_road_status(lat: float, lng: float, source: str) -> tuple[str, str]:
    road = nearest_road_segment(lat, lng)
    if road["distance_km"] <= 0.5 or (source == "field_official" and road["distance_km"] <= 1.5):
        return road["name"], "reported_blocked"
    return road["name"], "clear"


def enrich_zone_with_multihazard_data(zone_dict: dict, overrides: Optional[dict] = None) -> dict:
    weather = fetch_zone_live_weather(
        zone_dict["lat"],
        zone_dict["lng"],
        state=zone_dict.get("state", "India"),
        district_name=zone_dict.get("name", ""),
    )
    ov = overrides or {}
    
    temp_c = ov.get("temp_c") if ov.get("temp_c") is not None else weather.get("temp_c", 24.0)
    rh_pct = ov.get("rh_pct") if ov.get("rh_pct") is not None else weather.get("humidity_pct", 75.0)
    wind_kmh = ov.get("wind_kmh") if ov.get("wind_kmh") is not None else weather.get("wind_kmh", 12.0)
    pga_g = ov.get("pga_g")

    eval_res = evaluate_multihazard_zone_risk(
        slope_angle_norm=zone_dict["slope_angle_norm"],
        rainfall_24h_norm=zone_dict["rainfall_24h_norm"],
        rainfall_7d_norm=zone_dict["rainfall_7d_norm"],
        historical_density_norm=zone_dict["historical_density_norm"],
        temp_c=temp_c,
        rh_pct=rh_pct,
        wind_kmh=wind_kmh,
        pop_density=zone_dict.get("pop_density", 200.0),
        state=zone_dict.get("state", "India"),
        district_name=zone_dict.get("name", ""),
        pga_g=pga_g,
    )
    zone_dict["risk_score"] = eval_res["risk_score"]
    zone_dict["risk_level"] = eval_res["risk_level"]
    zone_dict["physics"] = eval_res["physics"]
    zone_dict["ml"] = eval_res["ml"]
    zone_dict["disasters"] = eval_res.get("disasters", {})
    
    # Store simulated weather adjustments for live feedback
    disp_weather = dict(weather)
    if ov.get("temp_c") is not None:
        disp_weather["temp_c"] = ov["temp_c"]
    if ov.get("rh_pct") is not None:
        disp_weather["humidity_pct"] = ov["rh_pct"]
    if ov.get("wind_kmh") is not None:
        disp_weather["wind_kmh"] = ov["wind_kmh"]
    zone_dict["live_weather"] = disp_weather
    return zone_dict


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "country": "India", "version": "0.4.0"}


@app.get("/states")
def get_states() -> list[str]:
    """Return distinct list of Indian states present in the district registry."""
    with closing(connect()) as connection:
        rows = connection.execute("SELECT DISTINCT state FROM zones ORDER BY state").fetchall()
    return [row["state"] for row in rows]


from concurrent.futures import ThreadPoolExecutor

@app.get("/districts")
def get_districts(state: Optional[str] = None) -> list[dict]:
    """Return all Indian districts enriched with live multi-hazard metrics and weather."""
    with closing(connect()) as connection:
        if state and isinstance(state, str) and state != "ALL STATES":
            rows = connection.execute("SELECT * FROM zones WHERE state = ? ORDER BY name", (state,)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM zones ORDER BY state, name").fetchall()
    zone_dicts = [dict(row) for row in rows]
    with ThreadPoolExecutor(max_workers=18) as pool:
        return list(pool.map(enrich_zone_with_multihazard_data, zone_dicts))


@app.get("/risk-scores")
def get_risk_scores() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones ORDER BY id").fetchall()
    zone_dicts = [dict(row) for row in rows]
    with ThreadPoolExecutor(max_workers=18) as pool:
        return list(pool.map(enrich_zone_with_multihazard_data, zone_dicts))


@app.get("/risk-heatmap")
def get_risk_heatmap() -> dict:
    """Return a simple inverse-distance-weighted risk surface across the district registry."""
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones ORDER BY lat, lng").fetchall()
    points = [dict(row) for row in rows]
    if not points:
        return {"cells": [], "max_risk": 0.0}

    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    grid = []
    lat_step = max((max_lat - min_lat) / 12.0, 0.8)
    lng_step = max((max_lng - min_lng) / 12.0, 0.8)
    for lat in [min_lat + i * lat_step for i in range(13)]:
        for lng in [min_lng + j * lng_step for j in range(13)]:
            weighted_total = 0.0
            weight_sum = 0.0
            for point in points:
                dist = haversine_km(lat, lng, point["lat"], point["lng"])
                if dist <= 0:
                    weighted_total = point["risk_score"]
                    weight_sum = 1.0
                    break
                weight = 1.0 / max(dist, 0.05) ** 2
                weighted_total += point["risk_score"] * weight
                weight_sum += weight
            risk_value = (weighted_total / weight_sum) if weight_sum else 0.0
            grid.append({"lat": round(lat, 3), "lng": round(lng, 3), "risk": round(risk_value, 2)})

    return {"cells": grid, "max_risk": round(max((cell["risk"] for cell in grid), default=0.0), 2)}


@app.get("/priority-queue")
def get_priority_queue() -> list[dict]:
    """Return districts ranked by urgency using risk, density, and road-blockage signal."""
    with closing(connect()) as connection:
        rows = connection.execute(
            "SELECT z.*, (SELECT COUNT(*) FROM reports r WHERE r.source = 'field_official' AND r.road_status = 'reported_blocked' AND r.road_name IN (SELECT DISTINCT road_name FROM reports WHERE road_name <> '')) AS blocked_reports FROM zones z ORDER BY z.name"
        ).fetchall()

    max_pop = max((float(row["pop_density"]) for row in rows), default=1.0)
    queue = []
    for row in rows:
        pop_density_norm = min(1.0, float(row["pop_density"]) / max_pop)
        road_blocked_flag = 1.0 if row["blocked_reports"] else 0.0
        shelter_dist_norm = max(1.0, 4.0 + (1.0 - float(row["historical_density_norm"])) * 3.0)
        score = float(row["risk_score"]) * pop_density_norm * (1.0 + road_blocked_flag) / shelter_dist_norm
        queue.append({
            "zone_id": row["id"],
            "name": row["name"],
            "state": row["state"],
            "risk_score": round(float(row["risk_score"]), 2),
            "priority_score": round(score, 2),
            "road_blocked_flag": bool(row["blocked_reports"]),
            "population_density_norm": round(pop_density_norm, 4),
        })
    queue.sort(key=lambda item: item["priority_score"], reverse=True)
    return queue


@app.post("/sync-live-weather")
def sync_live_weather() -> dict:
    """Fetch live OpenWeather observations for each district and update current 24h/7d rainfall norms."""
    synced = []
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones").fetchall()
        for row in rows:
            z = dict(row)
            weather = fetch_zone_live_weather(
                z["lat"],
                z["lng"],
                state=z.get("state", "India"),
                district_name=z.get("name", ""),
            )
            obs_rain = weather.get("rainfall_mm", 0.0)
            rain_24h, rain_7d = apply_rainfall(obs_rain, z["rainfall_7d_norm"])
            score = calculate_risk_score(
                z["slope_angle_norm"], rain_24h, rain_7d, z["historical_density_norm"]
            )
            connection.execute(
                """
                UPDATE zones
                SET rainfall_24h_norm = ?, rainfall_7d_norm = ?, risk_score = ?, risk_level = ?
                WHERE id = ?
                """,
                (rain_24h, rain_7d, score, risk_level(score), z["id"]),
            )
            synced.append(z["name"])
        connection.commit()
    return {"status": "synced", "zones_updated": synced}


class MultiHazardSimulation(BaseModel):
    zone_id: int
    rainfall_mm: float = Field(default=0.0, ge=0)
    pga_g: Optional[float] = Field(default=None, ge=0, le=2.0)
    temperature_c: Optional[float] = Field(default=None, ge=-20, le=60)
    humidity_pct: Optional[float] = Field(default=None, ge=0, le=100)
    wind_kmh: Optional[float] = Field(default=None, ge=0, le=350)


# Backward-compatible alias for existing tests and clients
RainfallSimulation = MultiHazardSimulation


@app.post("/simulate-hazard")
@app.post("/simulate-rainfall")
def simulate_hazard(simulation: MultiHazardSimulation) -> dict:
    with closing(connect()) as connection:
        zone = connection.execute(
            "SELECT * FROM zones WHERE id = ?", (simulation.zone_id,)
        ).fetchone()
        if zone is None:
            raise HTTPException(status_code=404, detail=f"District ID {simulation.zone_id} not found")
        
        rain_24h, rain_7d = apply_rainfall(simulation.rainfall_mm, zone["rainfall_7d_norm"])

        previous_enriched = enrich_zone_with_multihazard_data(dict(zone))

        overrides = {
            "pga_g": simulation.pga_g,
            "temp_c": simulation.temperature_c,
            "rh_pct": simulation.humidity_pct,
            "wind_kmh": simulation.wind_kmh,
        }

        zone_dict = dict(zone)
        zone_dict["rainfall_24h_norm"] = rain_24h
        zone_dict["rainfall_7d_norm"] = rain_7d

        enriched = enrich_zone_with_multihazard_data(zone_dict, overrides=overrides)

        connection.execute(
            """
            UPDATE zones
            SET rainfall_24h_norm = ?, rainfall_7d_norm = ?, risk_score = ?, risk_level = ?
            WHERE id = ?
            """,
            (rain_24h, rain_7d, enriched["risk_score"], enriched["risk_level"], simulation.zone_id),
        )
        connection.commit()

        if should_alert(zone["id"], previous_enriched["risk_level"], enriched["risk_level"]):
            messages = build_messages(
                enriched, enriched["risk_level"], enriched["risk_score"], previous_enriched["risk_score"]
            )
            connection.execute(
                """
                INSERT INTO alerts (zone_id, level, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    enriched["id"],
                    enriched["risk_level"],
                    json.dumps(messages),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
            preferred = messages.get("selected_language") or messages.get("default_language") or "en"
            sms_body = messages["community"].get(preferred, messages["community"].get("en", messages["authority"]))
            broadcast_alert_sms(sms_body)
    return enriched


@app.get("/alerts")
def get_alerts() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.zone_id, a.level, a.message, a.created_at, z.name AS zone_name, z.state AS zone_state
            FROM alerts a
            JOIN zones z ON z.id = a.zone_id
            ORDER BY a.id DESC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "zone_id": row["zone_id"],
            "zone_name": row["zone_name"],
            "zone_state": row["zone_state"],
            "level": row["level"],
            "messages": json.loads(row["message"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


class ReportCreate(BaseModel):
    # Strictly restricted to Indian geographic coordinates
    lat: float = Field(ge=6.0, le=37.5)
    lng: float = Field(ge=68.0, le=97.5)
    description: str = Field(min_length=1)
    photo_url: str = ""
    source: Literal["citizen", "field_official"]
    idempotency_key: str = ""


@app.post("/reports")
async def create_report(request: Request, file: UploadFile | None = File(None)) -> dict:
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
            report = ReportCreate(**payload)
            uploaded_file = None
            uploaded_path = None
        else:
            form = await request.form()
            payload = {
                "lat": float(form.get("lat", 0.0)),
                "lng": float(form.get("lng", 0.0)),
                "description": form.get("description", ""),
                "photo_url": form.get("photo_url", ""),
                "source": form.get("source", "citizen"),
                "idempotency_key": form.get("idempotency_key", ""),
            }
            report = ReportCreate(**payload)
            uploaded_file = file
            uploaded_path = None
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid report payload: {exc}") from exc

    status = status_for(report.source)
    created_at = datetime.now(timezone.utc).isoformat()
    report_photo_url = report.photo_url or ""

    if uploaded_file is not None:
        filename = uploaded_file.filename or "report_upload"
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_REPORT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use JPG, PNG, or MP4 uploads only.")
        content_type = uploaded_file.content_type or ALLOWED_REPORT_TYPES.get(suffix, "application/octet-stream")
        if content_type not in ALLOWED_REPORT_TYPES.values():
            raise HTTPException(status_code=400, detail="Unsupported file type. Use JPG, PNG, or MP4 uploads only.")
        data = await uploaded_file.read()
        if len(data) > MAX_REPORT_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File is too large. Limit is 8MB per upload.")

        REPORTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = f"report_{uuid.uuid4().hex}{suffix}"
        uploaded_path = REPORTS_UPLOAD_DIR / safe_name
        uploaded_path.write_bytes(data)
        uploaded_file_name = safe_name
    else:
        uploaded_file_name = None

    with closing(connect()) as connection:
        if report.idempotency_key:
            existing = connection.execute(
                "SELECT * FROM reports WHERE idempotency_key = ? LIMIT 1",
                (report.idempotency_key,),
            ).fetchone()
            if existing is not None:
                return dict(existing)

        road_name, road_status = infer_report_road_status(report.lat, report.lng, report.source)
        cursor = connection.execute(
            """
            INSERT INTO reports (lat, lng, description, photo_url, source, status, created_at, idempotency_key, road_name, road_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.lat,
                report.lng,
                report.description,
                "",
                report.source,
                status,
                created_at,
                report.idempotency_key,
                road_name,
                road_status,
            ),
        )
        report_id = cursor.lastrowid
        if uploaded_file_name is not None:
            media_url = f"/reports/{report_id}/media/{uploaded_file_name}"
            connection.execute(
                "UPDATE reports SET photo_url = ? WHERE id = ?",
                (media_url, report_id),
            )
            report_photo_url = media_url
        elif report.photo_url:
            connection.execute(
                "UPDATE reports SET photo_url = ? WHERE id = ?",
                (report.photo_url, report_id),
            )
            report_photo_url = report.photo_url
        connection.commit()
        row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    row_dict = dict(row)
    row_dict["photo_url"] = report_photo_url
    row_dict["road_name"] = road_name
    row_dict["road_status"] = road_status
    return row_dict


@app.get("/reports")
def get_reports() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/reports/{report_id}/media/{filename}")
def get_report_media(report_id: int, filename: str) -> FileResponse:
    with closing(connect()) as connection:
        row = connection.execute("SELECT photo_url FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None or not row["photo_url"]:
        raise HTTPException(status_code=404, detail="Report not found")
    media_path = row["photo_url"]
    if media_path.startswith("http://") or media_path.startswith("https://"):
        raise HTTPException(status_code=400, detail="Remote URLs are not served from this media endpoint")
    if media_path != f"/reports/{report_id}/media/{filename}":
        raise HTTPException(status_code=404, detail="Report media not available")
    storage_file = REPORTS_UPLOAD_DIR / filename
    if not storage_file.exists():
        raise HTTPException(status_code=404, detail="Uploaded media was not found")
    suffix = storage_file.suffix.lower()
    media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png" if suffix == ".png" else "video/mp4"
    return FileResponse(storage_file, media_type=media_type)
