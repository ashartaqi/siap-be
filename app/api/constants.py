# Football Leagues
FIXTURE_LEAGUES = [
    {"key": "FL1", "label": "Ligue 1", "badge": "L1"},
    {"key": "SA", "label": "Serie A", "badge": "SA"},
    {"key": "PL", "label": "Premier League", "badge": "PL"},
    {"key": "PPL", "label": "Primeira Liga", "badge": "PPL"},
    {"key": "PD", "label": "La Liga", "badge": "LL"},
    {"key": "BL1", "label": "Bundesliga", "badge": "BL1"},
    {"key": "CL", "label": "Champions League", "badge": "CL"},
]

# Player Positions

VALID_PLAYER_POSITIONS = {
    "attacking": ["LW", "ST", "RW", "CF", "LF", "RF", "SS"],
    "midfield": ["CM", "CAM", "CDM", "LM", "RM", "DM", "AM"],
    "defense": ["CB", "LB", "RB", "LWB", "RWB", "SW", "GK"],
}
# Match/Fixture Statuses

VALID_MATCH_STATUSES = [
    "SCHEDULED", "TIMED", "IN_PLAY", "PAUSED", "FINISHED",
    "POSTPONED", "SUSPENDED", "CANCELLED",
]

# Preferred Foot

VALID_PREFERRED_FEET = ["Left", "Right"]

# Player Stat Limits
PLAYER_STAT_MIN = 1
PLAYER_STAT_MAX = 99
PLAYER_TOTAL_STATS_MAX = 570
PLAYER_STATS = {
    "total": PLAYER_TOTAL_STATS_MAX,
    "min": PLAYER_STAT_MIN,
    "max": PLAYER_STAT_MAX,
}

# Formations
FORMATIONS = [
    {
        "id": "4-4-2",
        "label": "4-4-2",
        "description": "Classic Balance",
        "tacticalFit": "A+",
        "rows": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"]],
    },
    {
        "id": "4-3-3",
        "label": "4-3-3",
        "description": "Offensive Width",
        "tacticalFit": "A",
        "rows": [["LW", "ST", "RW"], ["CM", "CM", "CM"], ["LB", "CB", "CB", "RB"]],
    },
    {
        "id": "3-4-3",
        "label": "3-4-3",
        "description": "Midfield Control",
        "tacticalFit": "B+",
        "rows": [["LW", "ST", "RW"], ["LM", "CM", "CM", "RM"], ["CB", "CB", "CB"]],
    },
    {
        "id": "4-2-2-2",
        "label": "4-2-2-2",
        "description": "Tactical Pivot",
        "tacticalFit": "A-",
        "rows": [["ST", "ST"], ["AM", "AM"], ["DM", "DM"], ["LB", "CB", "CB", "RB"]],
    },
]
