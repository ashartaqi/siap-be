from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from datetime import date
from app.models import Player, PlayerPos, PlayerStats, GoalkeeperStats, FavouritePlayers, UnlockedPlayer
from app.constants import FREE_PLAYER_CAP
from app.crud.users import create

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
            query = query.filter((Player.id.in_(unlocked_ids)) | (Player.overall < FREE_PLAYER_CAP))
        elif unlock_status == "locked":
            query = query.filter((Player.overall >= FREE_PLAYER_CAP) & (~Player.id.in_(unlocked_ids)))

    players = query.offset(skip).limit(limit).all()
    
    for p in players:
        p.is_unlocked = (p.id in unlocked_ids or p.overall < FREE_PLAYER_CAP) if user_id else True
        
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
