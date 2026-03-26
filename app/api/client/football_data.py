import httpx
from app.core.config import settings


class FootballDataClient:
    """Client for football-data.org API v4.

    Docs: http://docs.football-data.org/general/v4/index.html
    Auth: X-Auth-Token header
    Base: https://api.football-data.org/v4/

    Resources: competitions, matches, teams, persons, areas
    """

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self):
        self.api_key = settings.FOOTBALL_DATA_API_KEY
        self.headers = {"X-Auth-Token": self.api_key}

    # ── Request client ──────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        resp = httpx.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Competitions ────────────────────────────────────────────────

    def get_competitions(self, params: dict | None = None) -> dict:
        """List all available competitions (filtered by plan/tier)."""
        return self.get("/competitions", params)

    def get_competition(self, code: str) -> dict:
        """Get a single competition by code (e.g. 'PL', 'CL', 'BL1')."""
        return self.get(f"/competitions/{code}")

    def get_competition_standings(self, code: str, params: dict | None = None) -> dict:
        """Get standings/league table for a competition.
        Params: season (int), matchday (int)
        """
        return self.get(f"/competitions/{code}/standings", params)

    def get_competition_matches(self, code: str, params: dict | None = None) -> dict:
        """Get matches for a competition.
        Params: dateFrom, dateTo, stage, status, matchday, group, season
        Status values: SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED,
                       POSTPONED, SUSPENDED, CANCELLED
        """
        return self.get(f"/competitions/{code}/matches", params)

    def get_competition_teams(self, code: str, params: dict | None = None) -> dict:
        """Get all teams in a competition.
        Params: season (int)
        """
        return self.get(f"/competitions/{code}/teams", params)

    def get_competition_scorers(self, code: str, params: dict | None = None) -> dict:
        """Get top scorers for a competition.
        Params: season (int), limit (int)
        """
        return self.get(f"/competitions/{code}/scorers", params)

    # ── Matches ─────────────────────────────────────────────────────

    def get_matches(self, params: dict | None = None) -> dict:
        """Get matches across all competitions (today by default).
        Params: competitions, dateFrom, dateTo, status, ids
        """
        return self.get("/matches", params)

    def get_match(self, match_id: int) -> dict:
        """Get a single match by ID."""
        return self.get(f"/matches/{match_id}")

    def get_head2head(self, match_id: int, params: dict | None = None) -> dict:
        """Get head-to-head stats for a match.
        Params: limit (int), dateFrom, dateTo
        """
        return self.get(f"/matches/{match_id}/head2head", params)

    # ── Teams ───────────────────────────────────────────────────────

    def get_team(self, team_id: int) -> dict:
        """Get a single team by ID (includes squad and coach)."""
        return self.get(f"/teams/{team_id}")

    def get_team_matches(self, team_id: int, params: dict | None = None) -> dict:
        """Get matches for a team.
        Params: dateFrom, dateTo, status, competitions, venue (HOME/AWAY), limit
        """
        return self.get(f"/teams/{team_id}/matches", params)

    # ── Persons (players, coaches, referees) ────────────────────────

    def get_person(self, person_id: int) -> dict:
        """Get a person by ID."""
        return self.get(f"/persons/{person_id}")

    def get_person_matches(self, person_id: int, params: dict | None = None) -> dict:
        """Get matches for a person.
        Params: dateFrom, dateTo, status, competitions, limit, offset
        """
        return self.get(f"/persons/{person_id}/matches", params)

    # ── Areas ───────────────────────────────────────────────────────

    def get_areas(self, params: dict | None = None) -> dict:
        """List all areas (countries/regions)."""
        return self.get("/areas", params)

    def get_area(self, area_id: int) -> dict:
        """Get a single area by ID."""
        return self.get(f"/areas/{area_id}")
