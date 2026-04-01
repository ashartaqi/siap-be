from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models import CustomPlayer, User
from app.schemas import CustomPlayerCreate, CustomPlayerUpdate, CustomPlayerOut

router = APIRouter()


def get_player_or_404(player_id: int, user_id: int, db: Session) -> CustomPlayer:
    player = db.query(CustomPlayer).filter(
        CustomPlayer.id == player_id,
        CustomPlayer.user_id == user_id
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="Custom player not found")
    return player


@router.post("/", response_model=CustomPlayerOut, status_code=status.HTTP_201_CREATED)
def create_custom_player(payload: CustomPlayerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(CustomPlayer).filter(CustomPlayer.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have a dream player. Delete it to create a new one.")

    overall = payload.pace + payload.shooting + payload.passing + payload.dribbling + payload.defending + payload.physic
    data = payload.model_dump()
    data["overall"] = overall

    player = CustomPlayer(user_id=current_user.id, **data)
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("/", response_model=CustomPlayerOut)
def get_dream_player(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = db.query(CustomPlayer).filter(CustomPlayer.user_id == current_user.id).first()
    if not player:
        raise HTTPException(status_code=404, detail="No dream player found")
    return player


@router.patch("/{player_id}", response_model=CustomPlayerOut)
def update_custom_player(player_id: int, payload: CustomPlayerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = get_player_or_404(player_id, current_user.id, db)

    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(player, field, value)

    total = player.pace + player.shooting + player.passing + player.dribbling + player.defending + player.physic
    if total > 570:
        raise HTTPException(status_code=400, detail=f"Updated total ({total}) exceeds 570 cap.")

    player.overall = total/6  # Recalculate overall as average of stats
    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_player(player_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = get_player_or_404(player_id, current_user.id, db)
    db.delete(player)
    db.commit()