from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text
from datetime import date, datetime, timezone, timedelta
import json
from types import SimpleNamespace
from app.core.security import verify_password, get_password_hash, hash_refresh_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload
from fastapi import HTTPException, status
from app.models import User, RefreshToken, Club, Player, PlayerStats, GoalkeeperStats, FavouritePlayers, FavouriteClubs, LeagueStandings, Form, Votes, Fixtures, CustomPlayer, DreamTeam, DreamTeamSlot, PlayerPos, ChatMessage, MatchComment, UnlockedPlayer
from app.constants import (
    TEAM_TOTAL_OVERALL_MAX,
    FREE_PLAYER_CAP,
    CHAT_REWARD,
    MATCH_COMMENT_REWARD,
    SHOP_PRICE_70_80,
    SHOP_PRICE_80_85,
    SHOP_PRICE_85_90,
    SHOP_PRICE_90_PLUS,
    DAILY_LOGIN_REWARD,
    INITIAL_BB_BALANCE
)
from app.ai_models.dream_player import predict_player


_VALID_STAT_ORDER_COLS = frozenset({
    'pace', 'shooting', 'passing', 'dribbling', 'defending', 'physic',
    'diving', 'handling', 'kicking', 'positioning', 'reflexes', 'speed',
})


def _pg_error_msg(e: Exception) -> str:
    """Extract just the RAISE EXCEPTION message from a psycopg2/SQLAlchemy error."""
    msg = str(e)
    if ') ' in msg:
        msg = msg.split(') ', 1)[1]
    return msg.split('\n')[0].strip()


def _row_to_player(row) -> SimpleNamespace:
    """Convert a v_players_with_stats / fn_players_for_user row to a
    Player-like object the Players Pydantic schema can serialize."""
    d = dict(row._mapping)

    stat_keys = ('pace', 'shooting', 'passing', 'dribbling', 'defending', 'physic')
    gk_keys   = ('diving', 'handling', 'kicking', 'positioning', 'reflexes', 'speed')

    p = SimpleNamespace(**{k: v for k, v in d.items() if k not in stat_keys + gk_keys})

    p.player_stats = (
        SimpleNamespace(**{k: d.get(k) for k in stat_keys})
        if any(d.get(k) is not None for k in stat_keys) else None
    )
    p.goalkeeper_stats = (
        SimpleNamespace(**{k: d.get(k) for k in gk_keys})
        if any(d.get(k) is not None for k in gk_keys) else None
    )

    if not isinstance(getattr(p, 'positions', None), list):
        p.positions = []

    if not hasattr(p, 'is_unlocked'):
        p.is_unlocked = True

    return p


# ── USERS ────────────────────────────────────────────────────────────────────

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
        bb_balance=INITIAL_BB_BALANCE
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
        with db.begin_nested():
            reward = db.execute(
                text("SELECT fn_check_and_award_daily_login(:uid)"),
                {"uid": user.id}
            ).scalar()
        return reward or 0
    except Exception as e:
        # begin_nested() rolls back to the savepoint on exception,
        # keeping the outer transaction alive for create_refresh_token.
        print(f"Daily reward error: {e}")
        return 0


def rotate_refresh_token(db: Session, old_token_id: int, user_id: int, new_plain_token: str):
    new_hash   = hash_refresh_token(new_plain_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    db.execute(
        text("CALL sp_rotate_refresh_token(:old_id, :uid, :hash, :expires)"),
        {"old_id": old_token_id, "uid": user_id, "hash": new_hash, "expires": expires_at}
    )
    db.commit()


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


def reset_user_password(db: Session, email: str, current_password: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(current_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete(synchronize_session=False)
    user.password = get_password_hash(password)
    db.commit()
    db.refresh(user)
    return user


# ── TEAMS ─────────────────────────────────────────────────────────────────────

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
    return db.execute(
        text("SELECT * FROM v_fav_teams WHERE user_id = :uid ORDER BY overall DESC"),
        {"uid": user}
    ).all()


def remove_fav_team(db: Session, user: int, team: int):
    deleted = db.query(FavouriteClubs).filter(
        FavouriteClubs.user_id == user,
        FavouriteClubs.club_id == team
    ).delete()
    db.commit()
    return deleted > 0


# ── PLAYERS ───────────────────────────────────────────────────────────────────

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
    conditions: list[str] = []
    params: dict = {"_limit": limit, "_skip": skip}

    if team_id:
        conditions.append("club_team_id = :team_id")
        params["team_id"] = team_id

    if name:
        conditions.append(
            "(replace(short_name, ' ', '') ILIKE :name_pat"
            " OR replace(long_name, ' ', '') ILIKE :name_pat)"
        )
        params["name_pat"] = f"%{name.replace(' ', '')}%"

    if nationality_name:
        conditions.append("replace(nationality_name, ' ', '') ILIKE :nat_pat")
        params["nat_pat"] = f"%{nationality_name.replace(' ', '')}%"

    if position:
        if isinstance(position, str):
            position = [position]
        positions_upper = [p.strip().upper() for p in position]
        if len(positions_upper) == 1:
            conditions.append(":pos = ANY(positions)")
            params["pos"] = positions_upper[0]
        else:
            conditions.append("positions && string_to_array(:positions, ',')")
            params["positions"] = ",".join(positions_upper)

    if min_overall:
        conditions.append("overall >= :min_overall")
        params["min_overall"] = min_overall

    if max_overall:
        conditions.append("overall <= :max_overall")
        params["max_overall"] = max_overall

    if min_age:
        today = date.today()
        max_dob_year = today.year - min_age
        try:
            max_dob = today.replace(year=max_dob_year)
        except ValueError:
            max_dob = today.replace(year=max_dob_year, day=28)
        conditions.append("dob <= :max_dob")
        params["max_dob"] = max_dob

    if max_age:
        today = date.today()
        min_dob_year = today.year - max_age - 1
        try:
            min_dob = today.replace(year=min_dob_year)
        except ValueError:
            min_dob = today.replace(year=min_dob_year, day=28)
        conditions.append("dob > :min_dob")
        params["min_dob"] = min_dob

    if preferred_foot:
        conditions.append("preferred_foot ILIKE :foot")
        params["foot"] = preferred_foot

    for _stat in ('pace', 'shooting', 'passing', 'dribbling', 'defending', 'physic'):
        _val = locals().get(_stat)
        if _val is not None:
            conditions.append(f"{_stat} = :{_stat}")
            params[_stat] = _val

    if unlock_status and unlock_status != "all" and user_id:
        if unlock_status == "unlocked":
            conditions.append("is_unlocked = TRUE")
        elif unlock_status == "locked":
            conditions.append("is_unlocked = FALSE")

    if order_by_stat and order_by_stat in _VALID_STAT_ORDER_COLS:
        order_clause = f"ORDER BY {order_by_stat} DESC NULLS LAST, overall DESC"
    else:
        order_clause = "ORDER BY overall DESC"

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    if user_id:
        # Inline the unlock join so we don't rely on fn_players_for_user existing
        base = """(
            SELECT pvs.*,
                   (pvs.overall < 70 OR up.player_id IS NOT NULL) AS is_unlocked
            FROM v_players_with_stats pvs
            LEFT JOIN unlocked_players up
                ON up.player_id = pvs.id AND up.user_id = :_uid
        ) AS _p"""
        params["_uid"] = user_id
    else:
        base = "v_players_with_stats AS _p"

    sql = f"""
        SELECT *
        FROM {base}
        {where_clause}
        {order_clause}
        LIMIT :_limit OFFSET :_skip
    """

    rows = db.execute(text(sql), params).all()
    return [_row_to_player(r) for r in rows]


def add_fav_player(db: Session, user: int, player: int):
    fav_player = FavouritePlayers(user_id=user, player_id=player)
    return create(db, fav_player, "Favourite either exists or there was a error")


def get_fav_players(db: Session, user: int):
    rows = db.execute(
        text("SELECT * FROM v_fav_players WHERE user_id = :uid ORDER BY overall DESC"),
        {"uid": user}
    ).all()
    return [_row_to_player(r) for r in rows]


def remove_fav_player(db: Session, user: int, player: int):
    deleted = db.query(FavouritePlayers).filter(
        FavouritePlayers.user_id == user,
        FavouritePlayers.player_id == player
    ).delete()
    db.commit()
    return deleted > 0


# ── FIXTURES ──────────────────────────────────────────────────────────────────

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
        if status_filter == 'FINISHED':
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


def get_upcoming_fixtures(db: Session, limit: int = 10) -> list:
    return (
        db.query(Fixtures)
        .filter(Fixtures.status.in_(["SCHEDULED", "TIMED"]))
        .order_by(Fixtures.date)
        .limit(limit)
        .all()
    )


# ── STANDINGS ─────────────────────────────────────────────────────────────────

def get_standings(
    db: Session,
    limit: int = 20,
    league: str = None,
    team_name: str = None
):
    conditions: list[str] = []
    params: dict = {"_limit": limit}

    if league:
        conditions.append("league = :league")
        params["league"] = league
    if team_name:
        conditions.append("team_name ILIKE :team_name")
        params["team_name"] = f"%{team_name}%"

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = f"""
        SELECT
            id, position, team_name, points, played_games, won, draw, lost,
            goals_for, goals_against, goal_difference, league, logo_url,
            ARRAY_AGG(form_outcome ORDER BY form_id DESC)
                FILTER (WHERE form_outcome IS NOT NULL) AS forms
        FROM v_standings_with_form
        {where_clause}
        GROUP BY id, position, team_name, points, played_games, won, draw, lost,
                 goals_for, goals_against, goal_difference, league, logo_url
        ORDER BY position
        LIMIT :_limit
    """

    return db.execute(text(sql), params).all()


# ── VOTES ─────────────────────────────────────────────────────────────────────

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
    rows = db.execute(
        text("""
            SELECT id, user_id, username, first_name,
                   fixture_id, prediction_home_score, prediction_away_score
            FROM v_votes_with_users
            WHERE fixture_id = :fixture_id
            LIMIT :limit
        """),
        {"fixture_id": fixture_id, "limit": limit}
    ).all()
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


# ── CUSTOM PLAYERS ────────────────────────────────────────────────────────────

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


# ── DREAM TEAM ────────────────────────────────────────────────────────────────

def get_dream_team(db: Session, user_id: int):
    return db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()


def delete_dream_team(db: Session, user_id: int):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if team:
        db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
        db.delete(team)
        db.commit()
        return True
    return False


def create_dream_team(db: Session, user_id: int, formation: str, slots: list):
    slots_json = json.dumps([
        {"position": s.position, "row": s.row, "col": s.col, "player_id": s.player_id}
        for s in slots
    ])
    try:
        db.execute(
            text("CALL sp_create_dream_team(:uid, :formation, :slots::jsonb)"),
            {"uid": user_id, "formation": formation, "slots": slots_json}
        )
        db.commit()
        return get_dream_team(db, user_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_pg_error_msg(e))


def update_dream_team(db: Session, user_id: int, formation: str, slots: list):
    slots_json = json.dumps([
        {"position": s.position, "row": s.row, "col": s.col, "player_id": s.player_id}
        for s in slots
    ])
    try:
        db.execute(
            text("CALL sp_update_dream_team(:uid, :formation, :slots::jsonb)"),
            {"uid": user_id, "formation": formation, "slots": slots_json}
        )
        db.commit()
        return get_dream_team(db, user_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_pg_error_msg(e))


def update_dream_team_slot(db: Session, user_id: int, slot_id: int, player_id: int):
    try:
        db.execute(
            text("CALL sp_update_dream_team_slot(:uid, :sid, :pid)"),
            {"uid": user_id, "sid": slot_id, "pid": player_id}
        )
        db.commit()
        return get_dream_team(db, user_id)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_pg_error_msg(e))


# ── CHAT ──────────────────────────────────────────────────────────────────────

def get_chat_messages(db: Session, limit: int = 50):
    return db.execute(
        text("SELECT * FROM v_chat_messages_with_users LIMIT :limit"),
        {"limit": limit}
    ).all()


def create_chat_message(db: Session, user_id: int, content: str):
    row = db.execute(
        text("SELECT message_id, reward FROM fn_create_chat_message(:uid, :content)"),
        {"uid": user_id, "content": content}
    ).first()
    msg_id, reward = row.message_id, row.reward

    msg_row = db.execute(
        text("SELECT * FROM v_chat_messages_with_users WHERE id = :id"),
        {"id": msg_id}
    ).first()
    db.commit()

    msg = SimpleNamespace(**dict(msg_row._mapping))
    return msg, reward


# ── MATCH COMMENTS ────────────────────────────────────────────────────────────

def get_match_comments(db: Session, match_id: int):
    return db.execute(
        text("SELECT * FROM v_match_comments_with_users WHERE match_id = :mid"),
        {"mid": match_id}
    ).all()


def create_match_comment(db: Session, user_id: int, match_id: int, content: str):
    row = db.execute(
        text("SELECT comment_id, reward FROM fn_create_match_comment(:uid, :mid, :content)"),
        {"uid": user_id, "mid": match_id, "content": content}
    ).first()
    comment_id, reward = row.comment_id, row.reward

    comment_row = db.execute(
        text("SELECT * FROM v_match_comments_with_users WHERE id = :id"),
        {"id": comment_id}
    ).first()
    db.commit()

    comment = SimpleNamespace(**dict(comment_row._mapping))
    return comment, reward


# ── SHOP ──────────────────────────────────────────────────────────────────────

def get_unlock_price(overall: int) -> int:
    if overall < FREE_PLAYER_CAP:          return 0
    if FREE_PLAYER_CAP <= overall < 80:    return SHOP_PRICE_70_80
    if 80 <= overall < 85:                 return SHOP_PRICE_80_85
    if 85 <= overall < 90:                 return SHOP_PRICE_85_90
    return SHOP_PRICE_90_PLUS


def unlock_player(db: Session, user_id: int, player_id: int):
    try:
        db.execute(
            text("CALL sp_unlock_player(:uid, :pid)"),
            {"uid": user_id, "pid": player_id}
        )
        db.commit()
        player_name = db.execute(
            text("SELECT short_name FROM players WHERE id = :id"), {"id": player_id}
        ).scalar()
        new_balance = db.execute(
            text("SELECT bb_balance FROM users WHERE id = :id"), {"id": user_id}
        ).scalar()
        return {"message": f"Successfully unlocked {player_name}", "new_balance": new_balance}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=_pg_error_msg(e))


# ── BATTLE ────────────────────────────────────────────────────────────────────

def get_battle_users_from_db(db: Session, current_user_id: int):
    rows = db.execute(
        text("SELECT * FROM v_battle_eligible_users WHERE id != :uid"),
        {"uid": current_user_id}
    ).all()

    if not rows:
        return [], set(), set()

    users_with_teams   = {r.id for r in rows if r.has_dream_team}
    users_with_players = {r.id for r in rows if r.has_custom_player}
    return rows, users_with_teams, users_with_players
