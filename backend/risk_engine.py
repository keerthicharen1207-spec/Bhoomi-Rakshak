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
    water_table_ratio = min(0.3 + (rainfall_24h_norm * 0.7), 1.0)
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
    fs_risk_component = max(0.0, min(1.0, (2.0 - factor_of_safety) / 1.0)) * 100.0
    ml_landslide_component = landslide_susceptibility * 100.0

    landslide_score = (0.50 * weighted_score) + (0.25 * fs_risk_component) + (0.25 * ml_landslide_component)
    flood_score = min(100.0, (flash_flood_q / 35.0) * 60.0 + (flood_depth_m / 3.0) * 40.0)
    wildfire_score = wildfire_cbi["cbi_score"]
    seismic_score = seismic_info["coseismic_risk_score"]
    storm_score = storm_info["storm_score"]

    # Composite multi-hazard risk score incorporates any extreme localized hazards
    max_hazard_score = max(landslide_score, flood_score, wildfire_score, seismic_score, storm_score)
    combined_score = round(max(landslide_score, (0.55 * max_hazard_score + 0.45 * landslide_score)), 2)
    combined_level = risk_level(combined_score)

    # 5. Multi-Disaster Breakdown Suite
    disasters = {
        "landslide": {
            "name": "Landslide & Slope Collapse",
            "score": combined_score,
            "level": combined_level,
            "fs": factor_of_safety,
            "fs_status": "Unstable (Failure Expected)" if factor_of_safety < 1.0 else ("Marginal Stability" if factor_of_safety < 1.5 else "Stable Slope"),
            "probability_pct": round(landslide_susceptibility * 100),
            "id_breached": id_threshold["breached"],
            "id_ratio": id_threshold["breach_ratio"],
        },
        "flood": {
            "name": "Flash Flood & Inundation",
            "score": round(min(100.0, (flash_flood_q / 35.0) * 60.0 + (flood_depth_m / 3.0) * 40.0), 1),
            "level": "Evacuate" if flood_depth_m > 2.0 else ("Warning" if flood_depth_m > 1.0 else ("Watch" if flood_depth_m > 0.4 else "Normal")),
            "peak_discharge_m3s": flash_flood_q,
            "inundation_depth_m": flood_depth_m,
            "runoff_status": "Flash Inundation Warning" if flash_flood_q > 20.0 else ("Elevated Runoff" if flash_flood_q > 10.0 else "Normal Channel Flow"),
        },
        "wildfire": {
            "name": "Wildfire & Forest Fire",
            "score": wildfire_cbi["cbi_score"],
            "level": wildfire_cbi["category"],
            "cbi_score": wildfire_cbi["cbi_score"],
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
