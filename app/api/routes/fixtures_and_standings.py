from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.schemas import Fixtures, LeagueStandings
from app.api.constants import LEAGUE_CODES, VALID_MATCH_STATUSES


router = APIRouter()


@router.get("/fixtures", response_model=list[Fixtures])
def get_fixtures(
    db: Session = Depends(get_db),
    limit: int = 11,
    league: str = None,
    status_filter: str = None,
    home_team: str = None,
    away_team: str = None,
    date: str = None
):
    try:
        fixtures = crud.get_fixtures(
            db, limit, league, status_filter, home_team, away_team, date
        )
        return fixtures
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/standings", response_model=list[LeagueStandings])
def get_standings(
    db: Session = Depends(get_db),
    limit: int = 20,
    league: str = None,
    team_name: str = None
):
    try:
        standings = crud.get_standings(db, limit, league, team_name)
        return standings
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/league-codes")
def get_league_codes():
    return LEAGUE_CODES


@router.get("/match-statuses")
def get_match_statuses():
    return VALID_MATCH_STATUSES
