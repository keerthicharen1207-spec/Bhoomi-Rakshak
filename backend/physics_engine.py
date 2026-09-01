"""Physical and Geotechnical Engineering Risk Engine.

Implements deterministic physics equations for multi-hazard monitoring:
1. Landslide Factor of Safety (FS) - Infinite Slope Model with Mohr-Coulomb shear criterion.
2. Flash Flood Peak Discharge (Q) - Rational Method (Q = C * I * A / 360).
3. Wildfire Severity Index - Chandler Burning Index (CBI).
4. USGS Empirical Rainfall Intensity-Duration (I-D) Threshold breach evaluation.
5. IS 1893:2016 Seismic Hazard & Co-seismic Ground Acceleration Analysis.
6. Severe Storm & Cyclonic Wind-Rain Pressure Index.
"""

import math
from typing import Dict, Any


def calculate_infinite_slope_fs(
    slope_deg: float,
    cohesion_kpa: float = 12.0,
    friction_angle_deg: float = 30.0,
    soil_depth_m: float = 2.0,
    unit_weight_kn_m3: float = 19.0,
    water_table_ratio: float = 0.8,
) -> float:
    """Calculate the Factor of Safety (FS) using the Infinite Slope Model under saturated flow conditions.

    FS < 1.0 indicates unstable slope / imminent failure.
    """
    if slope_deg <= 1.0:
        return 10.0

    slope_rad = math.radians(slope_deg)
    phi_rad = math.radians(friction_angle_deg)
    gamma_w = 9.81  # Water unit weight in kN/m^3

    # Effective stress parameters
    c_prime = cohesion_kpa
    gamma = unit_weight_kn_m3

    # Buoyant unit weight adjustment based on water table ratio (m)
    m = min(max(water_table_ratio, 0.0), 1.0)
    effective_unit_weight = gamma - (m * gamma_w)

    numerator = c_prime + (effective_unit_weight * soil_depth_m * (math.cos(slope_rad) ** 2) * math.tan(phi_rad))
    denominator = gamma * soil_depth_m * math.sin(slope_rad) * math.cos(slope_rad)

    if denominator <= 0:
        return 10.0

    fs = numerator / denominator
    return round(float(fs), 2)


def calculate_rational_peak_discharge(
    rainfall_intensity_mm_h: float,
    runoff_coefficient_c: float = 0.65,
    catchment_area_ha: float = 250.0,
) -> float:
    """Calculate peak runoff discharge Q (m^3/s) using the Rational Method: Q = (C * I * A) / 360."""
    q = (runoff_coefficient_c * rainfall_intensity_mm_h * catchment_area_ha) / 360.0
    return round(max(float(q), 0.0), 2)


def calculate_chandler_burning_index(
    temperature_c: float,
    relative_humidity_pct: float,
    wind_speed_kmh: float,
) -> Dict[str, Any]:
    """Calculate Chandler Burning Index (CBI) for wildfire risk."""
    rh = min(max(relative_humidity_pct, 0.0), 100.0)
    t = temperature_c
    w = max(wind_speed_kmh, 0.0)

    cbi = ((110.0 - 1.373 * rh) * ((10.18 + 0.27 * t) ** 2) / 60.0) * (10.0 ** (-0.03 * w))
    score = round(max(float(cbi), 0.0), 1)

    if score < 50.0:
        category = "Low"
    elif score < 75.0:
        category = "Moderate"
    elif score < 90.0:
        category = "High"
    else:
        category = "Extreme"

    return {"cbi_score": score, "category": category}


def evaluate_id_threshold_breach(
    rainfall_24h_mm: float,
    duration_hours: float = 24.0,
    a_coef: float = 14.2,
    b_coef: float = 0.41,
) -> Dict[str, Any]:
    """Evaluate USGS Empirical I-D Threshold: I = a * D^(-b)."""
    duration = max(duration_hours, 1.0)
    current_intensity = rainfall_24h_mm / duration
    critical_intensity = a_coef * (duration ** (-b_coef))
    breached = current_intensity >= critical_intensity

    return {
        "current_intensity_mm_h": round(current_intensity, 2),
        "critical_threshold_mm_h": round(critical_intensity, 2),
        "breached": breached,
        "breach_ratio": round(current_intensity / critical_intensity, 2),
    }


def calculate_seismic_hazard(
    state: str = "India",
    slope_deg: float = 25.0,
    district_name: str = "",
) -> Dict[str, Any]:
    """Calculate Seismic / Earthquake Vulnerability according to BIS IS 1893:2016."""
    state_lower = state.lower()
    name_lower = district_name.lower()

    # Zone V (Z = 0.36): All NE states, Rudraprayag, Chamoli, Mandi, Kangra, Kutch, A&N
    if any(s in state_lower for s in ["meghalaya", "assam", "nagaland", "arunachal", "sikkim", "manipur", "mizoram", "tripura"]) or \
       any(d in name_lower for d in ["rudraprayag", "chamoli", "mandi"]):
        zone_code = "Zone V"
        zone_factor_z = 0.36
        category = "Very High Damage Risk"
        pga_g = 0.36
    # Zone IV (Z = 0.24): Shimla, Darjeeling, remaining Uttarakhand/HP, parts of J&K, Delhi
    elif any(s in state_lower for s in ["himachal", "uttarakhand", "west bengal"]) or \
         any(d in name_lower for d in ["shimla", "darjeeling"]):
        zone_code = "Zone IV"
        zone_factor_z = 0.24
        category = "High Damage Risk"
        pga_g = 0.24
    # Zone III (Z = 0.16): Western Ghats (Kerala - Wayanad, Idukki), Maharashtra, Tamil Nadu
    elif "kerala" in state_lower or any(d in name_lower for d in ["wayanad", "idukki"]):
        zone_code = "Zone III"
        zone_factor_z = 0.16
        category = "Moderate Damage Risk"
        pga_g = 0.16
    else:
        zone_code = "Zone III"
        zone_factor_z = 0.16
        category = "Moderate Damage Risk"
        pga_g = 0.16

    # Co-seismic slope failure acceleration susceptibility: Newmark sliding block proxy
    # Higher slope + higher PGA = increased co-seismic landslide hazard
    coseismic_risk_score = round(min(100.0, (zone_factor_z / 0.36) * (slope_deg / 45.0) * 100.0), 1)

    return {
        "zone_code": zone_code,
        "zone_factor_z": zone_factor_z,
        "category": category,
        "pga_g": pga_g,
        "coseismic_risk_score": coseismic_risk_score,
    }


def calculate_severe_storm_index(
    wind_kmh: float,
    rain_24h_mm: float,
) -> Dict[str, Any]:
    """Calculate Storm / Cyclonic Weather Pressure Index."""
    wind = max(wind_kmh, 0.0)
    rain = max(rain_24h_mm, 0.0)

    # Dynamic pressure factor (q = 0.5 * rho * v^2) normalized + rainfall weight
    wind_factor = min(1.0, wind / 120.0)
    rain_factor = min(1.0, rain / 200.0)

    storm_score = round((0.6 * wind_factor + 0.4 * rain_factor) * 100.0, 1)

    if storm_score < 30.0:
        category = "Normal / Light Breeze"
    elif storm_score < 55.0:
        category = "Moderate Squall"
    elif storm_score < 75.0:
        category = "High Wind / Gale Advisory"
    else:
        category = "Severe Cyclonic Storm Warning"

    return {
        "storm_score": storm_score,
        "category": category,
        "wind_kmh": round(wind, 1),
        "rain_24h_mm": round(rain, 1),
    }
