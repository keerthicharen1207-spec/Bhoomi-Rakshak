from backend.alerts import build_messages, should_alert, last_alert_time


def test_should_alert_fires_on_escalation_into_warning_band():
    last_alert_time.clear()
    assert should_alert(1, "Normal", "Warning")
    assert should_alert(2, "Watch", "Warning")
    assert should_alert(3, "Warning", "Evacuate")
    assert should_alert(4, "Watch", "Evacuate")


def test_should_alert_stays_quiet_without_escalation():
    last_alert_time.clear()
    assert not should_alert(1, "Warning", "Warning")
    assert not should_alert(2, "Evacuate", "Evacuate")
    assert not should_alert(3, "Evacuate", "Warning")
    assert not should_alert(4, "Watch", "Watch")
    assert not should_alert(5, "Warning", "Watch")
    assert not should_alert(6, "Normal", "Watch")


def test_should_alert_respects_cooldown():
    last_alert_time.clear()
    assert should_alert(1, "Normal", "Warning")
    # Immediate second call for same zone is blocked by 15min cooldown
    assert not should_alert(1, "Warning", "Evacuate")
    # Different zone is allowed
    assert should_alert(2, "Watch", "Evacuate")


def test_build_messages_renders_authority_and_three_languages():
    zone = {
        "name": "East Khasi Hills (Sohra)",
        "lat": 25.27,
        "lng": 91.73,
        "rainfall_24h_norm": 1.0,
        "rainfall_7d_norm": 0.5,
        "slope_angle_norm": 0.82,
        "historical_density_norm": 0.68,
    }

    messages = build_messages(zone, "Warning", 79.9, 51.95)

    assert "East Khasi Hills (Sohra)" in messages["authority"]
    assert "NH6" in messages["authority"]
    assert "79.9" in messages["authority"]
    assert set(messages["community"]) == {"en", "as", "nl"}
    assert "NH6" in messages["community"]["en"]
    assert "East Khasi Hills (Sohra)" in messages["community"]["as"]

