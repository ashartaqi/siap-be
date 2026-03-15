from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.security import verify_password, get_password_hash
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models import User, Club, Player


def create_user(db: Session, username: str, email: str, password: str, super_user: bool = False):
    hashed_pw = get_password_hash(password)
    user = User(username=username, email=email, password=hashed_pw, super_user=super_user)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username or email already exists")
    return user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password):
        return user
    return None

def get_teams(
    db: Session, skip: int = 0,
    limit: int = 100,
    name: str = None, 
    league_name: str = None, 
    nationality_name: str = None, 
    min_overall: int = None, 
    max_overall: int = None, 
    min_attack: int = None, 
    min_midfield: int = None, 
    min_defence: int = None):
    
    query = db.query(Club)

    if name:
        query = query.filter(Club.name.ilike(f"%{name}%"))
    if league_name:
        query = query.filter(Club.league_name.ilike(f"%{league_name}%"))
    if nationality_name:
        query = query.filter(Club.nationality_name.ilike(nationality_name))
    if min_overall:
        query = query.filter(Club.overall >= min_overall)
    if max_overall:
        query = query.filter(Club.overall <= max_overall)
    if min_attack:
        query = query.filter(Club.attack >= min_attack)
    if min_midfield:
        query = query.filter(Club.midfield >= min_midfield)
    if min_defence:
        query = query.filter(Club.defence >= min_defence)

    return query.offset(skip).limit(limit).all()

def get_players(
    db: Session,
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
    query = db.query(Player)

    if team_id:
        query = query.filter(Player.club_team_id == team_id)
    if name:
        query = query.filter(
            Player.short_name.ilike(f"%{name}%") | 
            Player.long_name.ilike(f"%{name}%")
        )
    if nationality_name:
        query = query.filter(Player.nationality_name.ilike(nationality_name))
    if position:
        query = query.filter(Player.player_positions.ilike(f"%{position}%"))
    if min_overall:
        query = query.filter(Player.overall >= min_overall)
    if max_overall:
        query = query.filter(Player.overall <= max_overall)
    if min_age:
        query = query.filter(Player.age >= min_age)
    if max_age:
        query = query.filter(Player.age <= max_age)
    if preferred_foot:
        query = query.filter(Player.preferred_foot.ilike(preferred_foot))

    return query.limit(limit).all()