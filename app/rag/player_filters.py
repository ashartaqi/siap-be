from datetime import date
import unicodedata
import difflib
import re
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.models import Player, PlayerStats, GoalkeeperStats, PlayerPos, Club

VALID_POSITIONS = {"CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST", "GK"}

GK_SORT_FIELDS = {"diving", "handling", "kicking", "positioning", "reflexes", "speed"}
PLAYER_SORT_FIELDS = {"overall", "pace", "shooting", "passing", "dribbling", "defending", "physic"}

# Cached at module level -- rebuilt once per process, not once per request.
# Same tradeoff as the club-name cache in extraction_heuristic.py: a small
# amount of staleness risk (new players added mid-session won't be in the
# fuzzy-match candidate list until restart) in exchange for avoiding a
# fresh query on every name lookup.
_all_short_names_cache: list[str] | None = None


def _strip_accents(text: str) -> str:
    """Removes diacritics (accents) from text, e.g. 'Mbappé' -> 'Mbappe'.
    Uses stdlib unicodedata -- no new dependency needed."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _get_all_short_names(db: Session) -> list[str]:
    global _all_short_names_cache
    if _all_short_names_cache is None:
        _all_short_names_cache = [
            p.short_name for p in db.query(Player.short_name).all() if p.short_name
        ]
    return _all_short_names_cache


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
    overfetch_limit = top_k * 3
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

def _strip_name_prefix(short_name: str) -> str:
    """Strips a leading 'X. ' initial-prefix from a short_name for fuzzy
    matching purposes, e.g. 'L. Messi' -> 'Messi'. Falls back to the
    original string if no such prefix pattern is found."""
    match = re.match(r"^[A-Z]\.\s*(.+)$", short_name)
    return match.group(1) if match else short_name


def find_player_name_matches(db: Session, name: str) -> list[Player]:
    """Finds players matching the given name. Two-layer strategy:

    1. Whole-word, accent-insensitive substring match against short_name,
       then long_name. Using word boundaries (not raw substring) avoids
       matching a fragment buried inside an unrelated word (e.g. "Mesi"
       inside "Damesio") while still correctly matching a real name that
       appears as one word within a longer short_name (e.g. "Ronaldo"
       within "Cristiano Ronaldo").
    2. If no whole-word match is found at all, fall back to fuzzy
       matching (typo tolerance) against short names with any "X. "
       initial-prefix stripped first, for genuine misspellings where no
       real word matches literally (e.g. "Renaldo", "Mesi", "Halaand").
    """
    stripped_query = _strip_accents(name).lower()
    word_pattern = re.compile(rf"\b{re.escape(stripped_query)}\b")

    all_players = db.query(Player).filter(Player.short_name.isnot(None)).all()

    short_name_matches = [
        p for p in all_players
        if word_pattern.search(_strip_accents(p.short_name).lower())
    ]
    if short_name_matches:
        return sorted(short_name_matches, key=lambda p: p.overall, reverse=True)[:10]

    long_name_matches = [
        p for p in all_players
        if p.long_name and word_pattern.search(_strip_accents(p.long_name).lower())
    ]
    if long_name_matches:
        return sorted(long_name_matches, key=lambda p: p.overall, reverse=True)[:10]

    # Fallback: fuzzy matching for genuine typos, no whole-word match found.
    all_short_names = _get_all_short_names(db)
    stripped_to_real: dict[str, list[str]] = {}
    for real_name in all_short_names:
        stripped = _strip_name_prefix(real_name)
        stripped_to_real.setdefault(stripped, []).append(real_name)

    close_stripped_matches = difflib.get_close_matches(
        name, list(stripped_to_real.keys()), n=10, cutoff=0.7
    )
    if close_stripped_matches:
        real_matches = [
            real for stripped in close_stripped_matches
            for real in stripped_to_real[stripped]
        ]
        fuzzy_players = (
            db.query(Player)
            .filter(Player.short_name.in_(real_matches))
            .order_by(Player.overall.desc())
            .all()
        )
        return fuzzy_players[:10]

    return []