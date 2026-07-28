from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Player, PlayerStats, GoalkeeperStats, Club
from app.rag.player_filters import _apply_shared_filters

VALID_AGG_TYPES = {"count", "avg", "max", "min", "sum"}
VALID_GROUP_BY = {"league_name", "nationality_name", "club_name", "position", "preferred_foot"}

PLAYER_STAT_FIELDS = {"pace", "shooting", "passing", "dribbling", "defending", "physic"}
GK_STAT_FIELDS = {"diving", "handling", "kicking", "positioning", "reflexes", "speed"}


def _resolve_field_column(field: str):
    """Returns the SQLAlchemy column for a stat field, or None if not a valid stat."""
    if field == "overall":
        return Player.overall
    if field in PLAYER_STAT_FIELDS:
        return getattr(PlayerStats, field)
    if field in GK_STAT_FIELDS:
        return getattr(GoalkeeperStats, field)
    return None


def run_aggregation(db: Session, constraints: dict) -> dict | None:
    """
    Executes an aggregation query based on extracted constraints.
    Returns a dict of results, or None if there's no usable aggregation intent.
    """
    agg = constraints.get("aggregation")
    if not agg or agg.get("type") not in VALID_AGG_TYPES:
        return None

    agg_type = agg["type"]
    field = agg.get("field")
    group_by = agg.get("group_by")

    if group_by and group_by not in VALID_GROUP_BY:
        group_by = None

    if agg_type == "count":
        # distinct() guards against double-counting when a multi-position
        # filter (e.g. "midfielders or forwards") causes the PlayerPos join
        # to fan out one row per matching position for the same player.
        agg_expr = func.count(func.distinct(Player.id))
    else:
        if not field:
            return None  # avg/max/min/sum require a field
        column = _resolve_field_column(field)
        if column is None:
            return None
        agg_func = {"avg": func.avg, "max": func.max, "min": func.min, "sum": func.sum}[agg_type]
        agg_expr = agg_func(column)

    needs_player_stats = field in PLAYER_STAT_FIELDS if field else False
    needs_gk_stats = field in GK_STAT_FIELDS if field else False

    # Build the base query -- select only columns that are valid for this
    # grouping level (Postgres requires every non-aggregated SELECT column
    # to also appear in GROUP BY). When there's no group_by, explicitly
    # anchor the query with select_from(Player), since a bare aggregate
    # expression gives SQLAlchemy no entity to join from later.
    if group_by == "league_name":
        query = db.query(Club.league_name, agg_expr).join(Player, Player.club_team_id == Club.id)
    elif group_by == "club_name":
        query = db.query(Club.name, Club.league_name, agg_expr).join(Player, Player.club_team_id == Club.id)
    elif group_by:
        group_column = getattr(Player, group_by)
        query = db.query(group_column, agg_expr)
    else:
        query = db.query(agg_expr).select_from(Player)

    # Apply the same hard-constraint filters used by the filter/sort paths
    # (position, preferred_foot, age, nationality, overall) so aggregation
    # respects the question's stated constraints instead of running over
    # the entire table.
    query, _ = _apply_shared_filters(query, constraints)

    if needs_player_stats:
        query = query.join(PlayerStats, PlayerStats.player_id == Player.id)
    if needs_gk_stats:
        query = query.join(GoalkeeperStats, GoalkeeperStats.player_id == Player.id)

    if group_by == "league_name":
        query = query.group_by(Club.league_name).order_by(agg_expr.desc())
    elif group_by == "club_name":
        query = query.group_by(Club.name, Club.league_name).order_by(agg_expr.desc())
    elif group_by:
        query = query.group_by(getattr(Player, group_by)).order_by(agg_expr.desc())

    if group_by:
        rows = query.limit(20).all()  # cap grouped results, avoid dumping every league/club
        return {
            "type": agg_type,
            "field": field,
            "group_by": group_by,
            "results": [tuple(row) for row in rows],
        }
    else:
        result = query.scalar()
        return {
            "type": agg_type,
            "field": field,
            "group_by": None,
            "results": result,
        }


def format_aggregation_context(agg_result: dict) -> str:
    """Turns a run_aggregation() result into a plain-text context string
    for generate_answer(), so aggregation answers follow the same
    'only from provided context' discipline as player-document answers."""
    agg_type = agg_result["type"]
    field = agg_result.get("field")
    group_by = agg_result.get("group_by")
    results = agg_result["results"]

    label = f"{agg_type}({field})" if field else agg_type

    if group_by is None:
        return f"Computed result: {label} across all matching players = {results}"

    lines = [f"Computed result: {label}, grouped by {group_by}:"]
    for row in results:
        # row is a tuple: (group_value, ..., agg_value) -- club queries include league_name too
        lines.append(" - " + ", ".join(str(v) for v in row))
    return "\n".join(lines)