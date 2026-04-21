# ─── Football Leagues ─────────────────────────────────────────────────────────

LEAGUE_CODES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
}

FIXTURE_LEAGUES = [
    {"key": "FL1", "label": "Ligue 1", "badge": "L1"},
    {"key": "SA", "label": "Serie A", "badge": "SA"},
    {"key": "PL", "label": "Premier League", "badge": "PL"},
    {"key": "PPL", "label": "Primeira Liga", "badge": "PPL"},
    {"key": "PD", "label": "La Liga", "badge": "LL"},
    {"key": "BL1", "label": "Bundesliga", "badge": "BL1"},
    {"key": "CL", "label": "Champions League", "badge": "CL"},
]

STANDING_LEAGUES = [
    {"key": "PL", "label": "Premier League", "badge": "PL"},
    {"key": "PD", "label": "La Liga", "badge": "LL"},
    {"key": "SA", "label": "Serie A", "badge": "SA"},
    {"key": "BL1", "label": "Bundesliga", "badge": "BL1"},
    {"key": "FL1", "label": "Ligue 1", "badge": "L1"},
]

# ─── Player Positions ─────────────────────────────────────────────────────────

VALID_PLAYER_POSITIONS = {
    "attacking": ["LW", "ST", "RW", "CF", "LF", "RF", "SS"],
    "midfield": ["CM", "CAM", "CDM", "LM", "RM", "DM", "AM"],
    "defense": ["CB", "LB", "RB", "LWB", "RWB", "SW", "GK"],
}

ALL_POSITIONS = [
    "ST", "CF", "LW", "RW", "LF", "RF", "SS",
    "CM", "CAM", "CDM", "LM", "RM", "DM", "AM",
    "CB", "LB", "RB", "LWB", "RWB", "SW",
]

# ─── Countries ────────────────────────────────────────────────────────────────

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
    "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon",
    "Canada", "Central African Republic", "Chad", "Chile", "China",
    "Colombia", "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba",
    "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia",
    "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
    "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India",
    "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica",
    "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait",
    "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia",
    "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
    "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands",
    "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger",
    "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman",
    "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea",
    "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
    "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia",
    "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden",
    "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand",
    "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia",
    "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
    "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
    "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam",
    "Yemen", "Zambia", "Zimbabwe",
]

# ─── Match/Fixture Statuses ───────────────────────────────────────────────────

VALID_MATCH_STATUSES = [
    "SCHEDULED", "TIMED", "IN_PLAY", "PAUSED", "FINISHED",
    "POSTPONED", "SUSPENDED", "CANCELLED",
]

# ─── Preferred Foot ───────────────────────────────────────────────────────────

VALID_PREFERRED_FEET = ["Left", "Right"]

# ─── Player Stat Limits ───────────────────────────────────────────────────────

PLAYER_STAT_MIN = 1
PLAYER_STAT_MAX = 99
PLAYER_TOTAL_STATS_MAX = 570

# ─── Stat Field Map ───────────────────────────────────────────────────────────

STAT_FIELD_MAP = {
    "pace": "pace",
    "shooting": "shooting",
    "passing": "passing",
    "dribbling": "dribbling",
    "defending": "defending",
    "physic": "physic",
}

# ─── Default Player Values ────────────────────────────────────────────────────

DEFAULT_IDENTITY = {
    "name": "Your Player",
    "position": "ST",
    "nationality": "---",
    "shirt_number": 7,
    "preferred_foot": "Right",
}

DEFAULT_STATS = {
    "pace": 0,
    "shooting": 0,
    "passing": 0,
    "dribbling": 0,
    "defending": 0,
    "physic": 0,
}

# ─── Formations ───────────────────────────────────────────────────────────────

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

# ─── Season ───────────────────────────────────────────────────────────────────

CURRENT_SEASON = "2025/26"