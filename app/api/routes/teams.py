from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Team
from app.api.constants import FORMATIONS

router = APIRouter()

@router.get("", response_model=list[Team])
def get_teams(
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
    min_defence: int = None,
    team_type: str = "club"
):
    return crud.get_teams(db, skip, limit, name, league_name, nationality_name, min_overall, max_overall, min_attack, min_midfield, min_defence, team_type)


@router.post("/fav")
def add_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), team: int = None):
    if team:
        return crud.add_fav_team(db, current_user.id, team)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Team ID is required")


@router.get("/fav", response_model=list[Team])
def get_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    return crud.get_fav_teams(db, current_user.id)


@router.delete("/fav")
def remove_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), team: int = None):
    if team:
        result = crud.remove_fav_team(db, current_user.id, team)
        return {"success": result}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Team ID is required")
 

@router.get("/formations")
def get_formations():
    return FORMATIONS
