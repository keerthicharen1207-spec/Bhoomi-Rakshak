"""Incident reports submitted by citizens and field officials."""

STATUS_BY_SOURCE = {
    "citizen": "pending",
    "field_official": "verified",
}


def status_for(source: str) -> str:
    """Determine initial status based on reporter source."""
    return STATUS_BY_SOURCE.get(source, "pending")
