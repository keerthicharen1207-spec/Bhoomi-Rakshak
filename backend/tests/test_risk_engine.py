from backend.risk_engine import RAINFALL_24H_MAX_MM, apply_rainfall, calculate_risk_score, risk_level


def test_weighted_score_uses_all_inputs():
    assert calculate_risk_score(1, 1, 1, 1) == 100
    assert calculate_risk_score(0, 0, 0, 0) == 0


def test_risk_level_boundaries():
    assert risk_level(29.99) == "Normal"
    assert risk_level(30) == "Watch"
    assert risk_level(49.99) == "Watch"
    assert risk_level(50) == "Warning"
    assert risk_level(74.99) == "Warning"
    assert risk_level(75) == "Evacuate"


def test_apply_rainfall_replaces_24h_and_rolls_7d():
    rain_24h, rain_7d = apply_rainfall(100.0, 0.70)
    assert rain_24h == 0.5
    assert rain_7d == round(0.70 * 6 / 7 + 0.5 / 7, 4)


def test_apply_rainfall_clamps_norms_to_one():
    rain_24h, rain_7d = apply_rainfall(RAINFALL_24H_MAX_MM * 3, 1.0)
    assert rain_24h == 1.0
    assert rain_7d == 1.0


def test_apply_rainfall_dry_day_rolls_window_down():
    rain_24h, rain_7d = apply_rainfall(0.0, 0.70)
    assert rain_24h == 0.0
    assert rain_7d == round(0.70 * 6 / 7, 4)
