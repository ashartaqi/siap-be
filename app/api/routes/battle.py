from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app import crud
from app.api.deps import get_db
from app.models import User, DreamTeam, CustomPlayer
from app.core.security import get_current_user
from app.schemas import DreamTeamGet as DreamTeamSchema, CustomPlayerGet as CustomPlayerSchema

router = APIRouter()

@router.get("/users")
def get_battle_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Fetch all users who have either a dream team or a custom player
    # excluding the current user
    users_with_teams = db.query(DreamTeam.user_id).all()
    users_with_players = db.query(CustomPlayer.user_id).all()
    
    user_ids = set([u[0] for u in users_with_teams] + [u[0] for u in users_with_players])
    if current_user.id in user_ids:
        user_ids.remove(current_user.id)
        
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "has_team": u.id in [ut[0] for ut in users_with_teams],
            "has_player": u.id in [up[0] for up in users_with_players]
        }
        for u in users
    ]

@router.get("/team/{user_id}", response_model=DreamTeamSchema)
def get_user_dream_team(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, user_id)
    if not team:
        raise HTTPException(status_code=404, detail="Dream team not found for this user")
    return team

@router.get("/player/{user_id}", response_model=CustomPlayerSchema)
def get_user_custom_player(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = crud.get_custom_player(db, user_id)
    if not player:
        raise HTTPException(status_code=404, detail="Custom player not found for this user")
    return player
