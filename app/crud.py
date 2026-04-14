from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from app.core.security import verify_password, get_password_hash
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models import User, Club, Player, FavouritePlayers, FavouriteClubs, LeagueStandings, Votes, Fixtures, CustomPlayer


# USERS
def create(db: Session, model_item, error_msg: str = "Item already exists or an error occured"):
    try:
        db.add(model_item)
        db.commit()
        db.refresh(model_item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    return model_item


def create_user(db: Session, username: str, email: str, first_name: str, last_name: str, password: str, super_user: bool = False):
    hashed_pw = get_password_hash(password)
    user = User(username=username, email=email,first_name=first_name, last_name=last_name, password=hashed_pw, super_user=super_user)
    return create(db, user, "Username or email already exists")


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password):
        return user
    return None

# TEAMS
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


def add_fav_team(db, user, team):
    fav_team = FavouriteClubs(user_id=user, club_id=team)
    return create(db, fav_team, "Favourite either exists or there was a error")


def get_fav_teams(db, user):
    return db.query(Club).join(FavouriteClubs, FavouriteClubs.club_id == Club.id).filter(FavouriteClubs.user_id == user).all()


def remove_fav_team(db, user, team):
    deleted = db.query(FavouriteClubs).filter(
        FavouriteClubs.user_id == user,
        FavouriteClubs.club_id == team
    ).delete()
    db.commit()
    return deleted > 0

# PLAYERS
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
        if position.strip().upper() == "GK":
            query = query.filter(Player.goalkeeper_stats.has())
        else:
            query = query.filter(Player.player_stats.has())
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

    return query.order_by(desc(Player.overall)).limit(limit).all()


def add_fav_player(db, user, player):
    fav_player = FavouritePlayers(user_id=user, player_id=player)
    return create(db, fav_player, "Favourite either exists or there was a error")


def get_fav_players(db, user):
    return db.query(Player).join(FavouritePlayers, FavouritePlayers.player_id == Player.id).filter(FavouritePlayers.user_id == user).all()


def remove_fav_player(db, user, player):
    deleted = db.query(FavouritePlayers).filter(
        FavouritePlayers.user_id == user,
        FavouritePlayers.player_id == player
    ).delete()

    db.commit()
    return deleted > 0

# FIXTURES
def get_fixtures(
    db: Session,
    limit: int = 11,
    league: str = None,
    status_filter: str = None,
    home_team: str = None,
    away_team: str = None,
    date: str = None
):
    query = db.query(Fixtures)
    
    if league:
        query = query.filter(Fixtures.league == league)
    if status_filter:
        query = query.filter(Fixtures.status == status_filter)
    if home_team:
        query = query.filter(Fixtures.home_team.ilike(f"%{home_team}%"))
    if away_team:
        query = query.filter(Fixtures.away_team.ilike(f"%{away_team}%"))
    if date:
        query = query.filter(Fixtures.date == date)
    
    return query.limit(limit).all()


def get_standings(
    db: Session,
    limit: int = 20,
    league: str = None,
    team_name: str = None
):
    query = db.query(LeagueStandings)
    
    if league:
        query = query.filter(LeagueStandings.league == league)
    if team_name:
        query = query.filter(LeagueStandings.team_name.ilike(f"%{team_name}%"))
    
    return query.order_by(LeagueStandings.position).limit(limit).all()


def get_votes(
    db: Session,
    limit: int = 11,
    fixture_id: int = None
):
    query = db.query(Votes)
    
    if fixture_id:
        query = query.filter(Votes.fixture_id == fixture_id)
    
    return query.limit(limit).all()


def create_vote(
    db: Session,
    user_id: int,
    fixture_id: int,
    prediction_home_score: int,
    prediction_away_score: int,
):
    if db.query(Votes).filter(Votes.fixture_id == fixture_id, Votes.user_id == user_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vote already exists")
    vote = Votes(
        user_id=user_id,
        fixture_id=fixture_id,
        prediction_home_score=prediction_home_score,
        prediction_away_score=prediction_away_score,
    )
    return create(db, vote, "Error creating vote")


def get_user_votes(db: Session, user_id: int):
    return db.query(Votes).filter(Votes.user_id == user_id).all()


def delete_vote(db: Session, user_id: int, vote_id: int):
    vote = db.query(Votes).filter(
        Votes.id == vote_id,
        Votes.user_id == user_id
    ).first()
    if vote:
        db.delete(vote)
        db.commit()
        return True
    return False


# CUSTOM PLAYERS
def get_custom_players(db: Session, user_id: int):
    return db.query(CustomPlayer).filter().all()


def get_custom_player(db: Session, user_id: int):
    return db.query(CustomPlayer).filter(CustomPlayer.user_id == user_id).first()


def add_custom_player(db: Session, user_id: int, **data):
    player = CustomPlayer(user_id=user_id, **data)
    overall = (player.pace + player.shooting + player.passing + player.dribbling + player.defending + player.physic) / 6
    player.overall = overall
    return create(db, player, "Error creating custom player")


def update_custom_player(db: Session, player, **data):
    for field, value in data.items():
        setattr(player, field, value)
    overall = (player.pace + player.shooting + player.passing + player.dribbling + player.defending + player.physic) / 6
    player.overall = overall
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
