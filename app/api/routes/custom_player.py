from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import CustomPlayerCreate, CustomPlayerUpdate, CustomPlayerGet

router = APIRouter()

@router.post("/", response_model=CustomPlayerCreate, status_code=status.HTTP_201_CREATED)
def create_custom_player(payload: CustomPlayerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = crud.get_custom_player(db, current_user.id)
    if player:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have a dream player.")

    data = payload.model_dump()
    try:
        player = crud.add_custom_player(db, user_id=current_user.id, **data)
        return player
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=CustomPlayerGet)
def get_dream_player(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = crud.get_custom_player(db, current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream player found")
    return player


@router.patch("/", response_model=CustomPlayerUpdate)
def update_dream_player(payload: CustomPlayerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = crud.get_custom_player(db, current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Create a dream player first.")

    data = payload.model_dump(exclude_unset=True)
    try:
        player = crud.update_custom_player(db, player, **data)
        return player
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/")
def delete_dream_player(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = crud.delete_custom_player(db, current_user.id)
    if result:
        return {"success": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom player not found")