"""FastAPI application for the India Multi-Hazard Risk Monitor — District Edition."""

import json
import os
import sqlite3
from contextlib import closing, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
    from weather_service import fetch_zone_live_weather, OPENWEATHER_API_KEY

DATABASE_PATH = Path(os.getenv("NER_DATABASE_PATH", Path(__file__).with_name("ner.db")))
DISTRICTS_FILE = Path(__file__).parent / "data" / "india_districts.json"


def _load_districts_file() -> list[dict]:
    if DISTRICTS_FILE.exists():
        with open(DISTRICTS_FILE) as f:
            return json.load(f)
    return []


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialise_database()
    yield


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
                created_at TEXT NOT NULL
            )
            """
        )

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


def enrich_zone_with_multihazard_data(zone_dict: dict, overrides: Optional[dict] = None) -> dict:
    weather = fetch_zone_live_weather(zone_dict["lat"], zone_dict["lng"])
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


@app.get("/districts")
def get_districts(state: Optional[str] = Query(None, description="Filter districts by Indian state")) -> list[dict]:
    """Return all 14 Indian districts enriched with live multi-hazard metrics and weather."""
    with closing(connect()) as connection:
        if state:
            rows = connection.execute("SELECT * FROM zones WHERE state = ? ORDER BY name", (state,)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM zones ORDER BY state, name").fetchall()
    return [enrich_zone_with_multihazard_data(dict(row)) for row in rows]


@app.get("/risk-scores")
def get_risk_scores() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones ORDER BY id").fetchall()
    return [enrich_zone_with_multihazard_data(dict(row)) for row in rows]


@app.post("/sync-live-weather")
def sync_live_weather() -> dict:
    """Fetch live OpenWeather observations for each district and update current 24h/7d rainfall norms."""
    synced = []
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones").fetchall()
        for row in rows:
            z = dict(row)
            weather = fetch_zone_live_weather(z["lat"], z["lng"])
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
        
        if should_alert(zone["id"], zone["risk_level"], enriched["risk_level"]):
            messages = build_messages(
                enriched, enriched["risk_level"], enriched["risk_score"], zone["risk_score"]
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


@app.post("/reports")
def create_report(report: ReportCreate) -> dict:
    status = status_for(report.source)
    created_at = datetime.now(timezone.utc).isoformat()
    with closing(connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO reports (lat, lng, description, photo_url, source, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.lat,
                report.lng,
                report.description,
                report.photo_url,
                report.source,
                status,
                created_at,
            ),
        )
        report_id = cursor.lastrowid
        connection.commit()
        row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return dict(row)


@app.get("/reports")
def get_reports() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]
