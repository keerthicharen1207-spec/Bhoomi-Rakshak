"""Live Weather Service Integration (OpenWeatherMap API).

Fetches live temperature, relative humidity, wind speed, and precipitation for NER zone coordinates.
Handles key propagation delays (401 Unauthorized during new key activation) with graceful fallbacks.
"""

import os
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def fetch_zone_live_weather(lat: float, lng: float, api_key: Optional[str] = None) -> Dict[str, Any]:
    key = api_key or OPENWEATHER_API_KEY
    if not key:
        return {
            "status": "disabled",
            "message": "No API key configured",
            "temp_c": 24.0,
            "humidity_pct": 75.0,
            "wind_kmh": 12.0,
            "rainfall_mm": 0.0,
        }

    url = f"{OPENWEATHER_BASE_URL}?lat={lat}&lon={lng}&appid={key}&units=metric"
    try:
        response = httpx.get(url, timeout=6.0)
        if response.status_code == 200:
            data = response.json()
            main = data.get("main", {})
            wind = data.get("wind", {})
            rain = data.get("rain", {})

            # Extract 1h rain or convert 3h rain to 24h estimation
            rain_1h = rain.get("1h", 0.0)
            rain_3h = rain.get("3h", 0.0)
            rainfall_mm = rain_1h * 24.0 if rain_1h > 0 else (rain_3h * 8.0 if rain_3h > 0 else 15.0)

            return {
                "status": "live",
                "temp_c": float(main.get("temp", 24.0)),
                "humidity_pct": float(main.get("humidity", 75.0)),
                "wind_kmh": round(float(wind.get("speed", 3.5)) * 3.6, 1),
                "rainfall_mm": round(rainfall_mm, 1),
                "weather_desc": data.get("weather", [{}])[0].get("description", "clear"),
            }
        elif response.status_code == 401:
            return {
                "status": "activating",
                "message": "OpenWeatherMap API key is activating (typically takes 10-30 mins after creation)",
                "temp_c": 24.0,
                "humidity_pct": 75.0,
                "wind_kmh": 12.0,
                "rainfall_mm": 20.0,
                "weather_desc": "key activating",
            }
        else:
            return {
                "status": "error",
                "message": f"API returned status {response.status_code}",
                "temp_c": 24.0,
                "humidity_pct": 75.0,
                "wind_kmh": 12.0,
                "rainfall_mm": 15.0,
                "weather_desc": "offline fallback",
            }
    except Exception as exc:
        return {
            "status": "offline",
            "message": f"Connection exception: {exc}",
            "temp_c": 24.0,
            "humidity_pct": 75.0,
            "wind_kmh": 12.0,
            "rainfall_mm": 15.0,
            "weather_desc": "offline fallback",
        }
