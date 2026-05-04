from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import UnlockedPlayer, Player, User
from app.constants import (
    FREE_PLAYER_CAP,
    SHOP_PRICE_70_80,
    SHOP_PRICE_80_85,
    SHOP_PRICE_85_90,
    SHOP_PRICE_90_PLUS
)

def get_unlock_price(overall: int) -> int:
    if overall < FREE_PLAYER_CAP:
        return 0
    if FREE_PLAYER_CAP <= overall < 80:
        return SHOP_PRICE_70_80
    if 80 <= overall < 85:
        return SHOP_PRICE_80_85
    if 85 <= overall < 90:
        return SHOP_PRICE_85_90
    return SHOP_PRICE_90_PLUS

def unlock_player(db: Session, user_id: int, player_id: int):
    existing = db.query(UnlockedPlayer).filter(
        UnlockedPlayer.user_id == user_id,
        UnlockedPlayer.player_id == player_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player already unlocked")

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    user = db.query(User).filter(User.id == user_id).first()
    price = get_unlock_price(player.overall)
    if user.bb_balance < price:
        raise HTTPException(status_code=400, detail=f"Insufficient BB balance. Need {price} BB.")

    user.bb_balance -= price
    db.add(UnlockedPlayer(user_id=user_id, player_id=player_id))
    db.commit()

    return {"message": f"Successfully unlocked {player.short_name}", "new_balance": user.bb_balance}
