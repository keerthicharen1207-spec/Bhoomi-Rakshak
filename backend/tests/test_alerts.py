from backend.alerts import build_messages, should_alert


def test_should_alert_fires_on_escalation_into_warning_band():
    assert should_alert("Low", "High")
    assert should_alert("Medium", "High")
    assert should_alert("High", "Severe")
    assert should_alert("Medium", "Severe")


def test_should_alert_stays_quiet_without_escalation():
    assert not should_alert("High", "High")
    assert not should_alert("Severe", "Severe")
    assert not should_alert("Severe", "High")
    assert not should_alert("Medium", "Medium")
    assert not should_alert("High", "Medium")
    assert not should_alert("Low", "Medium")


def test_build_messages_renders_authority_and_three_languages():
    zone = {
        "name": "Sohra",
        "lat": 25.27,
        "lng": 91.73,
        "rainfall_24h_norm": 1.0,
        "rainfall_7d_norm": 0.5,
        "slope_angle_norm": 0.82,
        "historical_density_norm": 0.68,
    }

    messages = build_messages(zone, "High", 79.9, 51.95)

    assert "Sohra" in messages["authority"]
    assert "NH6" in messages["authority"]
    assert "79.9" in messages["authority"]
    assert set(messages["community"]) == {"en", "as", "nl"}
    assert "NH6" in messages["community"]["en"]
    assert "Sohra" in messages["community"]["as"]
