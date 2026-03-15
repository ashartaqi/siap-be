from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db


router = APIRouter()

@router.get("")
def getTeams(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    name: str = None,
    league_name: str = None,
    nationality_name: str = None,
    min_overall: int = None,
    max_overall: int = None,
    min_attack: int = None,
    min_midfield: int = None,
    min_defence: int = None
):
    return crud.get_teams(db, skip, limit, name, league_name, nationality_name, min_overall, max_overall, min_attack, min_midfield, min_defence)