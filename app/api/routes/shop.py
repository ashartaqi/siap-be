from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import ShopUnlockResponse

router = APIRouter()

@router.post("/unlock/{player_id}", response_model=ShopUnlockResponse)
def unlock_player(player_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.unlock_player_in_db(db, current_user, player_id)
