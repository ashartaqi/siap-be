"""
match_score.py
==============
Regression model to predict match scores, with outcome derived from scores.

Accuracy improvements over baseline:
  1. LeagueStandings features  – points, GD, win-rate, goals-for/against
  2. Rolling form              – last-5 avg goals scored/conceded per team
  3. VotingRegressor ensemble  – HistGBR + RF + ExtraTrees averaged
  4. Calibrated draw threshold – chosen from training distribution

Run:
    python3 -m app.ai_models.match_score           # train + predict
    python3 -m app.ai_models.match_score --predict # predict only
"""

import json, os, sys
from collections import defaultdict
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.core.db import SessionLocal
from app.models import Club, LeagueStandings, Match

# ---------------------------------------------------------------------------
COLUMNS      = ["team1", "team2", "winner", "team1_score", "team2_score",
                 "league", "date"]
LEAGUES      = ["en.1", "es.1", "de.1", "it.1", "fr.1"]
MODELS_DIR   = os.path.join(os.path.dirname(__file__), "compiled_models")
FORM_WINDOW  = 5        # rolling games for form features

FEATURE_COLS = [
    # team identity
    "team1_enc", "team2_enc",
    # club ratings
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    # signed rating diffs
    "attack_diff", "mid_diff", "defense_diff", "overall_diff",
    # league standings
    "t1_points", "t1_gd", "t1_win_rate", "t1_goals_for", "t1_goals_against",
    "t2_points", "t2_gd", "t2_win_rate", "t2_goals_for", "t2_goals_against",
    "points_diff", "gd_diff",
    # rolling form (last FORM_WINDOW games)
    "t1_form_scored", "t1_form_conceded",
    "t2_form_scored", "t2_form_conceded",
]

# Lazy inference cache
_team_enc:       Optional[LabelEncoder]   = None
_feature_scaler: Optional[StandardScaler] = None
_reg_t1 = None
_reg_t2 = None
_meta:   Optional[dict] = None          # stores draw_threshold + known_teams


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_matches() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(
            Match.team1, Match.team2, Match.winner,
            Match.team1_score, Match.team2_score,
            Match.league, Match.date,
        ).filter(Match.league.in_(LEAGUES)).all()
    finally:
        db.close()
    return pd.DataFrame(rows, columns=COLUMNS)


def _load_clubs() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(
            Club.name, Club.attack, Club.midfield,
            Club.defence, Club.overall,
        ).all()
    finally:
        db.close()
    return (
        pd.DataFrame(rows, columns=["name","attack","midfield","defence","overall"])
        .drop_duplicates(subset=["name"])
    )


def _load_standings() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(
            LeagueStandings.team_name,
            LeagueStandings.points,
            LeagueStandings.won,
            LeagueStandings.draw,
            LeagueStandings.lost,
            LeagueStandings.goals_for,
            LeagueStandings.goals_against,
            LeagueStandings.goal_difference,
            LeagueStandings.played_games,
        ).all()
    finally:
        db.close()
    df = pd.DataFrame(rows, columns=[
        "team_name","points","won","draw","lost",
        "goals_for","goals_against","goal_difference","played_games",
    ])
    # aggregate across seasons/leagues → take latest (max points is a proxy)
    df = df.sort_values("points", ascending=False).drop_duplicates("team_name")
    df["win_rate"] = df["won"] / df["played_games"].clip(lower=1)
    return df.set_index("team_name")


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _build_rolling_form(df: pd.DataFrame) -> dict:
    """
    Return per-team rolling stats dict:
        team -> { "scored": float, "conceded": float }
    computed from all rows in df, sorted by date.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","team1_score","team2_score"])
    df = df.sort_values("date")

    history: dict[str, list] = defaultdict(list)
    for _, r in df.iterrows():
        for team, scored, conceded in [
            (r["team1"], r["team1_score"], r["team2_score"]),
            (r["team2"], r["team2_score"], r["team1_score"]),
        ]:
            history[team].append((float(scored), float(conceded)))

    form = {}
    for team, games in history.items():
        last = games[-FORM_WINDOW:] if len(games) >= FORM_WINDOW else games
        arr = np.array(last)
        form[team] = {
            "scored":    float(arr[:, 0].mean()),
            "conceded":  float(arr[:, 1].mean()),
        }
    return form


def add_features(df: pd.DataFrame, clubs_df: pd.DataFrame,
                 standings: pd.DataFrame, form: dict) -> pd.DataFrame:
    """Join all feature groups onto match rows."""
    # --- club ratings ---
    df = (df.merge(clubs_df, left_on="team1", right_on="name", how="left")
            .drop(columns=["name"])
            .rename(columns={"attack":"team1_attack","midfield":"team1_mid",
                              "defence":"team1_def","overall":"team1_overall"}))
    df = (df.merge(clubs_df, left_on="team2", right_on="name", how="left")
            .drop(columns=["name"])
            .rename(columns={"attack":"team2_attack","midfield":"team2_mid",
                              "defence":"team2_def","overall":"team2_overall"}))

    rating_cols = ["team1_attack","team1_mid","team1_def","team1_overall",
                   "team2_attack","team2_mid","team2_def","team2_overall"]
    df.dropna(subset=rating_cols, inplace=True)
    df[rating_cols] = df[rating_cols].astype(int)

    df["attack_diff"]  = df["team1_attack"]  - df["team2_attack"]
    df["mid_diff"]     = df["team1_mid"]      - df["team2_mid"]
    df["defense_diff"] = df["team1_def"]      - df["team2_def"]
    df["overall_diff"] = df["team1_overall"]  - df["team2_overall"]

    # --- standings ---
    def _std(team, col, default=0.0):
        return float(standings.loc[team, col]) if team in standings.index else default

    for prefix, team_col in [("t1", "team1"), ("t2", "team2")]:
        df[f"{prefix}_points"]       = df[team_col].apply(lambda t: _std(t, "points"))
        df[f"{prefix}_gd"]           = df[team_col].apply(lambda t: _std(t, "goal_difference"))
        df[f"{prefix}_win_rate"]     = df[team_col].apply(lambda t: _std(t, "win_rate"))
        df[f"{prefix}_goals_for"]    = df[team_col].apply(lambda t: _std(t, "goals_for"))
        df[f"{prefix}_goals_against"]= df[team_col].apply(lambda t: _std(t, "goals_against"))

    df["points_diff"] = df["t1_points"] - df["t2_points"]
    df["gd_diff"]     = df["t1_gd"]     - df["t2_gd"]

    # --- rolling form ---
    def _form(team, key, default=1.2):
        return form[team][key] if team in form else default

    df["t1_form_scored"]   = df["team1"].apply(lambda t: _form(t, "scored"))
    df["t1_form_conceded"] = df["team1"].apply(lambda t: _form(t, "conceded"))
    df["t2_form_scored"]   = df["team2"].apply(lambda t: _form(t, "scored"))
    df["t2_form_conceded"] = df["team2"].apply(lambda t: _form(t, "conceded"))

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Outcome logic
# ---------------------------------------------------------------------------

def _score_to_outcome(t1: float, t2: float, threshold: float = 0.5) -> str:
    d = t1 - t2
    if d >  threshold: return "win"
    if d < -threshold: return "loss"
    return "draw"


def _calibrate_threshold(pred_t1, pred_t2, actual_t1, actual_t2) -> float:
    """Grid-search the threshold that maximises outcome accuracy on training."""
    best_t, best_acc = 0.3, 0.0
    for t in np.arange(0.1, 1.5, 0.05):
        preds   = [_score_to_outcome(p1, p2, t) for p1, p2 in zip(pred_t1, pred_t2)]
        actuals = [_score_to_outcome(a1, a2, 0.0) for a1, a2 in zip(actual_t1, actual_t2)]
        acc = sum(p == a for p, a in zip(preds, actuals)) / len(preds)
        if acc > best_acc:
            best_acc, best_t = acc, t
    return round(best_t, 2)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def compile_model() -> None:
    print("=" * 60)
    print("STEP 1 — Loading data")
    print("=" * 60)

    df        = _load_matches()
    clubs_df  = _load_clubs()
    standings = _load_standings()
    form      = _build_rolling_form(df)

    df = df[df["team1_score"].notna() & df["team2_score"].notna()].copy()
    df = add_features(df, clubs_df, standings, form)
    df = df.reset_index(drop=True)
    print(f"  Usable rows: {len(df)}")

    team_enc = LabelEncoder()
    team_enc.fit(pd.concat([df["team1"], df["team2"]]))
    df["team1_enc"] = team_enc.transform(df["team1"])
    df["team2_enc"] = team_enc.transform(df["team2"])

    X   = df[FEATURE_COLS].values.astype(float)
    y_t1 = df["team1_score"].values.astype(float)
    y_t2 = df["team2_score"].values.astype(float)
    idx  = np.arange(len(X))

    X_train, X_test, yt1_tr, yt1_te, yt2_tr, yt2_te, idx_tr, idx_te = train_test_split(
        X, y_t1, y_t2, idx, test_size=0.20, random_state=42,
    )
    print(f"  Train: {len(X_train)}  Test: {len(X_test)}")

    scaler = StandardScaler()
    Xtr = scaler.fit_transform(X_train)
    Xte = scaler.transform(X_test)

    # --- ensemble ---
    def _make_ensemble():
        return VotingRegressor([
            ("hgb", HistGradientBoostingRegressor(
                max_iter=600, learning_rate=0.04, max_depth=6,
                min_samples_leaf=20, l2_regularization=0.1, random_state=42)),
            ("rf",  RandomForestRegressor(
                n_estimators=300, max_depth=12, min_samples_leaf=10,
                n_jobs=-1, random_state=42)),
            ("et",  ExtraTreesRegressor(
                n_estimators=300, max_depth=12, min_samples_leaf=10,
                n_jobs=-1, random_state=42)),
        ])

    print("\n" + "=" * 60)
    print("STEP 2 — Training team1_score regressor")
    print("=" * 60)
    reg_t1 = _make_ensemble()
    reg_t1.fit(Xtr, yt1_tr)
    pred_t1 = np.clip(reg_t1.predict(Xte), 0, None)
    print(f"  MAE : {mean_absolute_error(yt1_te, pred_t1):.4f}")
    print(f"  RMSE: {mean_squared_error(yt1_te, pred_t1)**0.5:.4f}")

    print("\n" + "=" * 60)
    print("STEP 3 — Training team2_score regressor")
    print("=" * 60)
    reg_t2 = _make_ensemble()
    reg_t2.fit(Xtr, yt2_tr)
    pred_t2 = np.clip(reg_t2.predict(Xte), 0, None)
    print(f"  MAE : {mean_absolute_error(yt2_te, pred_t2):.4f}")
    print(f"  RMSE: {mean_squared_error(yt2_te, pred_t2)**0.5:.4f}")

    print("\n" + "=" * 60)
    print("STEP 4 — Calibrating draw threshold")
    print("=" * 60)
    draw_thr = _calibrate_threshold(
        reg_t1.predict(Xtr), reg_t2.predict(Xtr), yt1_tr, yt2_tr
    )
    print(f"  Best threshold: {draw_thr}")

    actual_out = [_score_to_outcome(a, b, 0.0) for a, b in zip(yt1_te, yt2_te)]
    pred_out   = [_score_to_outcome(p, q, draw_thr) for p, q in zip(pred_t1, pred_t2)]
    acc = sum(a == p for a, p in zip(actual_out, pred_out)) / len(actual_out)
    print(f"  Outcome accuracy: {acc*100:.2f}%")

    # --- save ---
    print("\n" + "=" * 60)
    print("STEP 5 — Saving artefacts")
    print("=" * 60)
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(team_enc, os.path.join(MODELS_DIR, "match_team_enc.pkl"))
    joblib.dump(scaler,   os.path.join(MODELS_DIR, "match_feature_scaler.pkl"))
    joblib.dump(reg_t1,   os.path.join(MODELS_DIR, "match_score_reg_t1.pkl"))
    joblib.dump(reg_t2,   os.path.join(MODELS_DIR, "match_score_reg_t2.pkl"))

    meta = {"draw_threshold": draw_thr, "known_teams": list(team_enc.classes_)}
    with open(os.path.join(MODELS_DIR, "match_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    test_rows = df.iloc[idx_te].reset_index(drop=True)
    pd.DataFrame({
        "team1": test_rows["team1"],
        "team2": test_rows["team2"],
        "actual_t1": yt1_te, "actual_t2": yt2_te,
        "pred_t1": np.round(pred_t1, 2), "pred_t2": np.round(pred_t2, 2),
        "actual_outcome": actual_out,
        "pred_outcome":   pred_out,
    }).to_csv(os.path.join(MODELS_DIR, "match_test_predictions.csv"), index=False)

    metrics = {
        "split": {"train": int(len(X_train)), "test": int(len(X_test))},
        "draw_threshold": draw_thr,
        "team1_score": {
            "mae":  round(mean_absolute_error(yt1_te, pred_t1), 4),
            "rmse": round(mean_squared_error(yt1_te, pred_t1)**0.5, 4),
        },
        "team2_score": {
            "mae":  round(mean_absolute_error(yt2_te, pred_t2), 4),
            "rmse": round(mean_squared_error(yt2_te, pred_t2)**0.5, 4),
        },
        "outcome_accuracy_pct": round(acc * 100, 2),
        "known_teams": list(team_enc.classes_),
    }
    with open(os.path.join(MODELS_DIR, "match_model_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print("  All artefacts saved.")
    print("\n✅ Training complete.\n")


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

def _load_models():
    global _team_enc, _feature_scaler, _reg_t1, _reg_t2, _meta
    if _team_enc is None:
        _team_enc       = joblib.load(os.path.join(MODELS_DIR, "match_team_enc.pkl"))
        _feature_scaler = joblib.load(os.path.join(MODELS_DIR, "match_feature_scaler.pkl"))
        _reg_t1         = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t1.pkl"))
        _reg_t2         = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t2.pkl"))
        with open(os.path.join(MODELS_DIR, "match_meta.json")) as f:
            _meta = json.load(f)


def _standings_for(team: str, standings: pd.DataFrame) -> dict:
    if team in standings.index:
        r = standings.loc[team]
        return {
            "points": float(r["points"]),
            "gd":     float(r["goal_difference"]),
            "win_rate": float(r["win_rate"]),
            "goals_for": float(r["goals_for"]),
            "goals_against": float(r["goals_against"]),
        }
    return {"points": 0, "gd": 0, "win_rate": 0, "goals_for": 0, "goals_against": 0}


def _form_for(team: str, form: dict) -> dict:
    return form.get(team, {"scored": 1.2, "conceded": 1.2})


# ---------------------------------------------------------------------------
# Public predict API
# ---------------------------------------------------------------------------

def predict_match(
    team1: str, team2: str,
    team1_attack: int, team1_mid: int, team1_def: int, team1_overall: int,
    team2_attack: int, team2_mid: int, team2_def: int, team2_overall: int,
) -> dict:
    """
    Predict match result.  Outcome is derived from predicted scores.

    Returns dict with team1_score_pred, team2_score_pred,
    outcome ('win'/'draw'/'loss' for team1), score_diff.
    """
    _load_models()

    known = set(_team_enc.classes_)
    for name, role in [(team1, "team1"), (team2, "team2")]:
        if name not in known:
            raise ValueError(f"Unknown team '{name}' ({role}). Re-train to include it.")

    standings = _load_standings()
    form      = _build_rolling_form(_load_matches())
    draw_thr  = _meta["draw_threshold"]

    s1 = _standings_for(team1, standings)
    s2 = _standings_for(team2, standings)
    f1 = _form_for(team1, form)
    f2 = _form_for(team2, form)

    X = np.array([[
        _team_enc.transform([team1])[0],
        _team_enc.transform([team2])[0],
        team1_attack, team1_mid, team1_def, team1_overall,
        team2_attack, team2_mid, team2_def, team2_overall,
        team1_attack - team2_attack,
        team1_mid    - team2_mid,
        team1_def    - team2_def,
        team1_overall - team2_overall,
        s1["points"], s1["gd"], s1["win_rate"], s1["goals_for"], s1["goals_against"],
        s2["points"], s2["gd"], s2["win_rate"], s2["goals_for"], s2["goals_against"],
        s1["points"] - s2["points"],
        s1["gd"]     - s2["gd"],
        f1["scored"], f1["conceded"],
        f2["scored"], f2["conceded"],
    ]], dtype=float)

    X_sc = _feature_scaler.transform(X)
    t1 = float(max(0.0, round(float(_reg_t1.predict(X_sc)[0]), 2)))
    t2 = float(max(0.0, round(float(_reg_t2.predict(X_sc)[0]), 2)))

    return {
        "team1_score_pred": t1,
        "team2_score_pred": t2,
        "outcome":  _score_to_outcome(t1, t2, draw_thr),
        "score_diff": round(t1 - t2, 2),
    }


# ---------------------------------------------------------------------------
# Sample demo
# ---------------------------------------------------------------------------

def run_sample_predictions() -> None:
    print("\n" + "=" * 70)
    print("SAMPLE PREDICTIONS")
    print("=" * 70)

    db = SessionLocal()
    try:
        rows = db.query(Club.name, Club.attack, Club.midfield,
                        Club.defence, Club.overall).join(
            Match, (Match.team1 == Club.name) | (Match.team2 == Club.name)
        ).filter(
            Match.league.in_(LEAGUES),
            Club.attack.isnot(None),
        ).distinct().limit(20).all()
    finally:
        db.close()

    if len(rows) < 2:
        print("Not enough clubs in DB.")
        return

    clubs = {r.name: {"attack": int(r.attack), "mid": int(r.midfield),
                      "def": int(r.defence), "overall": int(r.overall)}
             for r in rows}
    names = list(clubs.keys())
    fixtures = [(names[i], names[i+1]) for i in range(0, min(len(names)-1, 10), 2)]

    print(f"\n{'#':<4} {'Home':<25} {'Away':<25} {'Score':>9}  {'Outcome':<7}  {'Diff':>6}")
    print("-" * 80)
    for i, (home, away) in enumerate(fixtures, 1):
        h, a = clubs[home], clubs[away]
        try:
            r = predict_match(home, away,
                h["attack"], h["mid"], h["def"], h["overall"],
                a["attack"], a["mid"], a["def"], a["overall"])
            score = f"{r['team1_score_pred']:.1f} - {r['team2_score_pred']:.1f}"
            print(f"{i:<4} {home:<25} {away:<25} {score:>9}  "
                  f"{r['outcome']:<7}  {r['score_diff']:>+.2f}")
        except ValueError as e:
            print(f"{i:<4} {home:<25} {away:<25}  SKIPPED — {e}")
    print()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--predict" in sys.argv:
        run_sample_predictions()
    else:
        compile_model()
        run_sample_predictions()