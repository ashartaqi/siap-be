from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db


router = APIRouter()

@router.get("")
def getPlayers(
    db: Session = Depends(get_db),
    limit: int = 11,
    team_id: int = None,
    name: str = None,
    nationality_name: str = None,
    position: str = None,
    min_overall: int = None,
    max_overall: int = None,
    min_age: int = None,
    max_age: int = None,
    preferred_foot: str = None
):
    return crud.get_players(db, limit, team_id, name, nationality_name, position, min_overall, max_overall, min_age, max_age, preferred_foot)