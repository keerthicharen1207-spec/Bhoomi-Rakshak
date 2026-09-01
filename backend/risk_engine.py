"""Risk scoring rules for NER monitoring zones."""


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
    """Map a score to the public risk-level bands."""
    if score < 40:
        return "Low"
    if score < 70:
        return "Medium"
    if score < 85:
        return "High"
    return "Severe"
