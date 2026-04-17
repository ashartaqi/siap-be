from app.core.db import SessionLocal
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.api.client.football_data import FootballDataClient
from app.models import Fixtures, LeagueStandings
from datetime import timedelta, datetime


async def update_fixtures():
    db = SessionLocal()
    client = FootballDataClient()

    ids = db.query(Fixtures.id).filter(Fixtures.status != "FINISHED").all()
    ids = [i[0] for i in ids]

    matches = client.get_matches({
        "ids": ",".join(str(i) for i in ids)
    })
    matches = matches.get("matches", [])
    for match in matches:
        match_id = match.get("id")
        status = match.get("status")
        if status == "FINISHED":
            away_score = match.get("score", {}).get("away")
            home_score = match.get("score", {}).get("home")
            winner = match.get("score", {}).get("winner")
            try:
                db.query(Fixtures).filter(Fixtures.id == match_id).update({
                    "status": status,
                    "away_team_score": away_score,
                    "home_team_score": home_score,
                    "winner": winner,
                })
                db.commit()
            except Exception as e:
                print(e)
                db.rollback()


async def fetch_fixtures():
    db = SessionLocal()
    client = FootballDataClient()

    start_date = db.query(func.max(Fixtures.date)).scalar()
    today_date = datetime.now().date()
    if start_date:
        start_date = (datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")).date()
        if start_date > today_date:
            start_date = today_date
    else:
        start_date = today_date
    next_date = (start_date + timedelta(days=15))
    if not start_date or start_date < today_date:
        start_date = today_date

    league_codes = ["PL", "PD", "BL1", "SA", "FL1", "CL", "WC", "PPL"]

    for code in league_codes:
        matches = client.get_competition_matches(code, {
            "dateFrom": str(start_date),
            "dateTo": str(next_date),
        })

        matches = matches.get("matches", [])
        for match in matches:
            away_team = match.get("awayTeam", {}).get("shortName")
            home_team = match.get("homeTeam", {}).get("shortName")

            if not home_team or not away_team:
                continue

            score = match.get("score", {}).get("fullTime", {})
            away_score = score.get("away")
            home_score = score.get("home")
            winner = match.get("score", {}).get("winner")
            match_id = match.get("id")
            league = match.get("competition", {}).get("code")
            status = match.get("status")
            date = match.get("utcDate")
            try:
                db.add(Fixtures(
                    id=match_id,
                    date=date,
                    away_team=away_team,
                    home_team=home_team,
                    away_team_score=away_score,
                    home_team_score=home_score,
                    winner=winner,
                    league=league,
                    status=status
                ))
                db.commit()
            except IntegrityError:
                db.rollback()
                cur_match = db.query(Fixtures).filter(Fixtures.id == match_id).first()
                if cur_match is None:
                    continue
                if cur_match.status == "FINISHED":
                    db.rollback()
                elif cur_match.status != status:
                    cur_match.status = status
                    cur_match.away_team_score = away_score
                    cur_match.home_team_score = home_score
                    cur_match.winner = winner
                    db.commit()
            except Exception as e:
                print(e)
                db.rollback()


async def fetch_leagues():
    db = SessionLocal()
    client = FootballDataClient()

    current_year = int(datetime.now().year)
    if datetime.now().month <= 8:
        current_year -= 1

    league_codes = ["PL", "PD", "BL1", "SA", "FL1", "PPL"]

    for code in league_codes:
        db.query(LeagueStandings).filter(
            LeagueStandings.league == code,
        ).delete()
        db.commit()

        leagues = client.get_competition_standings(code, {
            "season": current_year
        })
        leagues = leagues.get("standings", [])
        team_stats = leagues[0].get("table", {})
        for team in team_stats:
            position = team.get("position")
            team_name = team.get("team", {}).get("shortName")
            points = team.get("points")
            played_games = team.get("playedGames")
            won = team.get("won")
            draw = team.get("draw")
            lost = team.get("lost")
            goals_for = team.get("goalsFor")
            goals_against = team.get("goalsAgainst")
            goal_difference = team.get("goalDifference")

            try:
                db.add(LeagueStandings(
                    position=position,
                    team_name=team_name,
                    points=points,
                    played_games=played_games,
                    won=won,
                    draw=draw,
                    lost=lost,
                    goals_for=goals_for,
                    goals_against=goals_against,
                    goal_difference=goal_difference,
                    league=code
                ))
                db.commit()
            except IntegrityError:
                db.rollback()
            except Exception as e:
                print(e)
                db.rollback()

# To run the script:
# python3 -m app.scripts.jobs

#if __name__ == "__main__":
    #import asyncio
    #asyncio.run(fetch_fixtures())
    #asyncio.run(fetch_leagues())
    #asyncio.run(update_fixtures())