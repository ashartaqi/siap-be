from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Goalkeepers


router = APIRouter()

@router.get("/", response_model=list[Goalkeepers])
def get_goalkeepers(
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
        players = crud.get_goalkeepers(
            db, limit, team_id, name, nationality_name, position,
            min_overall, max_overall, min_age, max_age, preferred_foot
        )
        return players
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))