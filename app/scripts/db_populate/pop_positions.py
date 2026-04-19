from app.core.db import SessionLocal
from app.models import Player, PlayerPos


def populate_positions():
    db = SessionLocal()
    batch_size = 500
    offset = 0

    while True:
        players = db.query(Player).filter(
            Player.player_positions != None
        ).offset(offset).limit(batch_size).all()

        if not players:
            break

        for player in players:
            if not player.player_positions or not player.player_positions.strip():
                continue
            positions = [p.strip() for p in player.player_positions.split(",")]
            for pos in positions:
                if pos:
                    db.merge(PlayerPos(player_id=player.id, position=pos))

        db.commit()
        print(f"Processed {offset + len(players)} players...")
        offset += batch_size

    print("Done")

# if __name__ == "__main__":
    # run the script - python3 -m app.scripts.db_populate.Pop_Positions
    # populate_positions()