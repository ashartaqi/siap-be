import os
import pandas as pd
from app.core.db import SessionLocal
from app.models import Match, Club

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
    
    print(df)

# python3 -m app.ai_models.match_score
if __name__ == "__main__":
    compile_model()
