"""Risk scoring rules for NER monitoring zones."""

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
    """Map a score to the public risk-level bands."""
    if score < 40:
        return "Low"
    if score < 70:
        return "Medium"
    if score < 85:
        return "High"
    return "Severe"


def apply_rainfall(rainfall_mm: float, previous_7d_norm: float) -> tuple[float, float]:
    """Fold a new 24-hour rainfall observation into the zone's rainfall norms.

    The reading replaces rainfall_24h_norm and enters the trailing 7-day
    window weighted 1/7, with the oldest day falling out.
    """
    rain_24h = min(rainfall_mm / RAINFALL_24H_MAX_MM, 1.0)
    carried = previous_7d_norm * (RAINFALL_7D_WINDOW_DAYS - 1) / RAINFALL_7D_WINDOW_DAYS
    rain_7d = min(carried + rain_24h / RAINFALL_7D_WINDOW_DAYS, 1.0)
    return round(rain_24h, 4), round(rain_7d, 4)
