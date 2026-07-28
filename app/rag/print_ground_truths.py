from app.core.db import SessionLocal
from app.rag.eval_helpers import (
    young_fast_strikers, best_goalkeeper_reflexes,
    compare_players_by_name, best_left_footed_defenders,
    best_attacking_midfielders,
)
from app.rag.text_builders import calculate_age

if __name__ == "__main__":
    db = SessionLocal()
    try:
        print("=== Young fast strikers ===")
        for p in young_fast_strikers(db):
            print(f"{p.short_name}, age {calculate_age(p.dob)}, pace {p.player_stats.pace}")

        print("\n=== Best GK reflexes ===")
        for p in best_goalkeeper_reflexes(db):
            print(f"{p.short_name}, reflexes {p.goalkeeper_stats.reflexes}")

        print("\n=== Messi vs Ronaldo ===")
        p1, p2 = compare_players_by_name(db, "Messi", "Cristiano Ronaldo")
        if p1: print(f"{p1.short_name}: dribbling {p1.player_stats.dribbling}, passing {p1.player_stats.passing}")
        if p2: print(f"{p2.short_name}: dribbling {p2.player_stats.dribbling}, passing {p2.player_stats.passing}")

        print("\n=== Best left-footed defenders ===")
        for p in best_left_footed_defenders(db):
            print(f"{p.short_name}, defending {p.player_stats.defending}")

        print("\n=== Best CAMs ===")
        for p in best_attacking_midfielders(db):
            print(f"{p.short_name}, overall {p.overall}")
    finally:
        db.close()