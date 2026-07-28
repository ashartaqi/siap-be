from datetime import date
from app.models import Player

def calculate_age(dob) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def build_player_text(player: Player) -> str:
    positions = ", ".join(p.position for p in player.positions) if player.positions else "Unknown"
    club_name = player.club_name or "Free agent"
    age = calculate_age(player.dob)

    stats_line = ""
    if player.player_stats:
        s = player.player_stats
        stats_line = (
            f"Pace {s.pace}, shooting {s.shooting}, passing {s.passing}, "
            f"dribbling {s.dribbling}, defending {s.defending}, physical {s.physic}."
        )
    elif player.goalkeeper_stats:
        g = player.goalkeeper_stats
        stats_line = (
            f"Diving {g.diving}, handling {g.handling}, kicking {g.kicking}, "
            f"positioning {g.positioning}, reflexes {g.reflexes}, speed {g.speed}."
        )

    return (
        f"{player.long_name} ({player.short_name}), position(s): {positions}. "
        f"Plays for {club_name}. Overall rating {player.overall}. "
        f"Age {age if age is not None else 'unknown'}, "
        f"height {player.height_cm}cm, weight {player.weight_kg}kg. "
        f"Nationality: {player.nationality_name}. Preferred foot: {player.preferred_foot}. "
        f"Weak foot {player.weak_foot}/5, skill moves {player.skill_moves}/5, work rate {player.work_rate}. "
        f"{stats_line}"
    )