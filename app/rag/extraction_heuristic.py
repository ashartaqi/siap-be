import re

from app.rag.player_filters import VALID_POSITIONS

SORT_WORDS = {
    "best", "top", "fastest", "highest", "most", "worst", "lowest",
    "quickest", "slowest", "greatest", "strongest", "weakest",
    "fast", "high", "quick", "strong", "great", "good", "young", "old",
}

AGGREGATION_PHRASES = (
    "how many", "average", "count of", "which league", "which club",
    "which nationality", "which team", "total number",
)

COMPARISON_WORDS = {"compare", "vs", "versus", "comparing"}

FOOT_WORDS = {"left-footed", "right-footed", "left foot", "right foot"}

POSITION_PROSE_WORDS = {
    "striker", "strikers", "forward", "forwards",
    "midfielder", "midfielders", "midfield",
    "defender", "defenders", "defence", "defense",
    "goalkeeper", "goalkeepers", "keeper", "keepers",
    "winger", "wingers", "fullback", "fullbacks", "back",
}
# Common capitalized words that don't indicate a proper noun/player name --
# sentence-starters, common football vocabulary that's sometimes
# capitalized in casual writing, etc. Deliberately short and conservative;
# anything not in this list that looks like a proper noun triggers
# extraction, since missing a real player name is a worse failure than
# an unnecessary extraction call.
COMMON_CAPITALIZED_WORDS = {
    "who", "what", "which", "where", "when", "how", "why", "find", "show",
    "tell", "give", "list", "the", "a", "an", "is", "are", "does", "do",
    "i", "player", "players", "team", "club", "league",
    "explain", "describe", "compare", "define", "outline", "summarize",
    "discuss", "calculate", "rank", "sort", "name", "identify", "provide",
    "can", "could", "would", "should", "will", "please",
}


def get_known_club_names(db) -> set[str]:
    """Fetches club names once; caller is responsible for caching across
    calls if this is used in a hot path (see needs_constraint_extraction's
    club_names parameter)."""
    from app.models import Club
    return {c.name.lower() for c in db.query(Club.name).all() if c.name}


def _looks_like_proper_noun_phrase(question: str) -> bool:
    """Cheap proxy for 'this might contain a player/club/nationality name':
    any capitalized word that isn't common English. Deliberately loose --
    prefers false positives (unnecessary extraction) over false negatives
    (missing a real name)."""
    words = question.split()
    for word in words:
        cleaned = word.strip(".,!?'\"")
        if not cleaned:
            continue
        if cleaned[0].isupper() and cleaned.lower() not in COMMON_CAPITALIZED_WORDS:
            return True
    return False


def needs_constraint_extraction(question: str, known_club_names: set[str] | None = None) -> bool:
    q_lower = question.lower()

    if re.search(r"\d", question):
        return True

    for pos in VALID_POSITIONS:
        if re.search(rf"\b{pos}\b", question):
            return True

    words_lower = set(q_lower.split())
    if words_lower & POSITION_PROSE_WORDS:
        return True

    if any(fw in q_lower for fw in FOOT_WORDS):
        return True

    if words_lower & SORT_WORDS:
        return True

    if any(phrase in q_lower for phrase in AGGREGATION_PHRASES):
        return True

    if words_lower & COMPARISON_WORDS:
        return True

    if known_club_names:
        for club in known_club_names:
            if club in q_lower:
                return True

    if _looks_like_proper_noun_phrase(question):
        return True

    return False