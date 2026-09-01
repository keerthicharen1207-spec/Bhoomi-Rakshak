"""FastAPI application for the NER risk monitoring MVP."""

import os
import sqlite3
from contextlib import closing
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .risk_engine import calculate_risk_score, risk_level

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
