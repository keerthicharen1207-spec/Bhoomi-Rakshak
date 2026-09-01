"""Unified Multi-Hazard Risk Scoring & Physics-ML Hybrid Engine."""

from typing import Dict, Any, Optional
try:
    from .physics_engine import (
        calculate_infinite_slope_fs,
        calculate_rational_peak_discharge,
        calculate_chandler_burning_index,
        evaluate_id_threshold_breach,
        calculate_seismic_hazard,
        calculate_severe_storm_index,
    )
    from .ml_engine import (
        predict_landslide_susceptibility,
        predict_flood_depth,
        predict_population_triage,
    )
except (ImportError, ValueError):
    from physics_engine import (
        calculate_infinite_slope_fs,
        calculate_rational_peak_discharge,
        calculate_chandler_burning_index,
        evaluate_id_threshold_breach,
        calculate_seismic_hazard,
        calculate_severe_storm_index,
    )
    from ml_engine import (
        predict_landslide_susceptibility,
        predict_flood_depth,
        predict_population_triage,
    )

RAINFALL_24H_MAX_MM = 200.0
RAINFALL_7D_WINDOW_DAYS = 7


def calculate_risk_score(
    slope_angle_norm: float,
    rainfall_24h_norm: float,
    rainfall_7d_norm: float,
    historical_density_norm: float,
) -> float:
    """Return the weighted landslide risk score on a 0-100 scale."""
    score = 100 * (
        0.30 * slope_angle_norm
        + 0.35 * rainfall_24h_norm
        + 0.20 * rainfall_7d_norm
        + 0.15 * historical_density_norm
    )
    return round(score, 2)


def risk_level(score: float) -> str:
    """Map a score to the public standard 4-tier risk-level bands:
    - Normal:   0 - 29 (score < 30)
    - Watch:   30 - 49 (score < 50)
    - Warning: 50 - 74 (score < 75)
    - Evacuate:75 - 100 (score >= 75)
    """
    if score < 30:
        return "Normal"
    if score < 50:
        return "Watch"
    if score < 75:
        return "Warning"
    return "Evacuate"


def _dynamic_weather_multiplier(
    rain_24h_mm: float,
    rh_pct: float,
    temp_c: float,
    wind_kmh: float,
) -> float:
    """Dry, sunny weather should not keep India in a warning state without precipitation.

    A clear day with low rainfall, lower humidity, and mild-to-warm temperatures is treated as a
    low-risk baseline instead of carrying the full wet-season hazard load.
    """
    if rh_pct > 60.0 or temp_c < 18.0 or temp_c > 42.0 or wind_kmh > 35.0:
        return 1.0

    humidity_relief = max(0.0, (40.0 - rh_pct) / 40.0)
    temperature_relief = max(0.0, (35.0 - temp_c) / 15.0)
    wind_relief = max(0.0, (20.0 - wind_kmh) / 20.0)
    multiplier = 0.05 + 0.07 * humidity_relief + 0.06 * temperature_relief + 0.05 * wind_relief
    return min(0.15, max(0.05, multiplier))


def apply_rainfall(rainfall_mm: float, previous_7d_norm: float) -> tuple[float, float]:
    """Fold a new 24-hour rainfall observation into the zone's rainfall norms."""
    rain_24h = min(rainfall_mm / RAINFALL_24H_MAX_MM, 1.0)
    carried = previous_7d_norm * (RAINFALL_7D_WINDOW_DAYS - 1) / RAINFALL_7D_WINDOW_DAYS
    rain_7d = min(carried + rain_24h / RAINFALL_7D_WINDOW_DAYS, 1.0)
    return round(rain_24h, 4), round(rain_7d, 4)


def evaluate_multihazard_zone_risk(
    slope_angle_norm: float,
    rainfall_24h_norm: float,
    rainfall_7d_norm: float,
    historical_density_norm: float,
    elevation_m: float = 850.0,
    temp_c: float = 24.0,
    rh_pct: float = 75.0,
    wind_kmh: float = 12.0,
    pop_density: float = 850.0,
    state: str = "India",
    district_name: str = "",
    pga_g: Optional[float] = None,
) -> Dict[str, Any]:
    """Perform hybrid Physics + Machine Learning multi-hazard evaluation for a zone across all disaster classes."""

    # Dynamic weather calibration: a dry, sunny day in India should not carry the wet-season rainfall load.
    # Use live conditions to attenuate rainfall norms when the atmosphere is clear and low-moisture.
    if 18.0 <= temp_c <= 40.0 and rh_pct <= 60.0 and wind_kmh <= 25.0:
        rainfall_24h_norm *= 0.35
        rainfall_7d_norm *= 0.35

    # 1. Recompute basic weighted risk score
    weighted_score = calculate_risk_score(
        slope_angle_norm, rainfall_24h_norm, rainfall_7d_norm, historical_density_norm
    )
    base_level = risk_level(weighted_score)

    # Convert norms back to raw units for physical & ML inputs
    slope_deg = max(slope_angle_norm * 45.0, 2.0)
    rain_24h_mm = rainfall_24h_norm * RAINFALL_24H_MAX_MM
    rain_7d_mm = rainfall_7d_norm * RAINFALL_24H_MAX_MM * 7.0 / 2.0

    # 2. Physical engineering calculations
    water_table_ratio = min(0.05 + (rainfall_24h_norm * 0.65) + (rainfall_7d_norm * 0.30), 1.0)
    factor_of_safety = calculate_infinite_slope_fs(
        slope_deg=slope_deg,
        water_table_ratio=water_table_ratio,
    )
    intensity_mm_h = max(rain_24h_mm / 24.0, 0.5)
    flash_flood_q = calculate_rational_peak_discharge(
        rainfall_intensity_mm_h=intensity_mm_h,
    )
    wildfire_cbi = calculate_chandler_burning_index(
        temperature_c=temp_c,
        relative_humidity_pct=rh_pct,
        wind_speed_kmh=wind_kmh,
    )
    id_threshold = evaluate_id_threshold_breach(
        rainfall_24h_mm=rain_24h_mm,
    )
    seismic_info = calculate_seismic_hazard(
        state=state,
        slope_deg=slope_deg,
        district_name=district_name,
        pga_g=pga_g,
    )
    storm_info = calculate_severe_storm_index(
        wind_kmh=wind_kmh,
        rain_24h_mm=rain_24h_mm,
    )

    # 3. Machine Learning predictions
    ml_landslide_features = {
        "slope_deg": slope_deg,
        "elevation_m": elevation_m,
        "curvature": 0.005,
        "soil_ksat_mm_h": 12.5,
        "clay_pct": 25.0,
        "historical_density_norm": historical_density_norm,
        "rainfall_24h_mm": rain_24h_mm,
        "rainfall_7d_mm": rain_7d_mm,
    }
    landslide_susceptibility = predict_landslide_susceptibility(ml_landslide_features)

    ml_flood_features = {
        "elevation_m": elevation_m,
        "dist_to_river_m": 450.0,
        "catchment_area_ha": 250.0,
        "rainfall_24h_mm": rain_24h_mm,
        "rainfall_7d_mm": rain_7d_mm,
        "slope_deg": slope_deg,
    }
    flood_depth_m = predict_flood_depth(ml_flood_features)

    ml_triage_features = {
        "pop_density_per_km2": pop_density,
        "vulnerable_age_ratio": 0.22,
        "shelter_dist_km": 3.5,
        "landslide_susceptibility": landslide_susceptibility,
        "flood_depth_m": flood_depth_m,
        "housing_durability_idx": 0.65,
    }
    triage_info = predict_population_triage(ml_triage_features)

    # 4. Hybrid combined multi-hazard risk score
    # FS >= 1.5 is fully stable (0 risk), 1.0 <= FS < 1.5 is marginal, FS < 1.0 is failure
    if factor_of_safety >= 1.5:
        fs_risk_component = 0.0
    elif factor_of_safety >= 1.0:
        fs_risk_component = ((1.5 - factor_of_safety) / 0.5) * 50.0
    else:
        fs_risk_component = 50.0 + min(50.0, ((1.0 - factor_of_safety) / 0.5) * 50.0)

    ml_landslide_component = landslide_susceptibility * 100.0

    # Under dry clear weather (0mm rain), dry mountain slopes stay in Normal (0-29) / low Watch (30-35)
    # As live rain increases, score dynamically surges into Warning (50-74) and Evacuate (75+)
    weather_multiplier = _dynamic_weather_multiplier(rain_24h_mm, rh_pct, temp_c, wind_kmh)
    landslide_score = (0.50 * weighted_score) + (0.30 * fs_risk_component) + (0.20 * ml_landslide_component)
    landslide_score *= weather_multiplier
    flood_score = min(100.0, (flash_flood_q / 35.0) * 60.0 + (flood_depth_m / 3.0) * 40.0)
    flood_score *= weather_multiplier
    wildfire_score = wildfire_cbi["cbi_score"] * weather_multiplier
    seismic_score = seismic_info["coseismic_risk_score"]
    storm_score = storm_info["storm_score"] * weather_multiplier

    # Composite multi-hazard risk score
    max_hazard_score = max(landslide_score, flood_score, wildfire_score, seismic_score, storm_score)
    combined_score = round(max_hazard_score, 2)
    combined_level = risk_level(combined_score)

    # 5. Multi-Disaster Breakdown Suite
    disasters = {
        "landslide": {
            "name": "Landslide & Slope Collapse",
            "score": round(landslide_score, 1),
            "level": risk_level(landslide_score),
            "fs": factor_of_safety,
            "fs_status": "Unstable (Failure Expected)" if factor_of_safety < 1.0 else ("Marginal Stability" if factor_of_safety < 1.5 else "Stable Slope"),
            "probability_pct": round(landslide_susceptibility * 100),
            "id_breached": id_threshold["breached"],
            "id_ratio": id_threshold["breach_ratio"],
        },
        "flood": {
            "name": "Flash Flood & Inundation",
            "score": round(flood_score, 1),
            "level": risk_level(flood_score),
            "peak_discharge_m3s": flash_flood_q,
            "inundation_depth_m": flood_depth_m,
            "runoff_status": "Flash Inundation Warning" if flash_flood_q > 20.0 else ("Elevated Runoff" if flash_flood_q > 10.0 else "Normal Channel Flow"),
        },
        "wildfire": {
            "name": "Wildfire & Forest Fire",
            "score": round(wildfire_score, 1),
            "level": risk_level(wildfire_score),
            "cbi_score": round(wildfire_score, 1),
            "category": wildfire_cbi["category"],
            "rh_pct": rh_pct,
            "temp_c": temp_c,
        },
        "earthquake": {
            "name": "Seismic & Co-seismic Hazard",
            "score": seismic_info["coseismic_risk_score"],
            "level": "Evacuate" if seismic_info["zone_code"] == "Zone V" else ("Warning" if seismic_info["zone_code"] == "Zone IV" else "Watch"),
            "zone": seismic_info["zone_code"],
            "zone_factor_z": seismic_info["zone_factor_z"],
            "category": seismic_info["category"],
            "pga_g": seismic_info["pga_g"],
            "coseismic_risk_score": seismic_info["coseismic_risk_score"],
        },
        "storm": {
            "name": "Severe Storm & High Wind",
            "score": storm_info["storm_score"],
            "level": "Evacuate" if storm_info["storm_score"] >= 75 else ("Warning" if storm_info["storm_score"] >= 55 else ("Watch" if storm_info["storm_score"] >= 30 else "Normal")),
            "category": storm_info["category"],
            "wind_kmh": storm_info["wind_kmh"],
            "rain_24h_mm": storm_info["rain_24h_mm"],
        },
    }

    return {
        "risk_score": combined_score,
        "risk_level": combined_level,
        "weighted_score": weighted_score,
        "physics": {
            "factor_of_safety": factor_of_safety,
            "flash_flood_q_m3s": flash_flood_q,
            "wildfire_cbi": wildfire_cbi["cbi_score"],
            "wildfire_category": wildfire_cbi["category"],
            "id_threshold_breached": id_threshold["breached"],
            "id_breach_ratio": id_threshold["breach_ratio"],
        },
        "ml": {
            "landslide_susceptibility": landslide_susceptibility,
            "flood_depth_m": flood_depth_m,
            "population_triage_level": triage_info["triage_level"],
        },
        "disasters": disasters,
    }
