import requests
from app.core.db import SessionLocal
from app.models import Match

CHUNK_SIZE = 100
BASE_RAW = "https://raw.githubusercontent.com/openfootball/football.json/master"
BASE_API = "https://api.github.com/repos/openfootball/football.json/contents"

SEASONS = [
    "2010-11", "2011-12", "2012-13", "2013-14", "2014-15",
    "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
    "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"
]


def get_files_in_season(season):
    url = f"{BASE_API}/{season}"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    files = response.json()
    return [f["name"] for f in files if f["name"].endswith(".json")]


def determine_winner(team1, team2, ft):
    if ft[0] > ft[1]:
        return team1
    elif ft[1] > ft[0]:
        return team2
    else:
        return "draw"


def get_team_name(team):
    if isinstance(team, dict):
        return team.get("name", "Unknown")
    return team


def parse_matches_from_data(data):
    result = []
    if "matches" in data:
        for match in data["matches"]:
            result.append(match)
    elif "rounds" in data:
        for round_data in data["rounds"]:
            round_name = round_data.get("name", "NA")
            for match in round_data.get("matches", []):
                match["_round"] = round_name
                result.append(match)
    return result


def fetch_and_insert(db, url, label, total_inserted):
    response = requests.get(url)

    if response.status_code != 200:
        print(f"⚠️  Skipping {label} — not found ({response.status_code})")
        return total_inserted

    try:
        data = response.json()
    except Exception:
        print(f"⚠️  Skipping {label} — invalid JSON")
        return total_inserted

    matches = parse_matches_from_data(data)

    if not matches:
        print(f"⚠️  Skipping {label} — no matches found")
        return total_inserted

    # Extract league name from label e.g. "2024-25/uefa.cl.json" -> "uefa.cl"
    league = label.split("/")[1].replace(".json", "")

    chunk = []
    for match in matches:
        team1 = get_team_name(match.get("team1", "Unknown"))
        team2 = get_team_name(match.get("team2", "Unknown"))

        if "score" in match and "ft" in match["score"]:
            ft = match["score"]["ft"]
            score_str = f"{ft[0]}-{ft[1]}"
            winner = determine_winner(team1, team2, ft)
        else:
            score_str = None
            winner = None

        round_name = match.get("round") or match.get("_round", None)

        chunk.append(Match(
            round=round_name,
            date=match.get("date", None),
            time=match.get("time", None),
            team1=team1,
            team2=team2,
            score_ft=score_str,
            winner=winner,
            league=league
        ))

        if len(chunk) >= CHUNK_SIZE:
            db.bulk_save_objects(chunk)
            db.commit()
            total_inserted += len(chunk)
            print(f"  Inserted {total_inserted} rows so far...")
            chunk.clear()

    if chunk:
        db.bulk_save_objects(chunk)
        db.commit()
        total_inserted += len(chunk)
        chunk.clear()

    print(f"✅ Done: {label}")
    return total_inserted


def import_matches():
    db = SessionLocal()
    total_inserted = 0

    for season in SEASONS:
        print(f"\n📂 Processing season: {season}")
        files = get_files_in_season(season)

        if not files:
            print(f"⚠️  No files found for season {season}")
            continue

        print(f"   Found files: {files}")

        for filename in files:
            url = f"{BASE_RAW}/{season}/{filename}"
            label = f"{season}/{filename}"
            total_inserted = fetch_and_insert(db, url, label, total_inserted)

    db.close()
    print(f"\n🎉 All done! Total inserted: {total_inserted}")


if __name__ == "__main__":
    # run the file - python3 -m app.scripts.transfer_matches
    import_matches()