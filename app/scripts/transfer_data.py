import pandas as pd
from app.core.db import SessionLocal
from app.models import Player
import os

CSV_FILE = os.path.join(os.path.dirname(__file__), "male_players.csv")
COLUMNS = [
    "short_name",
    "long_name",
    "player_positions",
    "overall",
    "age",
    "dob",
    "height_cm",
    "weight_kg",
    "club_team_id",
    "club_name",
    "nationality_id",
    "nationality_name",
    "preferred_foot",
    "weak_foot",
    "skill_moves",
    "work_rate",
    "pace",
    "shooting",
    "passing",
    "dribbling",
    "defending",
    "physic",
    "player_face_url",
]

def safe_int(value):
    """Convert value to int if possible, otherwise None."""
    if pd.isna(value):
        return None
    return int(value)

def import_players():
    db = SessionLocal()
    try:
        df = pd.read_csv(
            CSV_FILE,
            usecols=COLUMNS,
            nrows=10
        )

        players = []
        for _, row in df.iterrows():
            player = Player(
                short_name=row.get("short_name", None),
                long_name=row.get("long_name", None),
                player_positions=row.get("player_positions", None),
                overall=safe_int(row.get("overall")),
                age=safe_int(row.get("age")),
                dob=row.get("dob", None),
                height_cm=safe_int(row.get("height_cm")),
                weight_kg=safe_int(row.get("weight_kg")),
                club_team_id=safe_int(row.get("club_team_id")),
                club_name=row.get("club_name", None),
                nationality_id=safe_int(row.get("nationality_id")),
                nationality_name=row.get("nationality_name", None),
                preferred_foot=row.get("preferred_foot", None),
                weak_foot=safe_int(row.get("weak_foot")),
                skill_moves=safe_int(row.get("skill_moves")),
                work_rate=row.get("work_rate", None),
                pace=safe_int(row.get("pace")),
                shooting=safe_int(row.get("shooting")),
                passing=safe_int(row.get("passing")),
                dribbling=safe_int(row.get("dribbling")),
                defending=safe_int(row.get("defending")),
                physic=safe_int(row.get("physic")),
                player_face_url=row.get("player_face_url", None)
            )
            db.add(player)

        db.commit()
        print(f"Inserted {len(players)} rows")

    finally:
        db.close()


if __name__ == "__main__":
    import_players()
