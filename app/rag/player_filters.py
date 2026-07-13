from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import Player, PlayerStats, GoalkeeperStats, PlayerPos


VALID_POSITIONS = {"CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST", "GK"}


def _age_bounds_to_dob_range(age_min: int | None, age_max: int | None):
    """Convert an age range into a dob range.
    Older age requirement -> dob must be further in the past (smaller date).
    """
    today = date.today()
    max_dob = None  # player at least age_min -> dob <= this
    min_dob = None  # player at most age_max -> dob >= this

    if age_min is not None:
        max_dob = today.replace(year=today.year - age_min)
    if age_max is not None:
        min_dob = today.replace(year=today.year - age_max - 1)

    return min_dob, max_dob


def build_filtered_player_ids(db: Session, constraints: dict) -> list[int] | None:
    """
    Returns matching player IDs, or None if no usable structured constraints
    were found — signals the caller to fall back to pure vector search.
    """
    if not constraints:
        return None

    query = db.query(Player.id)
    filters_applied = False

    age_min = constraints.get("age_min")
    age_max = constraints.get("age_max")
    if age_min is not None or age_max is not None:
        min_dob, max_dob = _age_bounds_to_dob_range(age_min, age_max)
        if max_dob is not None:
            query = query.filter(Player.dob <= max_dob)
            filters_applied = True
        if min_dob is not None:
            query = query.filter(Player.dob >= min_dob)
            filters_applied = True

    if constraints.get("preferred_foot"):
        query = query.filter(Player.preferred_foot.ilike(constraints["preferred_foot"]))
        filters_applied = True

    if constraints.get("nationality"):
        query = query.filter(Player.nationality_name.ilike(f"%{constraints['nationality']}%"))
        filters_applied = True

    if constraints.get("overall_min") is not None:
        query = query.filter(Player.overall >= constraints["overall_min"])
        filters_applied = True
    if constraints.get("overall_max") is not None:
        query = query.filter(Player.overall <= constraints["overall_max"])
        filters_applied = True

    positions = constraints.get("positions")
    if positions:
        positions = [p for p in positions if p in VALID_POSITIONS]
    if positions:
        query = query.join(PlayerPos, PlayerPos.player_id == Player.id)
        query = query.filter(PlayerPos.position.in_(positions))
        filters_applied = True

    stats = constraints.get("stats") or {}
    if stats:
        query = query.join(PlayerStats, PlayerStats.player_id == Player.id)
        stat_filters = [
            getattr(PlayerStats, name) >= stats[f"{name}_min"]
            for name in ("pace", "shooting", "passing", "dribbling", "defending", "physic")
            if stats.get(f"{name}_min") is not None
        ]
        if stat_filters:
            query = query.filter(and_(*stat_filters))
            filters_applied = True

    gk_stats = constraints.get("goalkeeper_stats") or {}
    if gk_stats:
        query = query.join(GoalkeeperStats, GoalkeeperStats.player_id == Player.id)
        gk_filters = [
            getattr(GoalkeeperStats, name) >= gk_stats[f"{name}_min"]
            for name in ("diving", "handling", "kicking", "positioning", "reflexes", "speed")
            if gk_stats.get(f"{name}_min") is not None
        ]
        if gk_filters:
            query = query.filter(and_(*gk_filters))
            filters_applied = True

    if not filters_applied:
        return None

    return [row.id for row in query.distinct().all()]