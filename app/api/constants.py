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
        "id": "4-3-3",
        "label": "4-3-3",
        "description": "Barca 2015/Madrid 2017",
        "tacticalFit": "A",
        "rows": [["LW", "ST", "RW"], ["CM", "CM", "CM"], ["LB", "CB", "CB", "RB"]],
    },
    {
        "id": "4-4-2",
        "label": "4-4-2",
        "description": "Juve 2017",
        "tacticalFit": "A+",
        "rows": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"]],
    },
    {
        "id": "4-2-3-1",
        "label": "4-2-3-1",
        "description": "Inter 2010",
        "tacticalFit": "A-",
        "rows": [["ST"], ["LM", "CAM", "RM"], ["CDM", "CDM"], ["LB", "CB", "CB", "RB"]],
    },
    {
        "id": "3-5-2",
        "label": "3-5-2",
        "description": "Argentina 2022",
        "tacticalFit": "B",
        "rows": [["ST", "ST"], ["LM", "CM", "CDM", "CM", "RM"], ["CB", "CB", "CB"]],
    },
    {
        "id": "5-3-2",
        "label": "5-3-2",
        "description": "Haram Ball",
        "tacticalFit": "A-",
        "rows": [["ST", "ST"], ["CM", "CM", "CM"], ["LWB", "CB", "CB", "CB", "RWB"]],
    },
    {
        "id": "3-4-3",
        "label": "3-4-3",
        "description": "PSG 2020",
        "tacticalFit": "B+",
        "rows": [["LW", "ST", "RW"], ["LM", "CM", "CM", "RM"], ["CB", "CB", "CB"]],
    },
]
