"""FastAPI application for the NER risk monitoring MVP."""

import json
import os
import sqlite3
from contextlib import closing
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .alerts import build_messages, should_alert
from .reports import status_for
from .risk_engine import apply_rainfall, calculate_risk_score, risk_level

DATABASE_PATH = Path(os.getenv("NER_DATABASE_PATH", Path(__file__).with_name("ner.db")))

SEED_ZONES = [
    ("Sohra", 25.27, 91.73, 0.82, 0.68, 0.25, 0.42),
    ("Jowai", 25.45, 92.20, 0.71, 0.55, 0.18, 0.35),
    ("Haflong", 25.17, 93.02, 0.76, 0.62, 0.22, 0.58),
    ("Kohima", 25.67, 94.11, 0.79, 0.72, 0.28, 0.64),
    ("Dimapur", 25.91, 93.73, 0.39, 0.31, 0.12, 0.29),
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialise_database()
    yield


app = FastAPI(title="NER Risk Monitor", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    with closing(connect()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                slope_angle_norm REAL NOT NULL,
                historical_density_norm REAL NOT NULL,
                rainfall_24h_norm REAL NOT NULL,
                rainfall_7d_norm REAL NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL
            )
            """
        )
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
        if connection.execute("SELECT COUNT(*) FROM zones").fetchone()[0] == 0:
            for zone in SEED_ZONES:
                name, lat, lng, slope, historical, rain_24h, rain_7d = zone
                score = calculate_risk_score(slope, rain_24h, rain_7d, historical)
                connection.execute(
                    """
                    INSERT INTO zones (
                        name, lat, lng, slope_angle_norm, historical_density_norm,
                        rainfall_24h_norm, rainfall_7d_norm, risk_score, risk_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, lat, lng, slope, historical, rain_24h, rain_7d, score, risk_level(score)),
                )
        connection.commit()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/risk-scores")
def get_risk_scores() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM zones ORDER BY risk_score DESC, name").fetchall()
    return [dict(row) for row in rows]


class RainfallSimulation(BaseModel):
    zone_id: int
    rainfall_mm: float = Field(ge=0)


@app.post("/simulate-rainfall")
def simulate_rainfall(simulation: RainfallSimulation) -> dict:
    with closing(connect()) as connection:
        zone = connection.execute(
            "SELECT * FROM zones WHERE id = ?", (simulation.zone_id,)
        ).fetchone()
        if zone is None:
            raise HTTPException(status_code=404, detail=f"Zone {simulation.zone_id} not found")
        rain_24h, rain_7d = apply_rainfall(simulation.rainfall_mm, zone["rainfall_7d_norm"])
        score = calculate_risk_score(
            zone["slope_angle_norm"], rain_24h, rain_7d, zone["historical_density_norm"]
        )
        connection.execute(
            """
            UPDATE zones
            SET rainfall_24h_norm = ?, rainfall_7d_norm = ?, risk_score = ?, risk_level = ?
            WHERE id = ?
            """,
            (rain_24h, rain_7d, score, risk_level(score), simulation.zone_id),
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM zones WHERE id = ?", (simulation.zone_id,)
        ).fetchone()
        if should_alert(zone["risk_level"], updated["risk_level"]):
            messages = build_messages(
                updated, updated["risk_level"], updated["risk_score"], zone["risk_score"]
            )
            connection.execute(
                """
                INSERT INTO alerts (zone_id, level, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    updated["id"],
                    updated["risk_level"],
                    json.dumps(messages),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
    return dict(updated)


@app.get("/alerts")
def get_alerts() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.zone_id, a.level, a.message, a.created_at, z.name AS zone_name
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
            "level": row["level"],
            "messages": json.loads(row["message"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


class ReportCreate(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
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
        row = connection.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    return dict(row)


@app.get("/reports")
def get_reports() -> list[dict]:
    with closing(connect()) as connection:
        rows = connection.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]

