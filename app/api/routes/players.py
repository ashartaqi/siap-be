from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Players
from app.api.constants import VALID_PLAYER_POSITIONS, VALID_PREFERRED_FEET


router = APIRouter()


@router.get("/", response_model=list[Players])
def get_players(
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
    try:
        players = crud.get_players(
            db, limit, team_id, name, nationality_name, position,
            min_overall, max_overall, min_age, max_age, preferred_foot
        )
        return players
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))


@router.post("/fav")
def add_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), player: int = None):
    if player:
        return crud.add_fav_player(db, current_user.id, player)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Player ID is required")


@router.get("/fav")
def get_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    return crud.get_fav_players(db, current_user.id)


@router.delete("/fav")
def remove_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), player: int = None):
    if player:
        result = crud.remove_fav_player(db, current_user.id, player)
        return {"success": result}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Player ID is required")


@router.get("/positions")
def get_player_positions():
    return VALID_PLAYER_POSITIONS


@router.get("/preferred-feet")
def get_preferred_feet():
    return VALID_PREFERRED_FEET
