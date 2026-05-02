from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import date, datetime, timezone, timedelta
from app.core.security import verify_password, get_password_hash, hash_refresh_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload
from fastapi import HTTPException, status
from app.models import User, RefreshToken, Club, Player, PlayerStats, GoalkeeperStats, FavouritePlayers, FavouriteClubs, LeagueStandings, Form, Votes, Fixtures, CustomPlayer, DreamTeam, DreamTeamSlot, PlayerPos, ChatMessage, MatchComment, UnlockedPlayer
from app.constants import (
    TEAM_TOTAL_OVERALL_MAX, 
    CHAT_REWARD,
    MATCH_COMMENT_REWARD,
    BATTLE_WIN_REWARD,
    BATTLE_DRAW_REWARD,
    BATTLE_PARTICIPATION_REWARD,
    SHOP_PRICE_70_80,
    SHOP_PRICE_80_85,
    SHOP_PRICE_85_90,
    SHOP_PRICE_90_PLUS,
    DAILY_LOGIN_REWARD,
    INITIAL_BB_BALANCE
)
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
    user = User(
        username=username, 
        email=email,
        first_name=first_name, 
        last_name=last_name, 
        password=hashed_pw, 
        super_user=super_user,
        bb_balance=INITIAL_BB_BALANCE # Initial gift
    )
    return create(db, user, "Username or email already exists")

def create_refresh_token(db: Session, user_id: int, plain_token: str) -> RefreshToken:
    token_entry = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    return create(db, token_entry, "Error creating refresh token")

def get_and_validate_refresh_token(db: Session, plain_token: str) -> RefreshToken | None:
    token_entry = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_refresh_token(plain_token)
    ).first()
    if not token_entry:
        return None
    expires_at = token_entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return token_entry

def add_bb_reward(db: Session, user_id: int, amount: int):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.bb_balance += amount
        db.commit()
    return user

def check_and_award_daily_login_reward(db: Session, user: User) -> int:
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        already_rewarded = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.created_at >= today_start,
        ).first()
        if not already_rewarded:
            reward = DAILY_LOGIN_REWARD
            user.bb_balance = (user.bb_balance or 0) + reward
            db.flush()
            return reward
    except Exception as e:
        print(f"Daily reward error: {e}")
    return 0

def rotate_refresh_token(db: Session, old_token_id: int, user_id: int, new_plain_token: str) -> RefreshToken:
    """Delete the old token and issue a new one atomically."""
    db.query(RefreshToken).filter(
        RefreshToken.id == old_token_id,
        RefreshToken.user_id == user_id,
    ).delete(synchronize_session=False)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.expires_at < datetime.now(timezone.utc),
    ).delete(synchronize_session=False)
    new_entry = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(new_plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

def revoke_refresh_token(db: Session, plain_token: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_refresh_token(plain_token)
    ).delete(synchronize_session=False)
    db.commit()

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()

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

# PLAYERS
def get_players(
    db: Session,
    user_id: int = None,
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
    unlock_status: str = None,
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

    # Fetch unlocked player IDs for this user
    unlocked_ids = set()
    if user_id:
        unlocked_ids = {u[0] for u in db.query(UnlockedPlayer.player_id).filter(UnlockedPlayer.user_id == user_id).all()}

    if unlock_status and unlock_status != "all" and user_id:
        if unlock_status == "unlocked":
            query = query.filter((Player.id.in_(unlocked_ids)) | (Player.overall < 70))
        elif unlock_status == "locked":
            query = query.filter((Player.overall >= 70) & (~Player.id.in_(unlocked_ids)))

    players = query.offset(skip).limit(limit).all()
    
    for p in players:
        p.is_unlocked = (p.id in unlocked_ids or p.overall < 70) if user_id else True
        
    return players


def add_fav_player(db: Session, user: int, player: int):
    fav_player = FavouritePlayers(user_id=user, player_id=player)
    return create(db, fav_player, "Favourite either exists or there was a error")


def get_fav_players(db: Session, user: int):
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


def remove_fav_player(db: Session, user: int, player: int):
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


def get_votes_with_users(
    db: Session,
    fixture_id: int,
    limit: int = 50,
):
    """Get all votes for a fixture, joined with user info."""
    rows = (
        db.query(
            Votes.id,
            Votes.user_id,
            User.username,
            User.first_name,
            Votes.fixture_id,
            Votes.prediction_home_score,
            Votes.prediction_away_score,
        )
        .join(User, User.id == Votes.user_id)
        .filter(Votes.fixture_id == fixture_id)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": r.username,
            "first_name": r.first_name,
            "fixture_id": r.fixture_id,
            "prediction_home_score": r.prediction_home_score,
            "prediction_away_score": r.prediction_away_score,
        }
        for r in rows
    ]


def create_vote(
    db: Session,
    user_id: int,
    fixture_id: int,
    prediction_home_score: int,
    prediction_away_score: int,
):
    existing = db.query(Votes).filter(Votes.user_id == user_id, Votes.fixture_id == fixture_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vote already exists for this fixture")

    vote = Votes(
        user_id=user_id,
        fixture_id=fixture_id,
        prediction_home_score=prediction_home_score,
        prediction_away_score=prediction_away_score,
    )
    return create(db, vote, "Error creating vote")



def get_user_votes(db: Session, user_id: int):
    return db.query(Votes).filter(Votes.user_id == user_id).all()


def update_vote(
    db: Session,
    user_id: int,
    fixture_id: int,
    prediction_home_score: int,
    prediction_away_score: int,
):
    """Update the prediction on the user's vote for a specific fixture."""
    vote = db.query(Votes).filter(Votes.user_id == user_id, Votes.fixture_id == fixture_id).first()
    if not vote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No vote found for this fixture")
    
    vote.fixture_id = fixture_id
    vote.prediction_home_score = prediction_home_score
    vote.prediction_away_score = prediction_away_score
    db.commit()
    db.refresh(vote)
    return vote


def delete_vote(db: Session, user_id: int, vote_id: int = None):
    if vote_id:
        vote = db.query(Votes).filter(
            Votes.id == vote_id,
            Votes.user_id == user_id
        ).first()
    else:
        vote = db.query(Votes).filter(Votes.user_id == user_id).first()
    
    if vote:
        db.delete(vote)
        db.commit()
        return True
    return False


# CUSTOM PLAYERS
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

# DREAM TEAM
def _validate_dream_team_slots(db: Session, slots: list) -> int:
    if len(slots) != 11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exactly 11 slots must be provided")

    player_ids = [slot.player_id for slot in slots]
    players_by_id = {p.id: p for p in db.query(Player).filter(Player.id.in_(player_ids)).all()}

    missing = [pid for pid in player_ids if pid not in players_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Players not found: {missing}")

    total_score = sum(players_by_id[slot.player_id].overall for slot in slots)
    if total_score > TEAM_TOTAL_OVERALL_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total overall cannot exceed {TEAM_TOTAL_OVERALL_MAX}. You used {total_score}."
        )

    return total_score


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

# CHAT
def get_chat_messages(db: Session, limit: int = 50):
    messages = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.user))
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
        .all()
    )
    return list(reversed(messages))

def create_chat_message(db: Session, user_id: int, content: str):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    reward = 0
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        first_today = not db.query(ChatMessage).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.created_at >= today_start,
        ).first()
        if first_today:
            reward = CHAT_REWARD
            user.bb_balance += reward
            db.flush()

    message = ChatMessage(user_id=user_id, content=content)
    db_message = create(db, message, "Error sending message")
    return db_message, reward

# MATCH COMMENTS
def get_match_comments(db: Session, match_id: int):
    return (
        db.query(MatchComment)
        .options(joinedload(MatchComment.user))
        .filter(MatchComment.match_id == match_id)
        .order_by(MatchComment.created_at.desc())
        .all()
    )

def create_match_comment(db: Session, user_id: int, match_id: int, content: str):
    comment = MatchComment(user_id=user_id, match_id=match_id, content=content)

    reward = MATCH_COMMENT_REWARD
    add_bb_reward(db, user_id, reward)

    db_comment = create(db, comment, "Error posting comment")
    return db_comment, reward




def create_dream_team(db: Session, user_id: int, formation: str, slots: list):
    total_score = _validate_dream_team_slots(db, slots)

    team = DreamTeam(user_id=user_id, formation=formation, total_score=total_score // 11)
    create(db, team)

    for slot in slots:
        create(db, DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        ))

    return team


def update_dream_team(db: Session, user_id: int, formation: str, slots: list):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")

    total_score = _validate_dream_team_slots(db, slots)

    team.formation = formation
    team.total_score = total_score // 11

    db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
    db.flush()

    for slot in slots:
        db.add(DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        ))

    db.commit()
    db.refresh(team)
    return team

# SHOP
def get_unlock_price(overall: int) -> int:
    if overall < 70:
        return 0
    if 70 <= overall < 80:
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

def get_battle_users_from_db(db: Session, current_user_id: int):
    # Fetch all user_ids who have either a dream team or a custom player
    users_with_teams = {u[0] for u in db.query(DreamTeam.user_id).all()}
    users_with_players = {u[0] for u in db.query(CustomPlayer.user_id).all()}
    
    user_ids = users_with_teams.union(users_with_players)
    if current_user_id in user_ids:
        user_ids.remove(current_user_id)
        
    if not user_ids:
        return [], set(), set()
        
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    return users, users_with_teams, users_with_players