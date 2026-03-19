import pandas as pd
from app.core.db import SessionLocal
from app.models import Player, Goalkeeper, Club
import os

CSV_FILE_TEAMS = os.path.join(os.path.dirname(__file__), "male_teams.csv")
COLUMNS_TEAMS = [
    "team_id",
    "team_name",
    "league_name",
    "nationality_name",
    "overall",
    "attack",
    "midfield",
    "defence",
    "home_stadium",
    "captain"
]

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
    "goalkeeping_diving",
    "goalkeeping_handling",
    "goalkeeping_kicking",
    "goalkeeping_positioning",
    "goalkeeping_reflexes",
    "goalkeeping_speed",
    "player_face_url",
]

def safe_int(value):
    """Convert value to int if possible, otherwise None."""
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (ValueError, TypeError):
        return None

def import_teams():
    db = SessionLocal()
    try:
        df = pd.read_csv(CSV_FILE_TEAMS, usecols=COLUMNS_TEAMS)
        df = df.drop_duplicates(subset="team_id", keep="first")

        chunk_size = 10000
        total_inserted = 0

        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            teams_data = []

            for row in chunk.to_dict(orient="records"):
                teams_data.append({
                    "id": safe_int(row.get("team_id")),
                    "name": row.get("team_name"),
                    "league_name": row.get("league_name"),
                    "nationality_name": row.get("nationality_name"),
                    "overall": safe_int(row.get("overall")),
                    "attack": safe_int(row.get("attack")),
                    "midfield": safe_int(row.get("midfield")),
                    "defence": safe_int(row.get("defence")),
                    "home_stadium": row.get("home_stadium"),
                    "captain": row.get("captain"),
                })

            db.bulk_insert_mappings(Club, teams_data)
            db.commit()

            total_inserted += len(teams_data)
            print(f"Inserted {total_inserted} rows so far")

        print(f"Finished inserting {total_inserted} rows")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()

def import_players():
    """Import all non-goalkeepers into Player table."""
    db = SessionLocal()
    chunk_size = 10000
    total_inserted = 0

    try:
        for df in pd.read_csv(CSV_FILE, usecols=COLUMNS, chunksize=chunk_size):
            players = []
            for row in df.to_dict(orient="records"):
                positions = row.get("player_positions", "")
                if "GK" in positions:  # skip goalkeepers
                    continue

                player = Player(
                    short_name=row.get("short_name"),
                    long_name=row.get("long_name"),
                    player_positions=positions,
                    overall=safe_int(row.get("overall")),
                    age=safe_int(row.get("age")),
                    dob=row.get("dob"),
                    height_cm=safe_int(row.get("height_cm")),
                    weight_kg=safe_int(row.get("weight_kg")),
                    club_team_id=safe_int(row.get("club_team_id")),
                    club_name=row.get("club_name"),
                    nationality_id=safe_int(row.get("nationality_id")),
                    nationality_name=row.get("nationality_name"),
                    preferred_foot=row.get("preferred_foot"),
                    weak_foot=safe_int(row.get("weak_foot")),
                    skill_moves=safe_int(row.get("skill_moves")),
                    work_rate=row.get("work_rate"),
                    pace=safe_int(row.get("pace")),
                    shooting=safe_int(row.get("shooting")),
                    passing=safe_int(row.get("passing")),
                    dribbling=safe_int(row.get("dribbling")),
                    defending=safe_int(row.get("defending")),
                    physic=safe_int(row.get("physic")),
                    player_face_url=row.get("player_face_url")
                )
                players.append(player)

            db.bulk_save_objects(players)
            db.commit()
            total_inserted += len(players)
            print(f"Inserted {total_inserted} non-GK players so far")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()

def import_goalkeepers():
    """Import all goalkeepers into Goalkeeper table."""
    db = SessionLocal()
    chunk_size = 10000
    total_inserted = 0

    try:
        for df in pd.read_csv(CSV_FILE, usecols=COLUMNS, chunksize=chunk_size):
            gks = []
            for row in df.to_dict(orient="records"):
                positions = row.get("player_positions", "")
                if "GK" not in positions:
                    continue

                gk = Goalkeeper(
                    short_name=row.get("short_name"),
                    long_name=row.get("long_name"),
                    player_positions=positions,
                    overall=safe_int(row.get("overall")),
                    age=safe_int(row.get("age")),
                    dob=row.get("dob"),
                    height_cm=safe_int(row.get("height_cm")),
                    weight_kg=safe_int(row.get("weight_kg")),
                    club_team_id=safe_int(row.get("club_team_id")),
                    club_name=row.get("club_name"),
                    nationality_id=safe_int(row.get("nationality_id")),
                    nationality_name=row.get("nationality_name"),
                    preferred_foot=row.get("preferred_foot"),
                    weak_foot=safe_int(row.get("weak_foot")),
                    skill_moves=safe_int(row.get("skill_moves")),
                    work_rate=row.get("work_rate"),
                    goalkeeping_diving=safe_int(row.get("goalkeeping_diving")),
                    goalkeeping_handling=safe_int(row.get("goalkeeping_handling")),
                    goalkeeping_kicking=safe_int(row.get("goalkeeping_kicking")),
                    goalkeeping_positioning=safe_int(row.get("goalkeeping_positioning")),
                    goalkeeping_reflexes=safe_int(row.get("goalkeeping_reflexes")),
                    goalkeeping_speed=safe_int(row.get("goalkeeping_speed")),
                    player_face_url=row.get("player_face_url")
                )
                gks.append(gk)

            db.bulk_save_objects(gks)
            db.commit()
            total_inserted += len(gks)
            print(f"Inserted {total_inserted} goalkeepers so far")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()

if __name__ == "__main__":
    #run the script - python3 -m app.scripts.transfer_data
    import_teams()
    import_players()
    import_goalkeepers()