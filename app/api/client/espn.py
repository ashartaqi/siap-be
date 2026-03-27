import httpx


class ESPNSoccerClient:
    CORE_BASE = "https://sports.core.api.espn.com/v2/sports/soccer"
    CORE_V3_BASE = "https://sports.core.api.espn.com/v3/sports/soccer"
    SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

    # Core API v2
    calendar = "/calendar"
    seasons = "/seasons"
    athletes_by_season = "/seasons/{season}/athletes"
    draft = "/seasons/{season}/draft"
    free_agents = "/seasons/{season}/freeagents"
    teams = "/teams"
    athletes = "/athletes"
    events = "/events"
    event = "/events/{event}"
    competition = "/events/{event}/competitions/{competition}"
    broadcasts = "/events/{event}/competitions/{competition}/broadcasts"
    competitor = "/events/{event}/competitions/{competition}/competitors/{competitor}"
    competition_odds = "/events/{event}/competitions/{competition}/odds"
    officials = "/events/{event}/competitions/{competition}/officials"
    plays = "/events/{event}/competitions/{competition}/plays"
    situation = "/events/{event}/competitions/{competition}/situation"
    probabilities = "/events/{event}/competitions/{competition}/probabilities"
    standings = "/standings"
    rankings = "/rankings"
    venues = "/venues"
    media = "/media"
    countries = "/countries"
    franchises = "/franchises"
    positions = "/positions"
    current_season = "/season"
    tournaments = "/tournaments"
    leaders = "/leaders"
    season_leaders = "/seasons/{season}/leaders"

    # Site API
    scoreboard = "/scoreboard"
    site_teams = "/teams"
    site_team = "/teams/{team_id}"
    roster = "/teams/{team_id}/roster"
    injuries = "/teams/{team_id}/injuries"
    schedule = "/teams/{team_id}/schedule"
    site_standings = "/standings"
    news = "/news"
    summary = "/summary"

    # Core API v3
    v3_league = ""
    v3_athletes = "/athletes"
    v3_season = "/seasons/{season}"

    def __init__(self, league: str = "eng.1"):
        self.league = league


    # Request helpers
    def get(self, url: str, params: dict | None = None) -> dict:
        resp = httpx.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _core_url(self, path: str) -> str:
        return f"{self.CORE_BASE}/leagues/{self.league}{path}"

    def _site_url(self, path: str) -> str:
        return f"{self.SITE_BASE}/{self.league}{path}"

    def _v3_url(self, path: str) -> str:
        return f"{self.CORE_V3_BASE}/{self.league}{path}"


    # Seasons & Calendar
    def get_calendar(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.calendar), params)

    def get_seasons(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.seasons), params)

    def get_athletes_by_season(self, season: int, params: dict | None = None) -> dict:
        path = self.athletes_by_season.format(season=season)
        return self.get(self._core_url(path), params)

    def get_draft(self, season: int, params: dict | None = None) -> dict:
        path = self.draft.format(season=season)
        return self.get(self._core_url(path), params)

    def get_free_agents(self, season: int, params: dict | None = None) -> dict:
        path = self.free_agents.format(season=season)
        return self.get(self._core_url(path), params)


    # Teams
    def get_teams(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.teams), params)


    # Athletes / Players
    def get_athletes(self, params: dict | None = None) -> list:
        data = self.get(self._core_url(self.athletes), params)

        athletes = []

        for item in data.get("items", []):
            ref_url = item.get("$ref")

            if ref_url:
                athlete_data = self.get(ref_url)
                athletes.append(athlete_data)

        return athletes

    # Events / Games
    def get_events(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.events), params)

    def get_event(self, event: str, params: dict | None = None) -> dict:
        path = self.event.format(event=event)
        return self.get(self._core_url(path), params)

    def get_competition(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.competition.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_broadcasts(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.broadcasts.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_competitor(self, event: str, competition: str, competitor: str, params: dict | None = None) -> dict:
        path = self.competitor.format(event=event, competition=competition, competitor=competitor)
        return self.get(self._core_url(path), params)

    def get_competition_odds(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.competition_odds.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_officials(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.officials.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_plays(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.plays.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_situation(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.situation.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)

    def get_probabilities(self, event: str, competition: str, params: dict | None = None) -> dict:
        path = self.probabilities.format(event=event, competition=competition)
        return self.get(self._core_url(path), params)


    # Standings / Rankings / Venues
    def get_standings(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.standings), params)

    def get_rankings(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.rankings), params)

    def get_venues(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.venues), params)


    # News & Media
    def get_media(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.media), params)


    # Other (Core API)
    def get_countries(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.countries), params)

    def get_franchises(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.franchises), params)

    def get_positions(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.positions), params)

    def get_current_season(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.current_season), params)

    def get_tournaments(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.tournaments), params)

    def get_leaders(self, params: dict | None = None) -> dict:
        return self.get(self._core_url(self.leaders), params)

    def get_season_leaders(self, season: int, params: dict | None = None) -> dict:
        path = self.season_leaders.format(season=season)
        return self.get(self._core_url(path), params)


    # Site API
    def get_scoreboard(self, params: dict | None = None) -> dict:
        return self.get(self._site_url(self.scoreboard), params)

    def get_site_teams(self, params: dict | None = None) -> dict:
        return self.get(self._site_url(self.site_teams), params)

    def get_site_team(self, team_id: int, params: dict | None = None) -> dict:
        path = self.site_team.format(team_id=team_id)
        return self.get(self._site_url(path), params)

    def get_roster(self, team_id: int, params: dict | None = None) -> dict:
        path = self.roster.format(team_id=team_id)
        return self.get(self._site_url(path), params)

    def get_injuries(self, team_id: int, params: dict | None = None) -> dict:
        path = self.injuries.format(team_id=team_id)
        return self.get(self._site_url(path), params)

    def get_schedule(self, team_id: int, params: dict | None = None) -> dict:
        path = self.schedule.format(team_id=team_id)
        return self.get(self._site_url(path), params)

    def get_site_standings(self, params: dict | None = None) -> dict:
        return self.get(self._site_url(self.site_standings), params)

    def get_news(self, params: dict | None = None) -> dict:
        return self.get(self._site_url(self.news), params)

    def get_summary(self, event_id: str, params: dict | None = None) -> dict:
        params = params or {}
        params["event"] = event_id
        return self.get(self._site_url(self.summary), params)


    # Core API v3
    def get_v3_league(self, params: dict | None = None) -> dict:
        return self.get(self._v3_url(self.v3_league), params)

    def get_v3_athletes(self, params: dict | None = None) -> dict:
        return self.get(self._v3_url(self.v3_athletes), params)

    def get_v3_season(self, season: int, params: dict | None = None) -> dict:
        path = self.v3_season.format(season=season)
        return self.get(self._v3_url(path), params)
