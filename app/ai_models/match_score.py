import os
import pandas as pd
from app.core.db import SessionLocal
from app.models import Match, Club
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
import joblib

COLUMNS = [
    "team1",
    "team2",
    "winner",
    "team1_score",
    "team2_score"
]

STATS_COLS = [
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    "attack_diff", "mid_diff", "defense_diff", "overall_diff"
]

def fit_normalizer(df, save_dir="scalers"):
    os.makedirs(save_dir, exist_ok=True)

    df = df.copy()

    # Fit and save team encoder
    team_enc = LabelEncoder()
    team_enc.fit(pd.concat([df["team1"], df["team2"]]))
    joblib.dump(team_enc, f"{save_dir}/team_enc.pkl")

    # Fit and save winner encoder
    winner_enc = LabelEncoder()
    winner_enc.fit(df["winner"])
    joblib.dump(winner_enc, f"{save_dir}/winner_enc.pkl")

    # Fit and save score scaler
    score_scaler = MinMaxScaler()
    score_cols = ["team1_score", "team2_score"]
    score_scaler.fit(df[score_cols])
    joblib.dump(score_scaler, f"{save_dir}/score_scaler.pkl")

    # Fit and save stat scaler
    stat_cols = [c for c in df.columns if c not in ["team1", "team2", "winner"] + score_cols]
    stat_scaler = StandardScaler()
    stat_scaler.fit(df[stat_cols])
    joblib.dump(stat_scaler, f"{save_dir}/stat_scaler.pkl")

    print(f"Encoders saved. Known teams: {list(team_enc.classes_)}")


def normalize(df, save_dir="scalers"):
    df = df.copy()

    team_enc    = joblib.load(f"{save_dir}/team_enc.pkl")
    winner_enc  = joblib.load(f"{save_dir}/winner_enc.pkl")
    score_scaler = joblib.load(f"{save_dir}/score_scaler.pkl")
    stat_scaler  = joblib.load(f"{save_dir}/stat_scaler.pkl")

    score_cols = ["team1_score", "team2_score"]
    stat_cols  = [c for c in df.columns if c not in ["team1", "team2", "winner"] + score_cols]

    # Handle unseen teams gracefully
    known_teams = set(team_enc.classes_)
    for col in ["team1", "team2"]:
        unseen = set(df[col]) - known_teams
        if unseen:
            raise ValueError(f"Unknown teams in `{col}`: {unseen}. Add them to training data.")

    df["team1"]  = team_enc.transform(df["team1"])
    df["team2"]  = team_enc.transform(df["team2"])

    if "winner" in df.columns:
        df["winner"] = winner_enc.transform(df["winner"])

    if all(c in df.columns for c in score_cols):
        df[score_cols] = score_scaler.transform(df[score_cols])

    df[stat_cols] = stat_scaler.transform(df[stat_cols])

    return df

def load_data() -> pd.DataFrame:
    db = SessionLocal()
    matches = db.query(
        Match.team1,
        Match.team2,
        Match.winner,
        Match.team1_score,
        Match.team2_score
    ).filter(
        Match.league.in_(["en.1", "es.1", "de.1", "it.1", "fr.1"])
    ).all()
    df = pd.DataFrame(matches, columns=COLUMNS)
    
    return df


def add_club_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Fetching club stats and adding those to the dataframe"""
    db = SessionLocal()
    clubs = db.query(
        Club.name,
        Club.attack,
        Club.midfield,
        Club.defence,
        Club.overall
    ).all()
    clubs_df = pd.DataFrame(clubs, columns=["name", "attack", "midfield", "defence", "overall"])
    clubs_df = clubs_df.drop_duplicates(subset=["name"])
    
    df = df.merge(clubs_df, left_on="team1", right_on="name", how="left").drop(columns=["name"])
    df = df.rename(columns={"attack": "team1_attack", "midfield": "team1_mid", "defence": "team1_def", "overall": "team1_overall"})
    
    df = df.merge(clubs_df, left_on="team2", right_on="name", how="left").drop(columns=["name"])
    df = df.rename(columns={"attack": "team2_attack", "midfield": "team2_mid", "defence": "team2_def", "overall": "team2_overall"})
    
    df["attack_diff"] = abs(df["team1_attack"] - df["team2_attack"])
    df["mid_diff"] = abs(df["team1_mid"] - df["team2_mid"])
    df["defense_diff"] = abs(df["team1_def"] - df["team2_def"])
    df["overall_diff"] = abs(df["team1_overall"] - df["team2_overall"])

    df.dropna(subset=STATS_COLS[4:], inplace=True)
    df[STATS_COLS] = df[STATS_COLS].astype(int)
    
    return df


def compile_model():
    df = load_data()
    df = add_club_stats(df)
    fit_normalizer(df, save_dir="app/ai_models/compiled_models")
    df = normalize(df)
    
    print(df)

# python3 -m app.ai_models.match_score
if __name__ == "__main__":
    compile_model()
