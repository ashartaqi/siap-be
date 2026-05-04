from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.models import Club, FavouriteClubs
from app.crud.users import create

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
    min_defence: int = None,
    team_type: str = "club"):
    
    query = db.query(Club)

    if team_type == "national":
        query = query.filter(Club.league_name == "Friendly International")
    else:
        query = query.filter(Club.league_name != "Friendly International")

    if name:
        query = query.filter(func.replace(Club.name, ' ', '').ilike(f"%{name.replace(' ', '')}%"))
    if league_name:
        query = query.filter(func.replace(Club.league_name, ' ', '').ilike(f"%{league_name.replace(' ', '')}%"))
    if nationality_name:
        query = query.filter(func.replace(Club.nationality_name, ' ', '').ilike(f"%{nationality_name.replace(' ', '')}%"))
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

    return query.order_by(desc(Club.overall)).offset(skip).limit(limit).all()


def get_club_by_name(db: Session, name: str):
    return db.query(Club).filter(Club.name == name).first()


def add_fav_team(db: Session, user: int, team: int):
    fav_team = FavouriteClubs(user_id=user, club_id=team)
    return create(db, fav_team, "Favourite either exists or there was a error")


def get_fav_teams(db: Session, user: int):
    return db.query(Club).join(FavouriteClubs, FavouriteClubs.club_id == Club.id).filter(FavouriteClubs.user_id == user).all()


def remove_fav_team(db: Session, user: int, team: int):
    deleted = db.query(FavouriteClubs).filter(
        FavouriteClubs.user_id == user,
        FavouriteClubs.club_id == team
    ).delete()
    db.commit()
    return deleted > 0
