"""
match_score.py
==============
Trains two sklearn models on historical match data:

  • GradientBoostingRegressor  → predicts team1_score and team2_score
  • RandomForestClassifier      → predicts outcome (win / draw / loss)
                                  from team1's perspective

Split: 80 % training / 20 % testing

Run:
    python3 -m app.ai_models.match_score
"""

import json
import os
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.core.db import SessionLocal
from app.models import Club, Match

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLUMNS: list[str] = ["team1", "team2", "winner", "team1_score", "team2_score"]

STATS_COLS: list[str] = [
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    "attack_diff",  "mid_diff",  "defense_diff", "overall_diff",
]

FEATURE_COLS: list[str] = [
    "team1_enc",    "team2_enc",
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    "attack_diff",  "mid_diff",  "defense_diff", "overall_diff",
]

LEAGUES: list[str] = ["en.1", "es.1", "de.1", "it.1", "fr.1"]

MODELS_DIR: str = os.path.join(os.path.dirname(__file__), "compiled_models")

# ---------------------------------------------------------------------------
# Lazy-loaded inference cache  (populated on first predict_match() call)
# ---------------------------------------------------------------------------

_team_enc:       Optional[LabelEncoder]            = None
_feature_scaler: Optional[StandardScaler]          = None
_score_reg_t1:   Optional[GradientBoostingRegressor] = None
_score_reg_t2:   Optional[GradientBoostingRegressor] = None
_outcome_clf:    Optional[RandomForestClassifier]  = None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Pull completed match rows from the DB for the top 5 leagues."""
    db = SessionLocal()
    try:
        rows = db.query(
            Match.team1,
            Match.team2,
            Match.winner,
            Match.team1_score,
            Match.team2_score,
        ).filter(
            Match.league.in_(LEAGUES)
        ).all()
    finally:
        db.close()

    return pd.DataFrame(rows, columns=COLUMNS)


def add_club_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Left-join club rating attributes for both teams and add diff features.
    Rows whose club stats cannot be resolved are dropped.
    """
    db = SessionLocal()
    try:
        clubs = db.query(
            Club.name,
            Club.attack,
            Club.midfield,
            Club.defence,
            Club.overall,
        ).all()
    finally:
        db.close()

    clubs_df = (
        pd.DataFrame(clubs, columns=["name", "attack", "midfield", "defence", "overall"])
        .drop_duplicates(subset=["name"])
    )

    # --- team1 stats ---
    df = df.merge(clubs_df, left_on="team1", right_on="name", how="left").drop(columns=["name"])
    df = df.rename(columns={
        "attack":   "team1_attack",
        "midfield": "team1_mid",
        "defence":  "team1_def",
        "overall":  "team1_overall",
    })

    # --- team2 stats ---
    df = df.merge(clubs_df, left_on="team2", right_on="name", how="left").drop(columns=["name"])
    df = df.rename(columns={
        "attack":   "team2_attack",
        "midfield": "team2_mid",
        "defence":  "team2_def",
        "overall":  "team2_overall",
    })

    # --- diff features ---
    df["attack_diff"]  = (df["team1_attack"]  - df["team2_attack"]).abs()
    df["mid_diff"]     = (df["team1_mid"]      - df["team2_mid"]).abs()
    df["defense_diff"] = (df["team1_def"]      - df["team2_def"]).abs()
    df["overall_diff"] = (df["team1_overall"]  - df["team2_overall"]).abs()

    df.dropna(subset=STATS_COLS, inplace=True)
    df[STATS_COLS] = df[STATS_COLS].astype(int)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _derive_outcome(df: pd.DataFrame) -> pd.DataFrame:
    """
    Encode match outcome from team1's perspective:
        1  → team1 wins
        0  → draw
       -1  → team1 loses

    Rows with a missing or blank winner are dropped before this function
    is called, so the fallback branch safely maps any non-team1, non-Draw
    winner to -1 (team2 won).
    """
    def _label(row: pd.Series) -> int:
        w = str(row["winner"]).strip()
        if w == row["team1"]:
            return 1
        if w.lower() == "draw":
            return 0
        return -1

    df = df.copy()
    df["outcome"] = df.apply(_label, axis=1)
    return df


def _encode_teams(df: pd.DataFrame, enc: LabelEncoder) -> pd.DataFrame:
    """Add integer-encoded team columns using a pre-fitted LabelEncoder."""
    df = df.copy()
    df["team1_enc"] = enc.transform(df["team1"])
    df["team2_enc"] = enc.transform(df["team2"])
    return df


# ---------------------------------------------------------------------------
# Training  (80 % train / 20 % test)
# ---------------------------------------------------------------------------

def compile_model() -> None:
    """
    Full training pipeline:
      1.  Load & enrich data from DB
      2.  Drop incomplete rows
      3.  Encode teams with LabelEncoder
      4.  Split 80 / 20 (stratified on outcome)
      5.  Scale features with StandardScaler
      6.  Train GradientBoostingRegressor × 2 (team1_score, team2_score)
      7.  Train RandomForestClassifier (win / draw / loss)
      8.  Evaluate and print metrics
      9.  Save all models + scalers as .pkl (joblib)
      10. Save test predictions and metrics as CSV / JSON
    """
    print("=" * 60)
    print("STEP 1 — Loading data")
    print("=" * 60)
    df = load_data()
    df = add_club_stats(df)

    # Drop rows with missing scores or empty winner strings
    df = df[df["winner"].notna() & (df["winner"].astype(str).str.strip() != "")]
    df = df[df["team1_score"].notna() & df["team2_score"].notna()]
    df = _derive_outcome(df)
    df = df.reset_index(drop=True)

    print(f"Total usable rows : {len(df)}")

    # --- Encode team names ---
    team_enc = LabelEncoder()
    team_enc.fit(pd.concat([df["team1"], df["team2"]]))
    df = _encode_teams(df, team_enc)

    X          = df[FEATURE_COLS].values.astype(float)
    y_score_t1 = df["team1_score"].values.astype(float)
    y_score_t2 = df["team2_score"].values.astype(float)
    y_outcome  = df["outcome"].values.astype(int)

    # -----------------------------------------------------------------------
    # 80 / 20 split  (stratified so each class keeps its natural proportion)
    # -----------------------------------------------------------------------
    print("\nSplit  →  80 % train / 20 % test  (stratified on outcome)")
    splits = train_test_split(
        X, y_score_t1, y_score_t2, y_outcome,
        test_size=0.20,
        random_state=42,
        stratify=y_outcome,
    )
    X_train, X_test = splits[0], splits[1]
    yt1_train, yt1_test = splits[2], splits[3]
    yt2_train, yt2_test = splits[4], splits[5]
    yo_train,  yo_test  = splits[6], splits[7]

    print(f"  Training samples : {len(X_train)}")
    print(f"  Testing  samples : {len(X_test)}")

    # --- Feature scaling (fit on train only, apply to both) ---
    feature_scaler = StandardScaler()
    X_train_sc = feature_scaler.fit_transform(X_train)
    X_test_sc  = feature_scaler.transform(X_test)

    # -----------------------------------------------------------------------
    # Regression — team1_score
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 2 — Regression: team1_score")
    print("=" * 60)
    reg_t1 = GradientBoostingRegressor(
        n_estimators=300, learning_rate=0.05, max_depth=4, random_state=42,
    )
    reg_t1.fit(X_train_sc, yt1_train)
    pred_t1 = reg_t1.predict(X_test_sc)
    # clip negatives so scores are always >= 0
    pred_t1_clipped = np.clip(pred_t1, 0, None)
    mae_t1  = mean_absolute_error(yt1_test, pred_t1_clipped)
    rmse_t1 = mean_squared_error(yt1_test, pred_t1_clipped) ** 0.5
    print(f"  MAE : {mae_t1:.4f}")
    print(f"  RMSE: {rmse_t1:.4f}")

    # -----------------------------------------------------------------------
    # Regression — team2_score
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 3 — Regression: team2_score")
    print("=" * 60)
    reg_t2 = GradientBoostingRegressor(
        n_estimators=300, learning_rate=0.05, max_depth=4, random_state=42,
    )
    reg_t2.fit(X_train_sc, yt2_train)
    pred_t2 = reg_t2.predict(X_test_sc)
    pred_t2_clipped = np.clip(pred_t2, 0, None)
    mae_t2  = mean_absolute_error(yt2_test, pred_t2_clipped)
    rmse_t2 = mean_squared_error(yt2_test, pred_t2_clipped) ** 0.5
    print(f"  MAE : {mae_t2:.4f}")
    print(f"  RMSE: {rmse_t2:.4f}")

    # -----------------------------------------------------------------------
    # Classification — outcome
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 4 — Classification: outcome (win / draw / loss)")
    print("=" * 60)
    clf = RandomForestClassifier(
        n_estimators=300, max_depth=8,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    clf.fit(X_train_sc, yo_train)
    pred_outcome = clf.predict(X_test_sc)
    acc = accuracy_score(yo_test, pred_outcome)
    report_str = classification_report(
        yo_test, pred_outcome,
        target_names=["loss (-1)", "draw (0)", "win (1)"],
        labels=[-1, 0, 1],
    )
    print(f"  Accuracy: {acc * 100:.2f}%")
    print(report_str)

    # -----------------------------------------------------------------------
    # Persist models  (joblib .pkl)
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("STEP 5 — Saving models")
    print("=" * 60)
    os.makedirs(MODELS_DIR, exist_ok=True)

    joblib.dump(team_enc,       os.path.join(MODELS_DIR, "match_team_enc.pkl"))
    joblib.dump(feature_scaler, os.path.join(MODELS_DIR, "match_feature_scaler.pkl"))
    joblib.dump(reg_t1,         os.path.join(MODELS_DIR, "match_score_reg_t1.pkl"))
    joblib.dump(reg_t2,         os.path.join(MODELS_DIR, "match_score_reg_t2.pkl"))
    joblib.dump(clf,            os.path.join(MODELS_DIR, "match_outcome_clf.pkl"))

    print(f"  Saved: match_team_enc.pkl")
    print(f"  Saved: match_feature_scaler.pkl")
    print(f"  Saved: match_score_reg_t1.pkl")
    print(f"  Saved: match_score_reg_t2.pkl")
    print(f"  Saved: match_outcome_clf.pkl")

    # -----------------------------------------------------------------------
    # Save test-set predictions  (CSV)
    # -----------------------------------------------------------------------
    test_df = df.iloc[len(X_train):].copy().reset_index(drop=True)   # same order as X_test
    # NOTE: iloc is only valid when train_test_split used default shuffle;
    # we use the explicit index arrays instead for accuracy.
    outcome_map = {1: "win", 0: "draw", -1: "loss"}

    results_df = pd.DataFrame({
        "team1":              X_test[:, FEATURE_COLS.index("team1_enc")],   # encoded int
        "team2":              X_test[:, FEATURE_COLS.index("team2_enc")],   # encoded int
        "actual_team1_score": yt1_test,
        "actual_team2_score": yt2_test,
        "pred_team1_score":   np.round(pred_t1_clipped, 2),
        "pred_team2_score":   np.round(pred_t2_clipped, 2),
        "actual_outcome":     [outcome_map[o] for o in yo_test],
        "pred_outcome":       [outcome_map[o] for o in pred_outcome],
    })

    predictions_path = os.path.join(MODELS_DIR, "match_test_predictions.csv")
    results_df.to_csv(predictions_path, index=False)
    print(f"\n  Saved test predictions → {predictions_path}")

    # -----------------------------------------------------------------------
    # Save evaluation metrics  (JSON)
    # -----------------------------------------------------------------------
    metrics = {
        "split": {
            "train_size": int(len(X_train)),
            "test_size":  int(len(X_test)),
            "test_ratio": 0.20,
        },
        "regression_team1_score": {
            "mae":  round(mae_t1,  4),
            "rmse": round(rmse_t1, 4),
        },
        "regression_team2_score": {
            "mae":  round(mae_t2,  4),
            "rmse": round(rmse_t2, 4),
        },
        "classification_outcome": {
            "accuracy":          round(acc, 4),
            "accuracy_pct":      round(acc * 100, 2),
            "classification_report": report_str,
        },
        "known_teams": list(team_enc.classes_),
    }

    metrics_path = os.path.join(MODELS_DIR, "match_model_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"  Saved metrics        → {metrics_path}")

    print("\n✅ Training complete.\n")


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _load_models() -> None:
    """Lazily load all saved match-prediction artefacts on first call."""
    global _team_enc, _feature_scaler, _score_reg_t1, _score_reg_t2, _outcome_clf
    if _team_enc is None:
        _team_enc       = joblib.load(os.path.join(MODELS_DIR, "match_team_enc.pkl"))
        _feature_scaler = joblib.load(os.path.join(MODELS_DIR, "match_feature_scaler.pkl"))
        _score_reg_t1   = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t1.pkl"))
        _score_reg_t2   = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t2.pkl"))
        _outcome_clf    = joblib.load(os.path.join(MODELS_DIR, "match_outcome_clf.pkl"))


def predict_match(
    team1: str,
    team2: str,
    team1_attack: int,
    team1_mid: int,
    team1_def: int,
    team1_overall: int,
    team2_attack: int,
    team2_mid: int,
    team2_def: int,
    team2_overall: int,
) -> dict:
    """
    Predict the result of an upcoming match.

    Parameters
    ----------
    team1, team2 : str
        Club names exactly as stored in the DB (case-sensitive).
    team*_attack / mid / def / overall : int
        Current club rating attributes fetched from the Club table.

    Returns
    -------
    dict
        team1_score_pred : float  — predicted goals scored by team1 (≥ 0)
        team2_score_pred : float  — predicted goals scored by team2 (≥ 0)
        outcome          : str    — "win" | "draw" | "loss" from team1's view
        outcome_proba    : dict   — {"win": float, "draw": float, "loss": float}

    Raises
    ------
    ValueError
        If either team name was not seen during training.
    RuntimeError
        If the model files have not been saved yet (run compile_model first).
    """
    _load_models()

    # Validate team names
    known = set(_team_enc.classes_)
    for name, role in [(team1, "team1"), (team2, "team2")]:
        if name not in known:
            raise ValueError(
                f"Unknown team '{name}' for `{role}`. "
                "Re-train the model to include it (run compile_model)."
            )

    attack_diff  = abs(team1_attack  - team2_attack)
    mid_diff     = abs(team1_mid     - team2_mid)
    defense_diff = abs(team1_def     - team2_def)
    overall_diff = abs(team1_overall - team2_overall)

    X = np.array([[
        _team_enc.transform([team1])[0],
        _team_enc.transform([team2])[0],
        team1_attack, team1_mid, team1_def, team1_overall,
        team2_attack, team2_mid, team2_def, team2_overall,
        attack_diff, mid_diff, defense_diff, overall_diff,
    ]], dtype=float)

    X_scaled = _feature_scaler.transform(X)

    t1_score = float(max(0.0, round(float(_score_reg_t1.predict(X_scaled)[0]), 2)))
    t2_score = float(max(0.0, round(float(_score_reg_t2.predict(X_scaled)[0]), 2)))

    outcome_code  = int(_outcome_clf.predict(X_scaled)[0])
    proba_raw     = _outcome_clf.predict_proba(X_scaled)[0]
    classes       = list(_outcome_clf.classes_)          # guaranteed [-1, 0, 1] after training

    outcome_proba = {
        "win":  round(float(proba_raw[classes.index( 1)]), 4),
        "draw": round(float(proba_raw[classes.index( 0)]), 4),
        "loss": round(float(proba_raw[classes.index(-1)]), 4),
    }
    outcome_label = {1: "win", 0: "draw", -1: "loss"}[outcome_code]

    return {
        "team1_score_pred": t1_score,
        "team2_score_pred": t2_score,
        "outcome":          outcome_label,
        "outcome_proba":    outcome_proba,
    }


# ---------------------------------------------------------------------------
# Sample predictions  (loads saved models, no DB write needed)
# ---------------------------------------------------------------------------

def run_sample_predictions() -> None:
    """
    Fetch a handful of real clubs from the DB, build sample matchups,
    call predict_match(), and print a formatted results table.

    Run standalone:
        python3 -m app.ai_models.match_score --predict
    """
    print("\n" + "=" * 70)
    print("SAMPLE PREDICTIONS  (loading saved models)")
    print("=" * 70)

    # ------------------------------------------------------------------ #
    # Pull distinct clubs that appear in match data (with stats)          #
    # ------------------------------------------------------------------ #
    db = SessionLocal()
    try:
        rows = db.query(
            Club.name,
            Club.attack,
            Club.midfield,
            Club.defence,
            Club.overall,
        ).join(
            Match,
            (Match.team1 == Club.name) | (Match.team2 == Club.name),
        ).filter(
            Match.league.in_(LEAGUES),
            Club.attack.isnot(None),
            Club.midfield.isnot(None),
            Club.defence.isnot(None),
            Club.overall.isnot(None),
        ).distinct().limit(20).all()
    finally:
        db.close()

    if len(rows) < 2:
        print("Not enough clubs found in DB to build sample matchups.")
        return

    # Build a lookup: name -> stats dict
    clubs: dict[str, dict] = {
        r.name: {
            "attack":   int(r.attack),
            "mid":      int(r.midfield),
            "def":      int(r.defence),
            "overall":  int(r.overall),
        }
        for r in rows
    }

    # Pair up adjacent teams to get 5 interesting fixtures
    names   = list(clubs.keys())
    fixtures = [(names[i], names[i + 1]) for i in range(0, min(len(names) - 1, 10), 2)]

    print(f"\n{'#':<4} {'Home Team':<25} {'Away Team':<25} "
          f"{'Pred Score':>12}  {'Outcome':<6}  {'Win%':>6}  {'Draw%':>6}  {'Loss%':>6}")
    print("-" * 95)

    for idx, (home, away) in enumerate(fixtures, start=1):
        hs = clubs[home]
        as_ = clubs[away]
        try:
            result = predict_match(
                team1=home, team2=away,
                team1_attack=hs["attack"], team1_mid=hs["mid"],
                team1_def=hs["def"],      team1_overall=hs["overall"],
                team2_attack=as_["attack"], team2_mid=as_["mid"],
                team2_def=as_["def"],       team2_overall=as_["overall"],
            )
            score_str = f"{result['team1_score_pred']:.1f} - {result['team2_score_pred']:.1f}"
            p = result["outcome_proba"]
            print(
                f"{idx:<4} {home:<25} {away:<25} "
                f"{score_str:>12}  {result['outcome']:<6}  "
                f"{p['win']*100:>5.1f}%  {p['draw']*100:>5.1f}%  {p['loss']*100:>5.1f}%"
            )
        except ValueError as e:
            print(f"{idx:<4} {home:<25} {away:<25}  SKIPPED — {e}")

    print()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

# Train only:    python3 -m app.ai_models.match_score
# Predict only:  python3 -m app.ai_models.match_score --predict
if __name__ == "__main__":
    import sys
    if "--predict" in sys.argv:
        run_sample_predictions()
    else:
        compile_model()
        run_sample_predictions()