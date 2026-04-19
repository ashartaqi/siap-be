# Leagues for standings (excluding Champions League)
LEAGUE_CODES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
}

# All valid positions
VALID_PLAYER_POSITIONS = {
    "attacking": [
        "LW",
        "ST",
        "RW",
        "CF",
    ],
    "midfield": [
        "CAM",
        "LM",
        "RM",
        "CM",
        "CDM",
    ],
    "defense": [
        "LWB",
        "RWB",
        "LB",
        "RB",
        "CB",
        "GK",
    ],
}

# Match/Fixture Statuses
VALID_MATCH_STATUSES = [
    "SCHEDULED",
    "TIMED",
    "IN_PLAY",
    "PAUSED",
    "FINISHED",
    "POSTPONED",
    "SUSPENDED",
    "CANCELLED",
]


# Preferred foot
VALID_PREFERRED_FEET = ["Left", "Right"]

# Player stat limits
PLAYER_STAT_MIN = 1
PLAYER_STAT_MAX = 99
PLAYER_TOTAL_STATS_MAX = 570