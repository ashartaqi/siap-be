from difflib import SequenceMatcher
from app.core.db import SessionLocal
from app.models import Club

TEAM_LOGOS = {
    # Premier League
    "Arsenal FC": "https://media.api-sports.io/football/teams/42.png",
    "Manchester City": "https://media.api-sports.io/football/teams/50.png",
    "Manchester United": "https://media.api-sports.io/football/teams/33.png",
    "Aston Villa": "https://media.api-sports.io/football/teams/66.png",
    "Liverpool FC": "https://media.api-sports.io/football/teams/40.png",
    "Chelsea FC": "https://media.api-sports.io/football/teams/49.png",
    "Brentford FC": "https://media.api-sports.io/football/teams/55.png",
    "Everton FC": "https://media.api-sports.io/football/teams/45.png",
    "Fulham FC": "https://media.api-sports.io/football/teams/36.png",
    "Brighton": "https://media.api-sports.io/football/teams/51.png",
    "Bournemouth": "https://media.api-sports.io/football/teams/35.png",
    "Sunderland": "https://media.api-sports.io/football/teams/43.png",
    "Newcastle United": "https://media.api-sports.io/football/teams/34.png",
    "Crystal Palace": "https://media.api-sports.io/football/teams/52.png",
    "Leeds United": "https://media.api-sports.io/football/teams/63.png",
    "Nottingham Forest": "https://media.api-sports.io/football/teams/65.png",
    "West Ham United": "https://media.api-sports.io/football/teams/48.png",
    "Tottenham Hotspur": "https://media.api-sports.io/football/teams/47.png",
    "Burnley FC": "https://media.api-sports.io/football/teams/44.png",
    "Wolverhampton": "https://media.api-sports.io/football/teams/39.png",

    # La Liga
    "FC Barcelona": "https://media.api-sports.io/football/teams/529.png",
    "Real Madrid": "https://media.api-sports.io/football/teams/541.png",
    "Villarreal CF": "https://media.api-sports.io/football/teams/533.png",
    "Atletico Madrid": "https://media.api-sports.io/football/teams/530.png",
    "Real Betis": "https://media.api-sports.io/football/teams/543.png",
    "Celta Vigo": "https://media.api-sports.io/football/teams/538.png",
    "Real Sociedad": "https://media.api-sports.io/football/teams/548.png",
    "Getafe CF": "https://media.api-sports.io/football/teams/546.png",
    "CA Osasuna": "https://media.api-sports.io/football/teams/727.png",
    "Espanyol": "https://media.api-sports.io/football/teams/532.png",
    "Athletic Bilbao": "https://media.api-sports.io/football/teams/531.png",
    "Girona FC": "https://media.api-sports.io/football/teams/547.png",
    "Rayo Vallecano": "https://media.api-sports.io/football/teams/728.png",
    "Valencia CF": "https://media.api-sports.io/football/teams/532.png",
    "Deportivo Alaves": "https://media.api-sports.io/football/teams/542.png",
    "RCD Mallorca": "https://media.api-sports.io/football/teams/798.png",
    "Sevilla FC": "https://media.api-sports.io/football/teams/536.png",

    # Bundesliga
    "Bayern Munich": "https://media.api-sports.io/football/teams/157.png",
    "Borussia Dortmund": "https://media.api-sports.io/football/teams/165.png",
    "RB Leipzig": "https://media.api-sports.io/football/teams/173.png",
    "VfB Stuttgart": "https://media.api-sports.io/football/teams/172.png",
    "TSG Hoffenheim": "https://media.api-sports.io/football/teams/167.png",
    "Bayer Leverkusen": "https://media.api-sports.io/football/teams/168.png",
    "Eintracht Frankfurt": "https://media.api-sports.io/football/teams/169.png",
    "SC Freiburg": "https://media.api-sports.io/football/teams/160.png",
    "FSV Mainz": "https://media.api-sports.io/football/teams/164.png",
    "FC Augsburg": "https://media.api-sports.io/football/teams/170.png",
    "Union Berlin": "https://media.api-sports.io/football/teams/182.png",
    "Hamburger SV": "https://media.api-sports.io/football/teams/163.png",
    "Borussia M'gladbach": "https://media.api-sports.io/football/teams/163.png",
    "Werder Bremen": "https://media.api-sports.io/football/teams/162.png",
    "1. FC Cologne": "https://media.api-sports.io/football/teams/192.png",

    # Serie A
    "Inter Milan": "https://media.api-sports.io/football/teams/505.png",
    "SSC Napoli": "https://media.api-sports.io/football/teams/492.png",
    "AC Milan": "https://media.api-sports.io/football/teams/489.png",
    "Juventus": "https://media.api-sports.io/football/teams/496.png",
    "AS Roma": "https://media.api-sports.io/football/teams/497.png",
    "Atalanta BC": "https://media.api-sports.io/football/teams/499.png",
    "Bologna FC": "https://media.api-sports.io/football/teams/500.png",
    "Lazio Rome": "https://media.api-sports.io/football/teams/487.png",
    "Udinese": "https://media.api-sports.io/football/teams/494.png",
    "Torino FC": "https://media.api-sports.io/football/teams/503.png",
    "Fiorentina": "https://media.api-sports.io/football/teams/502.png",
    "Cagliari": "https://media.api-sports.io/football/teams/490.png",

    # Ligue 1
    "Paris Saint-Germain": "https://media.api-sports.io/football/teams/85.png",
    "RC Lens": "https://media.api-sports.io/football/teams/116.png",
    "Olympique Marseille": "https://media.api-sports.io/football/teams/81.png",
    "Lille OSC": "https://media.api-sports.io/football/teams/79.png",
    "AS Monaco": "https://media.api-sports.io/football/teams/91.png",
    "Olympique Lyon": "https://media.api-sports.io/football/teams/80.png",
    "Stade Rennais": "https://media.api-sports.io/football/teams/111.png",
    "Strasbourg": "https://media.api-sports.io/football/teams/95.png",
    "Toulouse FC": "https://media.api-sports.io/football/teams/96.png",
    "Stade Brest": "https://media.api-sports.io/football/teams/130.png",
    "OGC Nice": "https://media.api-sports.io/football/teams/84.png",
    "FC Nantes": "https://media.api-sports.io/football/teams/83.png",
}

MATCH_THRESHOLD = 0.75


def normalize(name: str) -> str:
    if not name:
        return ""
    return (
        name.lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", " ")
        .strip()
    )


def best_match(db_name: str, candidates: dict) -> tuple[str, float]:
    norm_db = normalize(db_name)
    best_key = None
    best_score = 0.0
    for logo_name in candidates:
        score = SequenceMatcher(None, norm_db, normalize(logo_name)).ratio()
        if score > best_score:
            best_score = score
            best_key = logo_name
    return best_key, best_score


def update_logos():
    db = SessionLocal()
    updated = 0
    skipped = 0
    try:
        clubs = db.query(Club).all()
        for club in clubs:
            match_name, score = best_match(club.name, TEAM_LOGOS)
            if match_name and score >= MATCH_THRESHOLD:
                club.logo_url = TEAM_LOGOS[match_name]
                updated += 1
                print(f"[OK] {club.name!r} -> {match_name!r} (score={score:.2f})")
            else:
                skipped += 1
                print(f"[SKIP] {club.name!r} (best={match_name!r}, score={score:.2f})")

        db.commit()
        print(f"\nDone. Updated: {updated}, Skipped: {skipped}")

    except Exception as e:
        db.rollback()
        print("Error:", e)
    finally:
        db.close()


if __name__ == "__main__":
    # run: python3 -m app.scripts.db_populate.update_club_logos
    update_logos()
