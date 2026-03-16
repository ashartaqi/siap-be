from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user


router = APIRouter()

@router.get("/")
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
    return crud.get_players(db, limit, team_id, name, nationality_name, position, min_overall, max_overall, min_age, max_age, preferred_foot)


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