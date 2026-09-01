from backend.risk_engine import calculate_risk_score, risk_level


def test_weighted_score_uses_all_inputs():
    assert calculate_risk_score(1, 1, 1, 1) == 100
    assert calculate_risk_score(0, 0, 0, 0) == 0


def test_risk_level_boundaries():
    assert risk_level(39.99) == "Low"
    assert risk_level(40) == "Medium"
    assert risk_level(69.99) == "Medium"
    assert risk_level(70) == "High"
    assert risk_level(84.99) == "High"
    assert risk_level(85) == "Severe"
