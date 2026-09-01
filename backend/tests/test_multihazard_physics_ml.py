"""Tests for Physics Engine and Machine Learning Multi-Hazard Pipeline."""

from backend.physics_engine import (
    calculate_infinite_slope_fs,
    calculate_rational_peak_discharge,
    calculate_chandler_burning_index,
    evaluate_id_threshold_breach,
)
from backend.ml_engine import (
    train_all_models,
    predict_landslide_susceptibility,
    predict_flood_depth,
    predict_population_triage,
)
from backend.risk_engine import evaluate_multihazard_zone_risk


def test_physics_infinite_slope_fs():
    # Low slope should yield high FS
    fs_low = calculate_infinite_slope_fs(slope_deg=5.0, water_table_ratio=0.2)
    assert fs_low > 2.0

    # Steep slope under saturated conditions should yield lower FS
    fs_steep = calculate_infinite_slope_fs(slope_deg=42.0, water_table_ratio=1.0)
    assert fs_steep < 1.5


def test_physics_rational_peak_discharge():
    q = calculate_rational_peak_discharge(rainfall_intensity_mm_h=20.0, runoff_coefficient_c=0.7, catchment_area_ha=200.0)
    # Q = (0.7 * 20 * 200) / 360 = 7.78 m^3/s
    assert 7.0 <= q <= 8.5


def test_physics_wildfire_cbi():
    res = calculate_chandler_burning_index(temperature_c=35.0, relative_humidity_pct=25.0, wind_speed_kmh=20.0)
    assert "cbi_score" in res
    assert res["category"] in ["Low", "Moderate", "High", "Extreme"]


def test_physics_id_threshold():
    breach_low = evaluate_id_threshold_breach(rainfall_24h_mm=10.0)
    assert not breach_low["breached"]

    breach_high = evaluate_id_threshold_breach(rainfall_24h_mm=180.0)
    assert breach_high["breached"]


def test_ml_pipeline_training_and_inference():
    results = train_all_models()
    assert "landslide" in results
    assert "flood" in results
    assert "triage" in results

    ls_prob = predict_landslide_susceptibility({
        "slope_deg": 35.0,
        "elevation_m": 1200.0,
        "curvature": 0.01,
        "soil_ksat_mm_h": 5.0,
        "clay_pct": 35.0,
        "historical_density_norm": 0.8,
        "rainfall_24h_mm": 120.0,
        "rainfall_7d_mm": 350.0,
    })
    assert 0.0 <= ls_prob <= 1.0

    fl_depth = predict_flood_depth({
        "elevation_m": 120.0,
        "dist_to_river_m": 50.0,
        "catchment_area_ha": 500.0,
        "rainfall_24h_mm": 180.0,
        "rainfall_7d_mm": 400.0,
        "slope_deg": 2.0,
    })
    assert fl_depth >= 0.0

    triage = predict_population_triage({
        "pop_density_per_km2": 3500.0,
        "vulnerable_age_ratio": 0.35,
        "shelter_dist_km": 8.0,
        "landslide_susceptibility": ls_prob,
        "flood_depth_m": fl_depth,
        "housing_durability_idx": 0.3,
    })
    assert triage["triage_level"] in ["Low", "Moderate", "High", "Critical"]


def test_evaluate_multihazard_zone_risk():
    eval_res = evaluate_multihazard_zone_risk(
        slope_angle_norm=0.8,
        rainfall_24h_norm=0.7,
        rainfall_7d_norm=0.6,
        historical_density_norm=0.5,
    )
    assert "risk_score" in eval_res
    assert "physics" in eval_res
    assert "ml" in eval_res
    assert "factor_of_safety" in eval_res["physics"]
    assert "landslide_susceptibility" in eval_res["ml"]
