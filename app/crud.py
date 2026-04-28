from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import date
from app.core.security import verify_password, get_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload
from fastapi import HTTPException, status
from app.models import User, Club, Player, PlayerStats, GoalkeeperStats, FavouritePlayers, FavouriteClubs, LeagueStandings, Form, Votes, Fixtures, CustomPlayer, DreamTeam, DreamTeamSlot, PlayerPos
from app.api.constants import TEAM_TOTAL_OVERALL_MAX
from app.ai_models.dream_player import predict_player


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
    position: list[str] = None,
    min_overall: int = None,
    max_overall: int = None,
    min_age: int = None,
    max_age: int = None,
    preferred_foot: str = None,
    skip: int = 0,
    order_by_stat: str = None,
    pace: int = None,
    shooting: int = None,
    passing: int = None,
    dribbling: int = None,
    defending: int = None,
    physic: int = None,
):
    query = db.query(Player)

    if team_id:
        query = query.filter(Player.club_team_id == team_id)
    if name:
        query = query.filter(
            func.replace(Player.short_name, ' ', '').ilike(f"%{name.replace(' ', '')}%") |
            func.replace(Player.long_name, ' ', '').ilike(f"%{name.replace(' ', '')}%")
        )
    if nationality_name:
        query = query.filter(func.replace(Player.nationality_name, ' ', '').ilike(f"%{nationality_name.replace(' ', '')}%"))
    if position:
        # handle both single string and list
        if isinstance(position, str):
            position = [position]
        positions_upper = [p.strip().upper() for p in position]
        query = query.join(Player.positions).filter(PlayerPos.position.in_(positions_upper))
    if min_overall:
        query = query.filter(Player.overall >= min_overall)
    if max_overall:
        query = query.filter(Player.overall <= max_overall)
    if min_age:
        today = date.today()
        max_dob_year = today.year - min_age
        try:
            max_dob = today.replace(year=max_dob_year)
        except ValueError:
            max_dob = today.replace(year=max_dob_year, day=28)
        query = query.filter(Player.dob <= max_dob)
    if max_age:
        today = date.today()
        min_dob_year = today.year - max_age - 1
        try:
            min_dob = today.replace(year=min_dob_year)
        except ValueError:
            min_dob = today.replace(year=min_dob_year, day=28)
        query = query.filter(Player.dob > min_dob)
    if preferred_foot:
        query = query.filter(Player.preferred_foot.ilike(preferred_foot))

    if pace or shooting or passing or dribbling or defending or physic:
        query = query.join(Player.player_stats)
    if pace:
        query = query.filter(PlayerStats.pace == pace)
    if shooting:
        query = query.filter(PlayerStats.shooting == shooting)
    if passing:
        query = query.filter(PlayerStats.passing == passing)
    if dribbling:
        query = query.filter(PlayerStats.dribbling == dribbling)
    if defending:
        query = query.filter(PlayerStats.defending == defending)
    if physic:
        query = query.filter(PlayerStats.physic == physic)

    query = query.options(joinedload(Player.player_stats), joinedload(Player.positions), joinedload(Player.goalkeeper_stats))

    if order_by_stat:
        if hasattr(PlayerStats, order_by_stat):
            stat_col = getattr(PlayerStats, order_by_stat)
            query = query.join(Player.player_stats).filter(stat_col.is_not(None)).order_by(desc(stat_col), desc(Player.overall))
        elif hasattr(GoalkeeperStats, order_by_stat):
            stat_col = getattr(GoalkeeperStats, order_by_stat)
            query = query.join(Player.goalkeeper_stats).filter(stat_col.is_not(None)).order_by(desc(stat_col), desc(Player.overall))
        else:
            query = query.order_by(desc(Player.overall))
    else:
        query = query.order_by(desc(Player.overall))

    return query.offset(skip).limit(limit).all()


def add_fav_player(db, user, player):
    fav_player = FavouritePlayers(user_id=user, player_id=player)
    return create(db, fav_player, "Favourite either exists or there was a error")


def get_fav_players(db, user):
    return (
        db.query(Player)
        .join(FavouritePlayers, FavouritePlayers.player_id == Player.id)
        .filter(FavouritePlayers.user_id == user)
        .options(
            joinedload(Player.player_stats),
            joinedload(Player.positions),
            joinedload(Player.goalkeeper_stats)
        )
        .all()
    )


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
        if (status_filter == 'FINISHED'):
            query = query.filter(Fixtures.status == status_filter).order_by(Fixtures.date.desc())
        else:
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
    subq = db.query(LeagueStandings.id)

    if league:
        subq = subq.filter(LeagueStandings.league == league)
    if team_name:
        subq = subq.filter(LeagueStandings.team_name.ilike(f"%{team_name}%"))

    subq = subq.order_by(LeagueStandings.position).limit(limit).subquery()

    return (
        db.query(LeagueStandings)
        .join(subq, LeagueStandings.id == subq.c.id)
        .outerjoin(LeagueStandings.forms)
        .options(contains_eager(LeagueStandings.forms))
        .order_by(LeagueStandings.position, desc(Form.id))
        .all()
    )

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

#DREAM TEAM
def get_dream_team(db: Session, user_id: int):
    return db.query(DreamTeam)\
             .filter(DreamTeam.user_id == user_id)\
             .first()

def delete_dream_team(db: Session, user_id: int):
    team = db.query(DreamTeam).filter(
        DreamTeam.user_id == user_id
    ).first()
    if team:
        db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
        db.delete(team)
        db.commit()
        return True
    return False


def update_dream_team_slot(db: Session, user_id: int, slot_id: int, player_id: int):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")

    slot = db.query(DreamTeamSlot).filter(
        DreamTeamSlot.id == slot_id,
        DreamTeamSlot.dream_team_id == team.id
    ).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found in your dream team")

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player {player_id} not found")

    slot.player_id = player_id
    db.flush()

    # Recalculate total_score from all slots
    all_slots = db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).all()
    total = 0
    for s in all_slots:
        p = db.query(Player).filter(Player.id == s.player_id).first()
        if p:
            total += p.overall
    team.total_score = total // len(all_slots) if all_slots else 0

    db.commit()
    db.refresh(team)
    return team

def create_dream_team(db: Session, user_id: int, formation: str, slots: list):

    if len(slots) != 11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exactly 11 slots must be provided")

    total_score = 0
    for slot in slots:
        player = db.query(Player).filter(Player.id == slot.player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {slot.player_id} not found")
        total_score += player.overall

    if total_score > TEAM_TOTAL_OVERALL_MAX:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Total overall cannot exceed {TEAM_TOTAL_OVERALL_MAX}. You used {total_score}.")

    team=DreamTeam(user_id = user_id,formation=formation,total_score =(total_score)//11)
    create(db,team)

     

    
    for slot in slots:
        player = db.query(Player).filter(Player.id == slot.player_id).first()
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player with id {slot.player_id} not found")
        
        slot_row = DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        )
        create(db, slot_row)

    return team


def update_dream_team(db: Session, user_id: int, formation: str, slots: list):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")

    if len(slots) != 11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exactly 11 slots must be provided")

    total_score = 0
    for slot in slots:
        player = db.query(Player).filter(Player.id == slot.player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {slot.player_id} not found")
        total_score += player.overall

    if total_score > TEAM_TOTAL_OVERALL_MAX:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Total overall cannot exceed {TEAM_TOTAL_OVERALL_MAX}. You used {total_score}.")

    # Update team fields
    team.formation = formation
    team.total_score = total_score // 11

    # Delete old slots and create new ones
    db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
    db.flush()

    for slot in slots:
        slot_row = DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        )
        db.add(slot_row)

    db.commit()
    db.refresh(team)
    return team