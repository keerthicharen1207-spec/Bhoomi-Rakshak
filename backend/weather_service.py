"""Live Weather Service Integration (OpenWeatherMap API).

Fetches live temperature, relative humidity, wind speed, and precipitation for NER zone coordinates.
Handles key propagation delays (401 Unauthorized during new key activation) with graceful fallbacks.
"""

import os
import re
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

from pathlib import Path

def _load_api_key() -> str:
    key = os.getenv("OPENWEATHER_API_KEY", "")
    if not key:
        for env_path in [Path(".env"), Path("backend/.env"), Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.strip().startswith("OPENWEATHER_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            os.environ["OPENWEATHER_API_KEY"] = key
                            return key
    return key

OPENWEATHER_API_KEY = _load_api_key()
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


import time
from concurrent.futures import ThreadPoolExecutor

_WEATHER_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 600.0  # 10 minutes
_IMD_RAINFALL_URL = "https://sayantan-aquacarta.github.io/rainfall-pipeline/api/latest.json"


def ingest_source(name: str, cadence: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize each upstream data source into a consistent ingestion contract."""
    return {
        "name": name,
        "cadence": cadence,
        "fields": fields,
    }


def _normalize_place_name(value: str) -> str:
    cleaned = value.lower().replace("&", "and")
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    cleaned = cleaned.replace("district", "").replace("dist", "").replace("division", "")
    return cleaned


def _match_imd_district(state: Optional[str], district_name: Optional[str], rows: list[dict]) -> Optional[dict]:
    if not rows:
        return None

    target_state = _normalize_place_name(state or "")
    target_district = _normalize_place_name(district_name or "")

    if not target_district:
        return None

    best_match = None
    best_score = -1

    for row in rows:
        row_state = _normalize_place_name(str(row.get("state", "")))
        row_district = _normalize_place_name(str(row.get("district", "")))

        if not row_district:
            continue

        exact = row_district == target_district
        state_match = bool(target_state and row_state == target_state)
        contains = target_district in row_district or row_district in target_district
        score = 0
        if exact:
            score += 50
        if state_match:
            score += 25
        if contains:
            score += 15
        if row_district.startswith(target_district[:4]) or target_district.startswith(row_district[:4]):
            score += 5

        if score > best_score:
            best_score = score
            best_match = row

    if best_score >= 15:
        return best_match
    return None


def fetch_imd_rainfall_for_zone(state: Optional[str] = None, district_name: Optional[str] = None) -> Optional[dict]:
    """Fetch the public IMD district rainfall bulletin and map it to this district's name/state."""
    try:
        response = httpx.get(_IMD_RAINFALL_URL, timeout=8.0)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("rows", [])
        if not rows:
            return None
        match = _match_imd_district(state, district_name, rows)
        if not match:
            return None
        return {
            "source": "imd_daily_rainfall",
            "district": match.get("district"),
            "state": match.get("state"),
            "day_actual_mm": float(match.get("day_actual_mm", 0.0) or 0.0),
            "day_normal_mm": float(match.get("day_normal_mm", 0.0) or 0.0),
            "day_departure_pct": float(match.get("day_departure_pct", 0.0) or 0.0),
            "period_actual_mm": float(match.get("period_actual_mm", 0.0) or 0.0),
            "period_normal_mm": float(match.get("period_normal_mm", 0.0) or 0.0),
            "period_departure_pct": float(match.get("period_departure_pct", 0.0) or 0.0),
            "date": match.get("date"),
            "ingestion": ingest_source("IMD District Rainfall Bulletin", "daily", {
                "day_actual_mm": "mm",
                "day_normal_mm": "mm",
                "day_departure_pct": "%",
            }),
        }
    except Exception as exc:
        logger.warning("IMD rainfall fetch failed for %s/%s: %s", state, district_name, exc)
        return None


def fetch_zone_live_weather(
    lat: float,
    lng: float,
    api_key: Optional[str] = None,
    force_refresh: bool = False,
    state: Optional[str] = None,
    district_name: Optional[str] = None,
) -> Dict[str, Any]:
    cache_key = f"{round(lat, 2)}_{round(lng, 2)}|{(state or '').lower()}|{(district_name or '').lower()}"
    now = time.time()

    if not force_refresh and cache_key in _WEATHER_CACHE:
        cached_time, cached_val = _WEATHER_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return dict(cached_val)

    imd_rain = fetch_imd_rainfall_for_zone(state, district_name)
    key = api_key or _load_api_key()

    if not key:
        result = {
            "status": "hybrid",
            "message": "OpenWeatherMap key unavailable; using public IMD rainfall feed as the live rainfall source.",
            "temp_c": 24.0,
            "humidity_pct": 75.0,
            "wind_kmh": 12.0,
            "rainfall_mm": float(imd_rain["day_actual_mm"]) if imd_rain else 0.0,
            "weather_desc": "imd rainfall fallback",
            "source": "imd_daily_rainfall",
            "ingestion": [
                ingest_source("IMD District Rainfall Bulletin", "daily", {
                    "day_actual_mm": "mm",
                    "period_actual_mm": "mm",
                })
            ],
        }
        _WEATHER_CACHE[cache_key] = (now, result)
        return result

    url = f"{OPENWEATHER_BASE_URL}?lat={lat}&lon={lng}&appid={key}&units=metric"
    try:
        response = httpx.get(url, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            main = data.get("main", {})
            wind = data.get("wind", {})
            rain = data.get("rain", {})

            rain_1h = float(rain.get("1h", 0.0))
            rain_3h = float(rain.get("3h", 0.0))
            if rain_1h > 0:
                rainfall_mm = rain_1h * 24.0
            elif rain_3h > 0:
                rainfall_mm = rain_3h * 8.0
            else:
                rainfall_mm = 0.0

            if imd_rain:
                rainfall_mm = max(rainfall_mm, float(imd_rain["day_actual_mm"]))
                source_name = "hybrid_imd_openweather"
                ingest_chain = [
                    ingest_source("OpenWeatherMap", "live", {"temp_c": "C", "humidity_pct": "%", "wind_kmh": "km/h", "rainfall_mm": "mm"}),
                    imd_rain["ingestion"],
                ]
            else:
                source_name = "openweather"
                ingest_chain = [
                    ingest_source("OpenWeatherMap", "live", {"temp_c": "C", "humidity_pct": "%", "wind_kmh": "km/h", "rainfall_mm": "mm"})
                ]

            result = {
                "status": "live",
                "temp_c": float(main.get("temp", 24.0)),
                "humidity_pct": float(main.get("humidity", 75.0)),
                "wind_kmh": round(float(wind.get("speed", 3.5)) * 3.6, 1),
                "rainfall_mm": round(rainfall_mm, 1),
                "weather_desc": data.get("weather", [{}])[0].get("description", "clear"),
                "source": source_name,
                "ingestion": ingest_chain,
            }
            _WEATHER_CACHE[cache_key] = (now, result)
            return result
        elif response.status_code == 401:
            result = {
                "status": "activating",
                "message": "OpenWeatherMap API key is activating (typically takes 10-30 mins after creation)",
                "temp_c": 24.0,
                "humidity_pct": 75.0,
                "wind_kmh": 12.0,
                "rainfall_mm": float(imd_rain["day_actual_mm"]) if imd_rain else 20.0,
                "weather_desc": "key activating",
                "source": "imd_daily_rainfall" if imd_rain else "openweather",
                "ingestion": [imd_rain["ingestion"]] if imd_rain else [ingest_source("OpenWeatherMap", "live", {"rainfall_mm": "mm"})],
            }
            _WEATHER_CACHE[cache_key] = (now, result)
            return result
        else:
            result = {
                "status": "error",
                "message": f"API returned status {response.status_code}",
                "temp_c": 24.0,
                "humidity_pct": 75.0,
                "wind_kmh": 12.0,
                "rainfall_mm": float(imd_rain["day_actual_mm"]) if imd_rain else 15.0,
                "weather_desc": "offline fallback",
                "source": "imd_daily_rainfall" if imd_rain else "openweather",
                "ingestion": [imd_rain["ingestion"]] if imd_rain else [ingest_source("OpenWeatherMap", "live", {"rainfall_mm": "mm"})],
            }
            _WEATHER_CACHE[cache_key] = (now, result)
            return result
    except Exception as exc:
        result = {
            "status": "offline",
            "message": f"Connection exception: {exc}",
            "temp_c": 24.0,
            "humidity_pct": 75.0,
            "wind_kmh": 12.0,
            "rainfall_mm": float(imd_rain["day_actual_mm"]) if imd_rain else 15.0,
            "weather_desc": "offline fallback",
            "source": "imd_daily_rainfall" if imd_rain else "openweather",
            "ingestion": [imd_rain["ingestion"]] if imd_rain else [ingest_source("OpenWeatherMap", "live", {"rainfall_mm": "mm"})],
        }
        _WEATHER_CACHE[cache_key] = (now, result)
        return result
