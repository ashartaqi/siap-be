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
    # Fetch all user_ids who have either a dream team or a custom player
    users_with_teams = {u[0] for u in db.query(DreamTeam.user_id).all()}
    users_with_players = {u[0] for u in db.query(CustomPlayer.user_id).all()}
    
    user_ids = users_with_teams.union(users_with_players)
    if current_user.id in user_ids:
        user_ids.remove(current_user.id)
        
    if not user_ids:
        return []
        
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "has_team": u.id in users_with_teams,
            "has_player": u.id in users_with_players
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
        raise HTTPException(status_code=404, detail=f"Custom player not found for user_id {user_id}")
    return player

@router.post("/reward")
def award_battle_reward(result: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # result: 'win', 'loss', 'draw'
    reward = 10 # Participation
    if result == 'win':
        reward += 40
    elif result == 'draw':
        reward += 10 
        
    current_user.bb_balance += reward
    db.commit()
    return {"new_balance": current_user.bb_balance, "reward": reward}
