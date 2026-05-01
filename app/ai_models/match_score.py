"""
match_score.py  (v3)
====================
Trains an ensemble of sklearn models on COMBINED historical match data:

  Sources
  -------
  • Match table      — historical results 2010 → 2025-26
  • Fixtures table   — 2025-26 season results (status='FINISHED')

  Extra signals (new in v3)
  -------------------------
  • Home advantage flag    — home team encoded as team1
  • Current league rank    — from LeagueStanding (lower = better)
  • Form score             — last-5 wins from LeagueStanding.form (e.g. "WWDLW" → 3)
  • Points total           — from LeagueStanding.points
  • Goals scored / conceded — from LeagueStanding (attack/defence proxy)
  • Rank diff, form diff, points diff (signed + absolute)

  Models
  ------
  • HistGradientBoostingRegressor (Poisson loss) → team1_score, team2_score
  • HistGradientBoostingRegressor (squared error) → dominance ratio
  • CalibratedClassifierCV(VotingClassifier) → outcome (win / draw / loss)

Run:
    python3 -m app.ai_models.match_score           # train + backtest
    python3 -m app.ai_models.match_score --predict # backtest only
"""

import json
import os
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.core.db import SessionLocal
from app.models import Club, Match, Fixtures, LeagueStandings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCORE_DIFF_THRESHOLD: float = 0.5
RATIO_TOLERANCE:      float = 0.25

MODELS_DIR: str = os.path.join(os.path.dirname(__file__), "compiled_models")

_CLUB_STAT_COLS: list[str] = [
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    "attack_diff",  "mid_diff",  "defense_diff",  "overall_diff",
    "attack_abs_diff", "mid_abs_diff", "defense_abs_diff", "overall_abs_diff",
]

_STANDING_COLS: list[str] = [
    "team1_rank",   "team1_form",   "team1_points",
    "team1_gf",     "team1_ga",     "team1_gd",
    "team2_rank",   "team2_form",   "team2_points",
    "team2_gf",     "team2_ga",     "team2_gd",
    "rank_diff",    "form_diff",    "points_diff",   "gd_diff",
    "rank_abs_diff","form_abs_diff","points_abs_diff","gd_abs_diff",
]

BASE_FEATURE_COLS: list[str] = (
    ["team1_enc", "team2_enc", "is_home"]
    + _CLUB_STAT_COLS
    + _STANDING_COLS
)

CLF_FEATURE_COLS: list[str] = BASE_FEATURE_COLS + [
    "pred_t1_score", "pred_t2_score", "pred_ratio"
]


# ---------------------------------------------------------------------------
# Ratio helpers
# ---------------------------------------------------------------------------

def _dominance_ratio(t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    eps = 1e-8
    return (t1 - t2) / (t1 + t2 + eps)


def _ratio_mae(at1, at2, pt1, pt2) -> float:
    return float(np.mean(np.abs(_dominance_ratio(at1, at2) - _dominance_ratio(pt1, pt2))))


def _ratio_accuracy(at1, at2, pt1, pt2, tol=RATIO_TOLERANCE) -> float:
    return float(np.mean(
        np.abs(_dominance_ratio(at1, at2) - _dominance_ratio(pt1, pt2)) <= tol
    ))


def _ratio_outcome_accuracy(at1, at2, pt1, pt2, thr=SCORE_DIFF_THRESHOLD) -> float:
    def _out(t1, t2):
        d = t1 - t2
        o = np.zeros(len(d), dtype=int)
        o[d >  thr] =  1
        o[d < -thr] = -1
        return o
    return float(np.mean(_out(at1, at2) == _out(pt1, pt2)))


# ---------------------------------------------------------------------------
# Score display helper
# ---------------------------------------------------------------------------

def _display_score(t1_pred: float, t2_pred: float) -> str:
    """
    Convert raw predicted floats into a display scoreline using ratio-based
    rounding instead of rounding each score independently.

    Steps:
      1. Compute team1's share:  ratio = t1 / (t1 + t2)
      2. Decide total goals:     total = round(t1 + t2)
      3. Distribute by ratio:    s1 = round(ratio * total),  s2 = total - s1

    This keeps the dominance relationship intact.
    Examples:
      1.62 vs 1.21  → total=3, ratio=0.57 → 2-1
      2.48 vs 0.81  → total=3, ratio=0.75 → 2-1
      1.10 vs 1.05  → total=2, ratio=0.51 → 1-1  (draw)
      0.40 vs 0.35  → total=1, ratio=0.53 → 1-0  (narrow win still shows)
    """
    eps   = 1e-8
    total = int(round(t1_pred + t2_pred))
    ratio = t1_pred / (t1_pred + t2_pred + eps)

    s1 = int(round(ratio * total))
    s2 = total - s1
    s1 = max(0, s1)
    s2 = max(0, s2)
    return f"{s1}-{s2}"


# ---------------------------------------------------------------------------
# Form string → numeric score  ("WWDLW" → count of W's)
# ---------------------------------------------------------------------------

def _parse_form(form_str: Optional[str]) -> int:
    if not form_str:
        return 2
    return str(form_str).upper().count("W")


# ---------------------------------------------------------------------------
# DB lookups
# ---------------------------------------------------------------------------

def _load_standings_lookup(db) -> dict:
    """
    {team_name: {rank, form, points, gf, ga, gd}}
    If a team appears multiple times (multiple leagues / seasons),
    keep the snapshot with the highest points total.
    """
    rows = db.query(LeagueStandings).all()
    lookup: dict = {}
    for row in rows:
        name = str(row.team_name).strip()
        pts  = int(row.points or 0)
        if name not in lookup or pts > lookup[name]["points"]:
            gf = int(row.goals_for     or 0)
            ga = int(row.goals_against or 0)
            lookup[name] = {
                "rank":   int(row.position or 99),
                "form":   _parse_form(getattr(row, "form", None)),
                "points": pts,
                "gf":     gf,
                "ga":     ga,
                "gd":     gf - ga,
            }
    return lookup


def _load_clubs_lookup(db) -> dict:
    """Returns {team_name: {attack, mid, def, overall}}"""
    rows = db.query(Club.name, Club.attack, Club.midfield, Club.defence, Club.overall).all()
    out: dict = {}
    for r in rows:
        if None not in (r.attack, r.midfield, r.defence, r.overall):
            out[str(r.name).strip()] = {
                "attack":  int(r.attack),
                "mid":     int(r.midfield),
                "def":     int(r.defence),
                "overall": int(r.overall),
            }
    return out


# ---------------------------------------------------------------------------
# Data loading & feature engineering
# ---------------------------------------------------------------------------

def load_combined_data() -> pd.DataFrame:
    """
    Merge Match (historical) + Fixtures (current season, FINISHED).

    is_home flag:
      Match table  → 0  (no reliable home/away info historically)
      Fixtures     → 1  (home_team is always stored as team1)
    """
    db = SessionLocal()
    try:
        # Historical matches
        match_rows = db.query(
            Match.team1, Match.team2,
            Match.team1_score, Match.team2_score,
            Match.winner,
        ).all()

        match_df = pd.DataFrame(match_rows, columns=[
            "team1", "team2", "team1_score", "team2_score", "winner"
        ])
        match_df["is_home"] = 0

        def _norm_match_winner(row):
            w = str(row["winner"]).strip().lower()
            if w in ("draw", "none", ""):
                return "draw"
            if w == str(row["team1"]).strip().lower():
                return "team1"
            return "team2"

        match_df["winner_norm"] = match_df.apply(_norm_match_winner, axis=1)

        # Current-season finished fixtures
        fix_rows = db.query(
            Fixtures.home_team, Fixtures.away_team,
            Fixtures.home_team_score, Fixtures.away_team_score,
            Fixtures.winner,
        ).filter(Fixtures.status == "FINISHED").all()

        fix_df = pd.DataFrame(fix_rows, columns=[
            "team1", "team2", "team1_score", "team2_score", "winner"
        ])
        fix_df["is_home"] = 1

        def _norm_fix_winner(row):
            w = str(row["winner"]).strip().upper()
            if w in ("DRAW", "NONE", ""):
                return "draw"
            if w == "HOME_TEAM":
                return "team1"
            if w == "AWAY_TEAM":
                return "team2"
            if w == str(row["team1"]).strip().upper():
                return "team1"
            return "team2"

        fix_df["winner_norm"] = fix_df.apply(_norm_fix_winner, axis=1)

        standings = _load_standings_lookup(db)
        clubs     = _load_clubs_lookup(db)

    finally:
        db.close()

    df = pd.concat([match_df, fix_df], ignore_index=True)
    df = df.rename(columns={"winner_norm": "outcome_label"})

    df = df[df["team1_score"].notna() & df["team2_score"].notna()]
    df = df[df["outcome_label"].isin(["team1", "team2", "draw"])]
    df["team1_score"] = df["team1_score"].astype(float)
    df["team2_score"] = df["team2_score"].astype(float)
    df = df.reset_index(drop=True)

    print(f"  Match rows    : {len(match_df)}")
    print(f"  Fixture rows  : {len(fix_df)}")
    print(f"  Combined total: {len(df)}")

    df = _attach_club_stats(df, clubs)
    df = _attach_standing_features(df, standings)
    df["outcome"] = df["outcome_label"].map(
        {"team1": 1, "draw": 0, "team2": -1}
    ).astype(int)

    return df.reset_index(drop=True)


def _attach_club_stats(df: pd.DataFrame, clubs: dict) -> pd.DataFrame:
    def _get(name: str, stat: str, default: int = 70) -> int:
        return clubs.get(str(name).strip(), {}).get(stat, default)

    df = df.copy()
    for col, stat in [
        ("team1_attack", "attack"), ("team1_mid", "mid"),
        ("team1_def",    "def"),    ("team1_overall", "overall"),
        ("team2_attack", "attack"), ("team2_mid", "mid"),
        ("team2_def",    "def"),    ("team2_overall", "overall"),
    ]:
        team = "team1" if col.startswith("team1") else "team2"
        df[col] = df[team].apply(lambda n, s=stat: _get(n, s))

    df["attack_diff"]      = df["team1_attack"]  - df["team2_attack"]
    df["mid_diff"]         = df["team1_mid"]      - df["team2_mid"]
    df["defense_diff"]     = df["team1_def"]      - df["team2_def"]
    df["overall_diff"]     = df["team1_overall"]  - df["team2_overall"]
    df["attack_abs_diff"]  = df["attack_diff"].abs()
    df["mid_abs_diff"]     = df["mid_diff"].abs()
    df["defense_abs_diff"] = df["defense_diff"].abs()
    df["overall_abs_diff"] = df["overall_diff"].abs()
    return df


def _attach_standing_features(df: pd.DataFrame, standings: dict) -> pd.DataFrame:
    DEFAULTS = {"rank": 12, "form": 2, "points": 30, "gf": 30, "ga": 30, "gd": 0}

    def _get(name: str, stat: str) -> int:
        return standings.get(str(name).strip(), DEFAULTS).get(stat, DEFAULTS[stat])

    df = df.copy()
    for prefix in ("team1", "team2"):
        for stat in ("rank", "form", "points", "gf", "ga", "gd"):
            df[f"{prefix}_{stat}"] = df[prefix].apply(lambda n, s=stat: _get(n, s))

    # rank_diff positive = team1 ranks better (lower position number)
    df["rank_diff"]        = df["team2_rank"]   - df["team1_rank"]
    df["form_diff"]        = df["team1_form"]   - df["team2_form"]
    df["points_diff"]      = df["team1_points"] - df["team2_points"]
    df["gd_diff"]          = df["team1_gd"]     - df["team2_gd"]
    df["rank_abs_diff"]    = df["rank_diff"].abs()
    df["form_abs_diff"]    = df["form_diff"].abs()
    df["points_abs_diff"]  = df["points_diff"].abs()
    df["gd_abs_diff"]      = df["gd_diff"].abs()
    return df


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

def _build_score_regressor() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson", max_iter=500, learning_rate=0.03,
        max_depth=5, min_samples_leaf=20, l2_regularization=0.5, random_state=42,
    )


def _build_outcome_classifier() -> CalibratedClassifierCV:
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=10, min_samples_leaf=10,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    hgbt = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.03, max_depth=6,
        min_samples_leaf=15, l2_regularization=0.5,
        class_weight="balanced", random_state=42,
    )
    lr = LogisticRegression(
        C=0.5, max_iter=1000, class_weight="balanced",
        solver="lbfgs", random_state=42,
    )
    voting = VotingClassifier(
        estimators=[("rf", rf), ("hgbt", hgbt), ("lr", lr)],
        voting="soft", n_jobs=-1,
    )
    return CalibratedClassifierCV(voting, cv=5, method="isotonic")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def compile_model() -> None:
    print("=" * 60)
    print("STEP 1 — Loading combined Match + Fixtures data")
    print("=" * 60)
    df = load_combined_data()
    print(f"Usable rows after cleaning: {len(df)}")

    team_enc = LabelEncoder()
    team_enc.fit(pd.concat([df["team1"], df["team2"]]).unique())
    df["team1_enc"] = team_enc.transform(df["team1"])
    df["team2_enc"] = team_enc.transform(df["team2"])

    X_base     = df[BASE_FEATURE_COLS].values.astype(float)
    y_score_t1 = df["team1_score"].values.astype(float)
    y_score_t2 = df["team2_score"].values.astype(float)
    y_ratio    = _dominance_ratio(y_score_t1, y_score_t2)
    y_outcome  = df["outcome"].values.astype(int)

    print("\nSplit → 80% train / 20% test (stratified on outcome)")
    (X_tr, X_te,
     yt1_tr, yt1_te,
     yt2_tr, yt2_te,
     yr_tr,  yr_te,
     yo_tr,  yo_te) = train_test_split(
        X_base, y_score_t1, y_score_t2, y_ratio, y_outcome,
        test_size=0.20, random_state=42, stratify=y_outcome,
    )
    print(f"  Train: {len(X_tr)}   Test: {len(X_te)}")

    base_scaler = StandardScaler()
    X_tr_sc = base_scaler.fit_transform(X_tr)
    X_te_sc = base_scaler.transform(X_te)

    print("\n" + "=" * 60)
    print("STEP 2 — Score regressors (Poisson HistGBT)")
    print("=" * 60)
    reg_t1 = _build_score_regressor()
    reg_t1.fit(X_tr_sc, yt1_tr)
    pred_t1 = np.clip(reg_t1.predict(X_te_sc), 0, None)
    print(f"  team1  MAE={mean_absolute_error(yt1_te, pred_t1):.4f}  "
          f"RMSE={mean_squared_error(yt1_te, pred_t1)**0.5:.4f}")

    reg_t2 = _build_score_regressor()
    reg_t2.fit(X_tr_sc, yt2_tr)
    pred_t2 = np.clip(reg_t2.predict(X_te_sc), 0, None)
    print(f"  team2  MAE={mean_absolute_error(yt2_te, pred_t2):.4f}  "
          f"RMSE={mean_squared_error(yt2_te, pred_t2)**0.5:.4f}")

    print("\n" + "=" * 60)
    print("STEP 3 — Dominance ratio regressor")
    print("=" * 60)
    reg_ratio = HistGradientBoostingRegressor(
        loss="squared_error", max_iter=500, learning_rate=0.03,
        max_depth=5, min_samples_leaf=20, l2_regularization=0.5, random_state=42,
    )
    reg_ratio.fit(X_tr_sc, yr_tr)
    pred_ratio = np.clip(reg_ratio.predict(X_te_sc), -1.0, 1.0)
    print(f"  Ratio MAE : {mean_absolute_error(yr_te, pred_ratio):.4f}")

    print("\n" + "=" * 60)
    print("STEP 3b — Ratio-aware evaluation")
    print("=" * 60)
    r_mae     = _ratio_mae(yt1_te, yt2_te, pred_t1, pred_t2)
    r_acc     = _ratio_accuracy(yt1_te, yt2_te, pred_t1, pred_t2)
    r_out_acc = _ratio_outcome_accuracy(yt1_te, yt2_te, pred_t1, pred_t2)
    print(f"  Dominance ratio MAE          : {r_mae:.4f}")
    print(f"  Ratio accuracy (tol={RATIO_TOLERANCE:.2f})   : {r_acc*100:.2f}%")
    print(f"  Ratio-implied outcome acc    : {r_out_acc*100:.2f}%")

    print("\n" + "=" * 60)
    print("STEP 4 — Augmented classifier features")
    print("=" * 60)
    pred_t1_tr    = np.clip(reg_t1.predict(X_tr_sc), 0, None)
    pred_t2_tr    = np.clip(reg_t2.predict(X_tr_sc), 0, None)
    pred_ratio_tr = np.clip(reg_ratio.predict(X_tr_sc), -1.0, 1.0)

    X_clf_tr = np.hstack([X_tr_sc,
                           pred_t1_tr.reshape(-1, 1),
                           pred_t2_tr.reshape(-1, 1),
                           pred_ratio_tr.reshape(-1, 1)])
    X_clf_te = np.hstack([X_te_sc,
                           pred_t1.reshape(-1, 1),
                           pred_t2.reshape(-1, 1),
                           pred_ratio.reshape(-1, 1)])

    clf_scaler = StandardScaler()
    X_clf_tr_sc = clf_scaler.fit_transform(X_clf_tr)
    X_clf_te_sc = clf_scaler.transform(X_clf_te)
    print(f"  Classifier dims: {X_clf_tr_sc.shape[1]}")

    print("\n" + "=" * 60)
    print("STEP 5 — Outcome classifier")
    print("=" * 60)
    clf = _build_outcome_classifier()
    clf.fit(X_clf_tr_sc, yo_tr)

    pred_outcome = clf.predict(X_clf_te_sc)
    acc    = accuracy_score(yo_te, pred_outcome)
    report = classification_report(
        yo_te, pred_outcome,
        target_names=["team2 win (-1)", "draw (0)", "team1 win (1)"],
        labels=[-1, 0, 1],
    )
    print(f"  Hold-out Accuracy: {acc*100:.2f}%")
    print(report)

    print("=" * 60)
    print("STEP 6 — 5-Fold Stratified CV")
    print("=" * 60)
    cv_proxy = RandomForestClassifier(
        n_estimators=300, max_depth=8,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(
        cv_proxy, X_clf_tr_sc, yo_tr, cv=skf, scoring="accuracy", n_jobs=-1,
    )
    print(f"  CV Accuracy: {cv_scores.mean()*100:.2f}% ± {cv_scores.std()*100:.2f}%")
    print(f"  Per-fold   : {[f'{s*100:.1f}%' for s in cv_scores]}")

    print("\n" + "=" * 60)
    print("STEP 7 — Saving artefacts")
    print("=" * 60)
    os.makedirs(MODELS_DIR, exist_ok=True)
    for fname, obj in {
        "match_team_enc.pkl":       team_enc,
        "match_base_scaler.pkl":    base_scaler,
        "match_clf_scaler.pkl":     clf_scaler,
        "match_score_reg_t1.pkl":   reg_t1,
        "match_score_reg_t2.pkl":   reg_t2,
        "match_ratio_reg.pkl":      reg_ratio,
        "match_outcome_clf.pkl":    clf,
    }.items():
        joblib.dump(obj, os.path.join(MODELS_DIR, fname))
        print(f"  Saved: {fname}")

    outcome_map = {1: "team1_win", 0: "draw", -1: "team2_win"}
    pd.DataFrame({
        "actual_team1_score": yt1_te,
        "actual_team2_score": yt2_te,
        "pred_team1_score":   np.round(pred_t1, 2),
        "pred_team2_score":   np.round(pred_t2, 2),
        "actual_outcome":     [outcome_map[o] for o in yo_te],
        "pred_outcome":       [outcome_map[o] for o in pred_outcome],
    }).to_csv(os.path.join(MODELS_DIR, "match_test_predictions.csv"), index=False)

    metrics = {
        "split": {"train": int(len(X_tr)), "test": int(len(X_te)), "ratio": 0.20},
        "regression_team1_score": {
            "mae":  round(mean_absolute_error(yt1_te, pred_t1), 4),
            "rmse": round(mean_squared_error(yt1_te, pred_t1)**0.5, 4),
        },
        "regression_team2_score": {
            "mae":  round(mean_absolute_error(yt2_te, pred_t2), 4),
            "rmse": round(mean_squared_error(yt2_te, pred_t2)**0.5, 4),
        },
        "regression_dominance_ratio": {
            "ratio_mae":                  round(r_mae, 4),
            "ratio_accuracy_pct":         round(r_acc     * 100, 2),
            "ratio_outcome_accuracy_pct": round(r_out_acc * 100, 2),
            "ratio_tolerance_used":       RATIO_TOLERANCE,
        },
        "classification_outcome": {
            "hold_out_accuracy_pct": round(acc * 100, 2),
            "cv_accuracy_mean_pct":  round(float(cv_scores.mean()) * 100, 2),
            "cv_accuracy_std_pct":   round(float(cv_scores.std())  * 100, 2),
            "classification_report": report,
        },
        "features": {
            "base_feature_count": len(BASE_FEATURE_COLS),
            "clf_feature_count":  len(CLF_FEATURE_COLS),
        },
        "known_teams": list(team_enc.classes_),
    }
    with open(os.path.join(MODELS_DIR, "match_model_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Training complete.  Hold-out accuracy: {acc*100:.2f}%\n")


# ---------------------------------------------------------------------------
# Lazy inference cache
# ---------------------------------------------------------------------------

_team_enc:     Optional[LabelEncoder]                  = None
_base_scaler:  Optional[StandardScaler]                = None
_clf_scaler:   Optional[StandardScaler]                = None
_score_reg_t1: Optional[HistGradientBoostingRegressor] = None
_score_reg_t2: Optional[HistGradientBoostingRegressor] = None
_ratio_reg:    Optional[HistGradientBoostingRegressor] = None
_outcome_clf:  Optional[CalibratedClassifierCV]        = None


def _load_models() -> None:
    global _team_enc, _base_scaler, _clf_scaler
    global _score_reg_t1, _score_reg_t2, _ratio_reg, _outcome_clf
    if _team_enc is None:
        _team_enc     = joblib.load(os.path.join(MODELS_DIR, "match_team_enc.pkl"))
        _base_scaler  = joblib.load(os.path.join(MODELS_DIR, "match_base_scaler.pkl"))
        _clf_scaler   = joblib.load(os.path.join(MODELS_DIR, "match_clf_scaler.pkl"))
        _score_reg_t1 = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t1.pkl"))
        _score_reg_t2 = joblib.load(os.path.join(MODELS_DIR, "match_score_reg_t2.pkl"))
        _ratio_reg    = joblib.load(os.path.join(MODELS_DIR, "match_ratio_reg.pkl"))
        _outcome_clf  = joblib.load(os.path.join(MODELS_DIR, "match_outcome_clf.pkl"))


# ---------------------------------------------------------------------------
# Public inference API
# ---------------------------------------------------------------------------

def predict_match(
    team1: str,
    team2: str,
    team1_attack: int,  team1_mid: int,  team1_def: int,  team1_overall: int,
    team2_attack: int,  team2_mid: int,  team2_def: int,  team2_overall: int,
    is_home: int = 0,
    team1_rank: int   = 12,  team1_form: int   = 2,
    team1_points: int = 30,  team1_gf: int     = 30,  team1_ga: int = 30,
    team2_rank: int   = 12,  team2_form: int   = 2,
    team2_points: int = 30,  team2_gf: int     = 30,  team2_ga: int = 30,
) -> dict:
    """
    Predict the result of a match.

    is_home : 1 = team1 is the home side, 0 = neutral venue.
              Always pass the correct per-fixture value.
              Hardcoding 1 for every call biases every prediction to team1.

    Returns
    -------
    dict keys:
      team1_score_pred    float  — raw regressed goals, team1
      team2_score_pred    float  — raw regressed goals, team2
      score_display       str    — ratio-rounded scoreline, e.g. "2-1"
      score_diff          float  — team1_pred - team2_pred
      outcome             str    — classifier primary result
      outcome_from_scores str    — threshold-rule secondary result
      outcome_proba       dict   — calibrated win/draw/loss probabilities
    """
    _load_models()

    known = set(_team_enc.classes_)
    for name, role in [(team1, "team1"), (team2, "team2")]:
        if name not in known:
            raise ValueError(
                f"Unknown team '{name}' ({role}). Re-train with compile_model()."
            )

    team1_gd     = team1_gf - team1_ga
    team2_gd     = team2_gf - team2_ga
    attack_diff  = team1_attack  - team2_attack
    mid_diff     = team1_mid     - team2_mid
    defense_diff = team1_def     - team2_def
    overall_diff = team1_overall - team2_overall
    rank_diff    = team2_rank    - team1_rank
    form_diff    = team1_form    - team2_form
    points_diff  = team1_points  - team2_points
    gd_diff      = team1_gd      - team2_gd

    X_base = np.array([[
        _team_enc.transform([team1])[0],
        _team_enc.transform([team2])[0],
        is_home,
        team1_attack, team1_mid, team1_def, team1_overall,
        team2_attack, team2_mid, team2_def, team2_overall,
        attack_diff,  mid_diff,  defense_diff, overall_diff,
        abs(attack_diff), abs(mid_diff), abs(defense_diff), abs(overall_diff),
        team1_rank, team1_form, team1_points, team1_gf, team1_ga, team1_gd,
        team2_rank, team2_form, team2_points, team2_gf, team2_ga, team2_gd,
        rank_diff,   form_diff,   points_diff,   gd_diff,
        abs(rank_diff), abs(form_diff), abs(points_diff), abs(gd_diff),
    ]], dtype=float)

    X_base_sc = _base_scaler.transform(X_base)

    t1_pred = round(float(max(0.0, _score_reg_t1.predict(X_base_sc)[0])), 2)
    t2_pred = round(float(max(0.0, _score_reg_t2.predict(X_base_sc)[0])), 2)
    ratio_p = float(np.clip(_ratio_reg.predict(X_base_sc)[0], -1.0, 1.0))

    score_diff = round(t1_pred - t2_pred, 4)
    if score_diff >  SCORE_DIFF_THRESHOLD:
        outcome_from_scores = "team1_win"
    elif score_diff < -SCORE_DIFF_THRESHOLD:
        outcome_from_scores = "team2_win"
    else:
        outcome_from_scores = "draw"

    X_clf    = np.hstack([X_base_sc, [[t1_pred, t2_pred, ratio_p]]])
    X_clf_sc = _clf_scaler.transform(X_clf)

    outcome_code = int(_outcome_clf.predict(X_clf_sc)[0])
    proba_raw    = _outcome_clf.predict_proba(X_clf_sc)[0]
    classes      = list(_outcome_clf.classes_)

    outcome_proba = {
        "team1_win": round(float(proba_raw[classes.index( 1)]), 4),
        "draw":      round(float(proba_raw[classes.index( 0)]), 4),
        "team2_win": round(float(proba_raw[classes.index(-1)]), 4),
    }

    return {
        "team1_score_pred":    t1_pred,
        "team2_score_pred":    t2_pred,
        "score_display":       _display_score(t1_pred, t2_pred),
        "score_diff":          score_diff,
        "outcome":             {1: "team1_win", 0: "draw", -1: "team2_win"}[outcome_code],
        "outcome_from_scores": outcome_from_scores,
        "outcome_proba":       outcome_proba,
    }


# ---------------------------------------------------------------------------
# Backtest — all finished matches from both tables
# ---------------------------------------------------------------------------

def run_backtest() -> None:
    """
    Run predictions on big matches using ratio-based score rounding.
    """

    print("\n" + "=" * 100)
    print("BIG MATCH PREDICTIONS (RATIO-BASED SCORES)")
    print("=" * 100)

    _load_models()

    FIXTURES = [
        ("Man City", "Arsenal"),
        ("Real Madrid", "Barça"),
        ("Bayern", "PSG"),
        ("Liverpool", "Man United"),
        ("Inter", "Milan"),
        ("Chelsea", "Tottenham"),
        ("Arsenal", "Atleti"),
        ("Bayern", "Real Oviedo")
    ]

    db = SessionLocal()
    try:
        standings = _load_standings_lookup(db)

        teams = list({t for pair in FIXTURES for t in pair})

        clubs_data = db.query(
            Club.name,
            Club.attack,
            Club.midfield,
            Club.defence,
            Club.overall,
        ).filter(Club.name.in_(teams)).all()

    finally:
        db.close()

    clubs = {
        c.name: {
            "attack": int(c.attack),
            "mid": int(c.midfield),
            "def": int(c.defence),
            "overall": int(c.overall),
        }
        for c in clubs_data
        if None not in (c.attack, c.midfield, c.defence, c.overall)
    }

    print(f"{'#':<4} {'Team 1':<22} {'Team 2':<22} {'Prediction':<15} {'Score':<12}")

    for idx, (t1, t2) in enumerate(FIXTURES, 1):

        if t1 not in clubs or t2 not in clubs:
            print(f"{idx:<4} {t1:<22} {t2:<22} SKIPPED")
            continue

        c1, c2 = clubs[t1], clubs[t2]
        s1 = standings.get(t1, {})
        s2 = standings.get(t2, {})

        result = predict_match(
            team1=t1, team2=t2,

            team1_attack=c1["attack"], team1_mid=c1["mid"],
            team1_def=c1["def"],       team1_overall=c1["overall"],

            team2_attack=c2["attack"], team2_mid=c2["mid"],
            team2_def=c2["def"],       team2_overall=c2["overall"],

            is_home=1,

            team1_rank=s1.get("rank", 12),
            team1_form=s1.get("form", 2),
            team1_points=s1.get("points", 30),
            team1_gf=s1.get("gf", 30),
            team1_ga=s1.get("ga", 30),

            team2_rank=s2.get("rank", 12),
            team2_form=s2.get("form", 2),
            team2_points=s2.get("points", 30),
            team2_gf=s2.get("gf", 30),
            team2_ga=s2.get("ga", 30),
        )

        t1_pred = result["team1_score_pred"]
        t2_pred = result["team2_score_pred"]

        # -----------------------------
        # 🔥 Ratio-based rounding logic
        # -----------------------------
        if t2_pred == 0:
            t1_final = round(t1_pred)
            t2_final = 0
        else:
            ratio = t1_pred / t2_pred
            base_total = max(1, round(t1_pred + t2_pred))

            t1_final = round((ratio / (1 + ratio)) * base_total)
            t2_final = base_total - t1_final

        score_str = f"{t1_final}-{t2_final}"

        print(
            f"{idx:<4} {t1:<22} {t2:<22} "
            f"{result['outcome']:<15} {score_str:<12}"
        )

    print("\n")

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

# run for model generation - python3 -m app.ai_models.match_score
# run for prediction only - python3 -m app.ai_models.match_score --predict

if __name__ == "__main__":
    import sys
    if "--predict" in sys.argv:
        run_backtest()
    else:
        compile_model()
        run_backtest()