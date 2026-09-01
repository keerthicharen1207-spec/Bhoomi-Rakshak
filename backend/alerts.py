"""Alert generation for zone risk threshold crossings."""

from datetime import datetime, timezone

SEVERITY_ORDER = {"Normal": 0, "Watch": 1, "Warning": 2, "Evacuate": 3}
ALERT_LEVELS = ("Warning", "Evacuate")

ZONE_ROADS = {
    "East Khasi Hills (Sohra)": "NH6",
    "West Jaintia Hills (Jowai)": "NH44",
    "Dima Hasao (Haflong)": "NH27",
    "Kohima District": "NH2",
    "Dimapur District": "NH29",
    "Wayanad District": "NH766",
    "Chamoli District": "NH7",
    "Shimla District": "NH5",
    "Darjeeling District": "NH110",
    "East Sikkim (Gangtok)": "NH10",
    "Papum Pare (Itanagar)": "NH415",
    "Idukki District": "NH85",
    "Mandi District": "NH3",
    "Rudraprayag District": "NH107",
    # Legacy fallbacks
    "Sohra": "NH6",
    "Jowai": "NH44",
    "Haflong": "NH27",
}

COMMUNITY_TEMPLATES = {
    "Warning": {
        "en": "Avoid {road} near {zone} — high landslide risk.",
        "as": "{zone}ৰ কাষৰ {road} এৰক — মাটি ভাঙি পৰাৰ উচ্চ সম্ভাৱনা।",
        "nl": "{road} baru {zone} erekho — pahar bhangibo pare.",
    },
    "Evacuate": {
        "en": "Severe landslide risk near {zone}. Leave the {road} area now.",
        "as": "{zone}ৰ ওচৰত মাটি ভাঙি পৰাৰ গুৰুতৰ বিপদ — {road}ৰ এলেকা এতিয়াই এৰক।",
        "nl": "{zone} lagan pahar khub bhangibo pare — {road} area ekhon sobi erekho.",
    },
}

# Zone ID to last alert timestamp dict to implement cooldown
last_alert_time = {}

def should_alert(zone_id: int, previous_level: str, current_level: str) -> bool:
    """Fire only when a zone escalates into the Warning or Evacuate band, with 15min cooldown."""
    if current_level not in ALERT_LEVELS:
        return False
        
    if SEVERITY_ORDER.get(current_level, 0) <= SEVERITY_ORDER.get(previous_level, 0):
        return False

    now = datetime.now(timezone.utc).timestamp()
    last = last_alert_time.get(zone_id, 0)
    
    # 15 minute (900 seconds) cooldown
    if (now - last) < 900:
        return False
        
    last_alert_time[zone_id] = now
    return True


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
