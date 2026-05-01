from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User, Player, UnlockedPlayer
from app.core.security import get_current_user

router = APIRouter()

def get_unlock_price(overall: int) -> int:
    if overall < 70:
        return 0
    if 70 <= overall < 80:
        return 30
    if 80 <= overall < 85:
        return 40
    if 85 <= overall < 90:
        return 50
    return 100

@router.post("/unlock/{player_id}")
def unlock_player(player_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check if already unlocked
    existing = db.query(UnlockedPlayer).filter(
        UnlockedPlayer.user_id == current_user.id,
        UnlockedPlayer.player_id == player_id
    ).first()
    
    if existing:
        return {"message": "Player already unlocked"}
        
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
        
    price = get_unlock_price(player.overall)
    
    if current_user.bb_balance < price:
        raise HTTPException(status_code=400, detail=f"Insufficient BB balance. Need {price} BB.")
        
    # Deduct and unlock
    current_user.bb_balance -= price
    unlock_entry = UnlockedPlayer(user_id=current_user.id, player_id=player_id)
    db.add(unlock_entry)
    db.commit()
    
    return {"message": f"Successfully unlocked {player.short_name}", "new_balance": current_user.bb_balance}
