from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.schemas import Fixtures, LeagueStandings
from app.models import User
from app.core.security import get_current_user
from app.scripts.jobs import (
    update_fixtures as update_fixtures_job,
    fetch_leagues as fetch_leagues_job,
    fetch_fixtures as fetch_fixtures_job,
)
from app.api.constants import VALID_MATCH_STATUSES, FIXTURE_LEAGUES
from app.core.config import settings


router = APIRouter()


@router.get("/fixtures", response_model=list[Fixtures])
def get_fixtures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    league: str = None,
    team_name: str = None
):
    try:
        standings = crud.get_standings(db, limit, league, team_name)
        return standings
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/match-statuses")
def get_match_statuses(current_user: User = Depends(get_current_user)):
    return VALID_MATCH_STATUSES

@router.get("/fixture-leagues")
def get_fixture_leages(current_user: User = Depends(get_current_user)):
    return FIXTURE_LEAGUES


@router.get("/current-season")
def get_current_season(current_user: User = Depends(get_current_user)):
    now = datetime.now()

    if now.month >= 8:
        start_year = now.year
    else:
        start_year = now.year - 1

    formatted = f"{start_year}/{(start_year + 1) % 100:02d}"
    return formatted


@router.post("/update-fixtures")
async def update_match(background_tasks: BackgroundTasks, cron_key: Optional[str] = Header(None, alias="X-CRON-KEY")):
    if cron_key != settings.CRON_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this endpoint is forbidden")
    try:
        background_tasks.add_task(update_fixtures_job)
        return {"message": "Fixtures update started in background"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.post("/fetch-leagues")
async def fetch_leagues(background_tasks: BackgroundTasks, cron_key: Optional[str] = Header(None, alias="X-CRON-KEY")):
    if cron_key != settings.CRON_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this endpoint is forbidden")
    try:
        background_tasks.add_task(fetch_leagues_job)
        return {"message": "Leagues update started in background"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.post("/fetch-fixtures")
async def fetch_fixtures(background_tasks: BackgroundTasks, cron_key: Optional[str] = Header(None, alias="X-CRON-KEY")):
    if cron_key != settings.CRON_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this endpoint is forbidden")
    try:
        background_tasks.add_task(fetch_fixtures_job)
        return {"message": "Fixtures addition started in background"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))