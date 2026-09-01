"""Alert generation for zone risk threshold crossings."""

SEVERITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Severe": 3}
ALERT_LEVELS = ("High", "Severe")

ZONE_ROADS = {
    "Sohra": "NH6",
    "Jowai": "NH44",
    "Haflong": "NH27",
    "Kohima": "NH2",
    "Dimapur": "NH29",
}

COMMUNITY_TEMPLATES = {
    "High": {
        "en": "Avoid {road} near {zone} — high landslide risk.",
        "as": "{zone}ৰ কাষৰ {road} এৰক — মাটি ভাঙি পৰাৰ উচ্চ সম্ভাৱনা।",
        "nl": "{road} baru {zone} erekho — pahar bhangibo pare.",
    },
    "Severe": {
        "en": "Severe landslide risk near {zone}. Leave the {road} area now.",
        "as": "{zone}ৰ ওচৰত মাটি ভাঙি পৰাৰ গুৰুতৰ বিপদ — {road}ৰ এলেকা এতিয়াই এৰক।",
        "nl": "{zone} lagan pahar khub bhangibo pare — {road} area ekhon sobi erekho.",
    },
}


def should_alert(previous_level: str, current_level: str) -> bool:
    """Fire only when a zone escalates into the High or Severe band."""
    return (
        current_level in ALERT_LEVELS
        and SEVERITY_ORDER[current_level] > SEVERITY_ORDER[previous_level]
    )


def build_messages(zone, level: str, score: float, previous_score: float) -> dict:
    """Return the authority rendering and per-language community renderings."""
    road = ZONE_ROADS.get(zone["name"], "the highway")
    community = {
        language: template.format(road=road, zone=zone["name"])
        for language, template in COMMUNITY_TEMPLATES[level].items()
    }
    authority = (
        f"{level.upper()} landslide risk — {zone['name']} zone "
        f"({zone['lat']:.2f}N, {zone['lng']:.2f}E). "
        f"Risk score {score:.1f}/100, up from {previous_score:.1f}. "
        f"Drivers: 24h rainfall at {zone['rainfall_24h_norm'] * 100:.0f}% of the extreme benchmark, "
        f"7-day rainfall {zone['rainfall_7d_norm'] * 100:.0f}%, "
        f"slope angle {zone['slope_angle_norm'] * 100:.0f}%, "
        f"historical incident density {zone['historical_density_norm'] * 100:.0f}%. "
        f"Recommended: deploy field inspection along {road}, notify the district EOC."
    )
    return {"authority": authority, "community": community}
