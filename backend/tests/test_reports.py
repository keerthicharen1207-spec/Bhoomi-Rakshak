from backend.reports import status_for


def test_citizen_reports_start_pending():
    assert status_for("citizen") == "pending"


def test_field_official_reports_are_auto_verified():
    assert status_for("field_official") == "verified"
