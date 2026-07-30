from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.models import Player, PlayerStats, GoalkeeperStats, PlayerPos, Club

VALID_POSITIONS = {"CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST", "GK"}

GK_SORT_FIELDS = {"diving", "handling", "kicking", "positioning", "reflexes", "speed"}
PLAYER_SORT_FIELDS = {"overall", "pace", "shooting", "passing", "dribbling", "defending", "physic"}


def _age_bounds_to_dob_range(age_min: int | None, age_max: int | None):
    today = date.today()
    max_dob = None
    min_dob = None
    if age_min is not None:
        max_dob = today.replace(year=today.year - age_min)
    if age_max is not None:
        min_dob = today.replace(year=today.year - age_max - 1)
    return min_dob, max_dob


def _apply_shared_filters(query, constraints: dict) -> tuple:
    """Applies filters common to the ID-list, ranking, and aggregation paths.
    Returns (query, filters_applied: bool)."""
    filters_applied = False
    club_joined = False

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

    if constraints.get("club"):
        if not club_joined:
            query = query.join(Club, Club.id == Player.club_team_id)
            club_joined = True
        query = query.filter(Club.name.ilike(f"%{constraints['club']}%"))
        filters_applied = True

    if constraints.get("league"):
        if not club_joined:
            query = query.join(Club, Club.id == Player.club_team_id)
            club_joined = True
        query = query.filter(Club.league_name == constraints["league"])
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

    return query, filters_applied


def build_filtered_player_ids(db: Session, constraints: dict) -> list[int] | None:
    """
    Returns matching player IDs, or None if no usable structured constraints
    were found — signals the caller to fall back to pure vector search.
    """
    if not constraints:
        return None

    query = db.query(Player.id)
    query, filters_applied = _apply_shared_filters(query, constraints)

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


def build_ranked_player_ids(db: Session, constraints: dict, top_k: int = 5) -> list[int] | None:
    """
    Handles sort_by queries ("best reflexes", "fastest strikers"): applies any
    hard filters, then sorts directly in SQL and returns the top_k IDs.
    Returns None if there's no sort_by — signals caller to use the normal path.
    """
    sort_by = constraints.get("sort_by")
    if not sort_by:
        return None

    direction = desc if constraints.get("sort_direction", "desc") == "desc" else asc

    query = db.query(Player.id)
    query, _ = _apply_shared_filters(query, constraints)

    if sort_by in GK_SORT_FIELDS:
        query = query.join(GoalkeeperStats, GoalkeeperStats.player_id == Player.id)
        query = query.order_by(direction(getattr(GoalkeeperStats, sort_by)))
    elif sort_by in PLAYER_SORT_FIELDS:
        if sort_by == "overall":
            query = query.order_by(direction(Player.overall))
        else:
            query = query.join(PlayerStats, PlayerStats.player_id == Player.id)
            query = query.order_by(direction(getattr(PlayerStats, sort_by)))
    else:
        return None

    # A multi-position filter can cause the PlayerPos join to return the
    # same player multiple times (once per matching position). Postgres's
    # SELECT DISTINCT requires ORDER BY columns to be in the SELECT list,
    # which conflicts with sorting by a joined stat column -- so dedupe
    # in Python instead, over-fetching to compensate for potential
    # duplicates before trimming to top_k.
    overfetch_limit = top_k * 3  # generous margin; a player has at most a
                                  # few positions, so 3x is safely enough
    raw_ids = [row.id for row in query.limit(overfetch_limit).all()]

    deduped_ids = []
    seen = set()
    for pid in raw_ids:
        if pid not in seen:
            seen.add(pid)
            deduped_ids.append(pid)
        if len(deduped_ids) == top_k:
            break

    return deduped_ids


def find_player_name_matches(db: Session, name: str) -> list[Player]:
    """Finds players matching the given name. Tries short_name first
    (handles single distinctive names like "Messi", "Ronaldo", "Mbappé").
    Falls back to long_name for fuller names like "Kylian Mbappé" that
    won't appear in a "K. Mbappé"-style short_name."""
    pattern = f"%{name}%"

    matches = (
        db.query(Player)
        .filter(Player.short_name.ilike(pattern))
        .order_by(Player.overall.desc())
        .limit(10)
        .all()
    )
    if matches:
        return matches

    return (
        db.query(Player)
        .filter(Player.long_name.ilike(pattern))
        .order_by(Player.overall.desc())
        .limit(10)
        .all()
    )