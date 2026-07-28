from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import date
from app.models import Player, PlayerPos
from app.rag.text_builders import calculate_age


def young_fast_strikers(db: Session, age_limit: int = 23, pace_min: int = 80, limit: int = 5):
    players = (
        db.query(Player)
        .join(Player.positions)
        .options(joinedload(Player.player_stats), joinedload(Player.positions))
        .filter(PlayerPos.position == "ST")
        .all()
    )
    results = [
        p for p in players
        if p.player_stats and p.player_stats.pace and p.player_stats.pace >= pace_min
        and calculate_age(p.dob) is not None and calculate_age(p.dob) <= age_limit
    ]
    results.sort(key=lambda p: p.player_stats.pace, reverse=True)
    return results[:limit]


def best_goalkeeper_reflexes(db: Session, limit: int = 5):
    from app.models import GoalkeeperStats
    players = (
        db.query(Player)
        .join(Player.goalkeeper_stats)
        .options(joinedload(Player.goalkeeper_stats))
        .order_by(GoalkeeperStats.reflexes.desc())
        .limit(limit)
        .all()
    )
    return players


def compare_players_by_name(db: Session, name1: str, name2: str):
    p1 = db.query(Player).filter(Player.short_name.ilike(f"%{name1}%")).options(joinedload(Player.player_stats)).first()
    p2 = db.query(Player).filter(Player.long_name.ilike("%Cristiano Ronaldo%")).options(joinedload(Player.player_stats)).first()
    return p1, p2


def best_left_footed_defenders(db: Session, limit: int = 5):
    players = (
        db.query(Player)
        .join(Player.positions)
        .options(joinedload(Player.player_stats), joinedload(Player.positions))
        .filter(PlayerPos.position.in_(["CB", "LB", "RB"]))
        .filter(Player.preferred_foot == "Left")
        .all()
    )
    results = [p for p in players if p.player_stats and p.player_stats.defending]
    results.sort(key=lambda p: p.player_stats.defending, reverse=True)
    return results[:limit]


def best_attacking_midfielders(db: Session, limit: int = 5):
    players = (
        db.query(Player)
        .join(Player.positions)
        .options(joinedload(Player.positions))
        .filter(PlayerPos.position == "CAM")
        .order_by(Player.overall.desc())
        .limit(limit)
        .all()
    )
    return players