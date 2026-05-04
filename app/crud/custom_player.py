from sqlalchemy.orm import Session
from app.models import CustomPlayer
from app.ai_models.dream_player import predict_player
from app.crud.users import create

def get_custom_player(db: Session, user_id: int):
    return db.query(CustomPlayer).filter(CustomPlayer.user_id == user_id).first()


def add_custom_player(db: Session, user_id: int, **data):
    player = CustomPlayer(user_id=user_id, **data)
    overall, position = predict_player(
        player.pace, player.shooting, player.passing,
        player.dribbling, player.defending, player.physic,
    )
    player.overall = overall
    player.position = position
    return create(db, player, "Error creating custom player")


def update_custom_player(db: Session, player, **data):
    for field, value in data.items():
        setattr(player, field, value)
    overall, position = predict_player(
        player.pace, player.shooting, player.passing,
        player.dribbling, player.defending, player.physic,
    )
    player.overall = overall
    player.position = position
    db.commit()
    db.refresh(player)
    return player


def delete_custom_player(db: Session, user_id: int):
    player = db.query(CustomPlayer).filter(
        CustomPlayer.user_id == user_id
    ).first()
    if player:
        db.delete(player)
        db.commit()
        return True
    return False
