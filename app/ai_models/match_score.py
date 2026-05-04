import os
import json
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input, Embedding, Flatten, Concatenate
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from app.core.db import SessionLocal
from app.models import Match, Club

MODELS_DIR = os.path.join(os.path.dirname(__file__), "compiled_models/match_score")

NUMERIC_FEATURES = [
    "team1_attack", "team1_mid", "team1_def", "team1_overall",
    "team2_attack", "team2_mid", "team2_def", "team2_overall",
    "attack_diff", "mid_diff", "defense_diff", "overall_diff",
    "t1_attack_vs_t2_def", "t2_attack_vs_t1_def",
]

_t1_model = None
_t2_model = None
_feature_scaler = None
_team_encoder = None
_meta = None


def load_data() -> pd.DataFrame:
    """Load matches"""
    db = SessionLocal()
    matches = db.query(
        Match.team1, Match.team2, Match.winner,
        Match.team1_score, Match.team2_score,
    ).filter(
        Match.league.in_(["en.1", "es.1", "de.1", "it.1", "fr.1"])
    ).all()
    return pd.DataFrame(matches, columns=["team1", "team2", "winner", "team1_score", "team2_score"])


def load_clubs() -> pd.DataFrame:
    """Load clubs"""
    db = SessionLocal()
    clubs = db.query(Club.name, Club.attack, Club.midfield, Club.defence, Club.overall).all()
    clubs_df = pd.DataFrame(clubs, columns=["name", "attack", "midfield", "defence", "overall"])
    return clubs_df.drop_duplicates(subset=["name"])


def add_features(df: pd.DataFrame, clubs_df: pd.DataFrame) -> pd.DataFrame:
    """Join club ratings and compute rating diffs"""
    df = (df.merge(clubs_df, left_on="team1", right_on="name", how="left")
            .drop(columns=["name"])
            .rename(columns={"attack": "team1_attack", "midfield": "team1_mid",
                             "defence": "team1_def", "overall": "team1_overall"}))
    df = (df.merge(clubs_df, left_on="team2", right_on="name", how="left")
            .drop(columns=["name"])
            .rename(columns={"attack": "team2_attack", "midfield": "team2_mid",
                             "defence": "team2_def", "overall": "team2_overall"}))

    rating_cols = ["team1_attack", "team1_mid", "team1_def", "team1_overall",
                   "team2_attack", "team2_mid", "team2_def", "team2_overall"]
    df.dropna(subset=rating_cols, inplace=True)
    df[rating_cols] = df[rating_cols].astype(int)

    df["attack_diff"] = df["team1_attack"] - df["team2_attack"]
    df["mid_diff"] = df["team1_mid"] - df["team2_mid"]
    df["defense_diff"] = df["team1_def"] - df["team2_def"]
    df["overall_diff"] = df["team1_overall"] - df["team2_overall"]

    df["t1_attack_vs_t2_def"] = df["team1_attack"] - df["team2_def"]
    df["t2_attack_vs_t1_def"] = df["team2_attack"] - df["team1_def"]

    return df.reset_index(drop=True)


def process_data(df: pd.DataFrame):
    """Normalize and encode data"""
    df = df.dropna(subset=["team1_score", "team2_score"]).copy()

    team_encoder = LabelEncoder()
    team_encoder.fit(pd.concat([df["team1"], df["team2"]]).unique())
    df["team1_id"] = team_encoder.transform(df["team1"])
    df["team2_id"] = team_encoder.transform(df["team2"])

    feature_scaler = StandardScaler()
    df[NUMERIC_FEATURES] = feature_scaler.fit_transform(df[NUMERIC_FEATURES])

    X_numeric = df[NUMERIC_FEATURES].values.astype("float32")
    X_t1 = df["team1_id"].values.astype("int32")
    X_t2 = df["team2_id"].values.astype("int32")
    y_t1 = df["team1_score"].values.astype("float32")
    y_t2 = df["team2_score"].values.astype("float32")

    return X_numeric, X_t1, X_t2, y_t1, y_t2, team_encoder, feature_scaler


def build_model(num_features, num_teams, embed_dim=8):
    numeric_in = Input(shape=(num_features,), name="numeric")
    t1_in = Input(shape=(1,), name="team1_id", dtype="int32")
    t2_in = Input(shape=(1,), name="team2_id", dtype="int32")

    team_embed = Embedding(num_teams, embed_dim, name="team_embed")
    t1_vec = Flatten()(team_embed(t1_in))
    t2_vec = Flatten()(team_embed(t2_in))

    x = Concatenate()([numeric_in, t1_vec, t2_vec])
    x = Dense(128, activation="relu")(x)
    x = BatchNormalization()(x)
    x = Dropout(0.1)(x)
    x = Dense(64, activation="relu")(x)
    x = BatchNormalization()(x)
    x = Dense(32, activation="relu")(x)

    out = Dense(1, activation="exponential")(x)

    model = Model(inputs=[numeric_in, t1_in, t2_in], outputs=out)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=tf.keras.losses.Poisson(),
        metrics=["mae", "mse"],
    )
    return model


def train_one(name, num_features, num_teams, train_inputs, y_tr, val_inputs, y_te):
    """Train one model"""
    early_stop = EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, min_lr=1e-5)

    model = build_model(num_features, num_teams)
    model.fit(
        train_inputs, y_tr,
        validation_data=(val_inputs, y_te),
        epochs=100,
        batch_size=256,
        callbacks=[early_stop, reduce_lr],
        verbose=2,
    )

    preds = np.clip(model.predict(val_inputs, verbose=0).flatten(), 0, None)
    mae = np.mean(np.abs(preds - y_te))
    rmse = np.sqrt(np.mean((preds - y_te) ** 2))
    print(f"\n--- {name} accuracy ---")
    print(f"MAE : {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"Pred range: [{preds.min():.2f}, {preds.max():.2f}]  mean={preds.mean():.2f}")

    return model, preds, mae, rmse


def score_to_outcome(t1, t2, threshold=0.5):
    """Return 'win' (team1), 'loss' (team2), or 'draw' based on score diff vs threshold."""
    d = t1 - t2
    if d > threshold:
        return "win"
    if d < -threshold:
        return "loss"
    return "draw"


def calibrate_threshold(pred_t1, pred_t2, actual_t1, actual_t2):
    """Grid-search the draw threshold that maximises outcome accuracy."""
    best_t, best_acc = 0.1, 0.0
    for t in np.arange(0.05, 1.5, 0.05):
        preds = [score_to_outcome(p1, p2, t) for p1, p2 in zip(pred_t1, pred_t2)]
        actuals = [score_to_outcome(a1, a2, 0.0) for a1, a2 in zip(actual_t1, actual_t2)]
        acc = sum(p == a for p, a in zip(preds, actuals)) / len(preds)
        if acc > best_acc:
            best_acc, best_t = acc, t
    return round(float(best_t), 2)


def compile_and_save_model():
    """Compile and save models"""
    matches = load_data()
    clubs_df = load_clubs()

    df = add_features(matches, clubs_df)
    X_num, X_t1, X_t2, y_t1, y_t2, team_encoder, feature_scaler = process_data(df)

    X_num_tr, X_num_te, X_t1_tr, X_t1_te, X_t2_tr, X_t2_te, yt1_tr, yt1_te, yt2_tr, yt2_te = train_test_split(
        X_num, X_t1, X_t2, y_t1, y_t2, test_size=0.2, random_state=42
    )

    num_features = X_num.shape[1]
    num_teams = len(team_encoder.classes_)
    train_inputs = [X_num_tr, X_t1_tr, X_t2_tr]
    val_inputs = [X_num_te, X_t1_te, X_t2_te]

    # train two independent regressors
    t1_model, pred_t1, t1_mae, t1_rmse = train_one(
        "team1_score", num_features, num_teams, train_inputs, yt1_tr, val_inputs, yt1_te
    )
    t2_model, pred_t2, t2_mae, t2_rmse = train_one(
        "team2_score", num_features, num_teams, train_inputs, yt2_tr, val_inputs, yt2_te
    )

    # calibrate draw threshold on TRAIN predictions (no leakage)
    train_pred_t1 = np.clip(t1_model.predict(train_inputs, verbose=0).flatten(), 0, None)
    train_pred_t2 = np.clip(t2_model.predict(train_inputs, verbose=0).flatten(), 0, None)
    draw_thr = calibrate_threshold(train_pred_t1, train_pred_t2, yt1_tr, yt2_tr)

    # combined accuracy: how often both rounded predictions match the actual scoreline
    rounded_t1 = np.clip(np.round(pred_t1), 0, None)
    rounded_t2 = np.clip(np.round(pred_t2), 0, None)
    exact_match = np.mean((rounded_t1 == yt1_te) & (rounded_t2 == yt2_te))
    within_1_both = np.mean((np.abs(rounded_t1 - yt1_te) <= 1) & (np.abs(rounded_t2 - yt2_te) <= 1))

    # outcome accuracy with calibrated threshold
    actual_outcomes = [score_to_outcome(a, b, 0.0) for a, b in zip(yt1_te, yt2_te)]
    pred_outcomes = [score_to_outcome(p, q, draw_thr) for p, q in zip(pred_t1, pred_t2)]
    outcome_acc = sum(a == p for a, p in zip(actual_outcomes, pred_outcomes)) / len(actual_outcomes)

    print("\n" + "=" * 50)
    print("OVERALL MODEL ACCURACY")
    print("=" * 50)
    print(f"team1 MAE / RMSE: {t1_mae:.3f} / {t1_rmse:.3f}")
    print(f"team2 MAE / RMSE: {t2_mae:.3f} / {t2_rmse:.3f}")
    print(f"Calibrated draw thresh: {draw_thr}")
    print(f"Exact scoreline match: {exact_match * 100:.2f}%")
    print(f"Both teams within ±1: {within_1_both * 100:.2f}%")
    print(f"Outcome (W/D/L) accuracy: {outcome_acc * 100:.2f}%")
    print("=" * 50)

    # save models
    os.makedirs(MODELS_DIR, exist_ok=True)
    t1_model.save(os.path.join(MODELS_DIR, "score_model_t1.keras"))
    t2_model.save(os.path.join(MODELS_DIR, "score_model_t2.keras"))
    joblib.dump(feature_scaler, os.path.join(MODELS_DIR, "score_feature_scaler.pkl"))
    joblib.dump(team_encoder, os.path.join(MODELS_DIR, "team_encoder.pkl"))

    meta = {
        "team1_score": {"mae": round(float(t1_mae), 4), "rmse": round(float(t1_rmse), 4)},
        "team2_score": {"mae": round(float(t2_mae), 4), "rmse": round(float(t2_rmse), 4)},
        "draw_threshold": draw_thr,
        "exact_scoreline_pct": round(float(exact_match) * 100, 2),
        "within_1_both_pct": round(float(within_1_both) * 100, 2),
        "outcome_accuracy_pct": round(float(outcome_acc) * 100, 2),
        "known_teams": list(team_encoder.classes_),
    }
    with open(os.path.join(MODELS_DIR, "match_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def _load_models():
    """Load models from disk"""
    global _t1_model, _t2_model, _feature_scaler, _team_encoder, _meta
    if _t1_model is None:
        _t1_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "score_model_t1.keras"))
        _t2_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "score_model_t2.keras"))
        _feature_scaler = joblib.load(os.path.join(MODELS_DIR, "score_feature_scaler.pkl"))
        _team_encoder = joblib.load(os.path.join(MODELS_DIR, "team_encoder.pkl"))
        with open(os.path.join(MODELS_DIR, "match_meta.json")) as f:
            _meta = json.load(f)


def _build_feature_row(t1_stats, t2_stats):
    """Build feature row"""
    row = {
        "team1_attack": t1_stats["attack"], "team1_mid": t1_stats["midfield"],
        "team1_def": t1_stats["defence"], "team1_overall": t1_stats["overall"],
        "team2_attack": t2_stats["attack"], "team2_mid": t2_stats["midfield"],
        "team2_def": t2_stats["defence"], "team2_overall": t2_stats["overall"],
        "attack_diff": t1_stats["attack"] - t2_stats["attack"],
        "mid_diff": t1_stats["midfield"] - t2_stats["midfield"],
        "defense_diff": t1_stats["defence"] - t2_stats["defence"],
        "overall_diff": t1_stats["overall"] - t2_stats["overall"],
        "t1_attack_vs_t2_def": t1_stats["attack"] - t2_stats["defence"],
        "t2_attack_vs_t1_def": t2_stats["attack"] - t1_stats["defence"],
    }
    return pd.DataFrame([row])[NUMERIC_FEATURES]


def predict_match(team1, team2, t1_stats: dict, t2_stats: dict):
    """Predict using two independent models"""
    _load_models()

    feat_df = _build_feature_row(t1_stats, t2_stats)
    feat_scaled = _feature_scaler.transform(feat_df).astype("float32")
    t1_id = np.array([_team_encoder.transform([team1])[0]], dtype="int32")
    t2_id = np.array([_team_encoder.transform([team2])[0]], dtype="int32")

    inputs = [feat_scaled, t1_id, t2_id]
    t1_raw = float(np.clip(_t1_model.predict(inputs, verbose=0).flatten()[0], 0, None))
    t2_raw = float(np.clip(_t2_model.predict(inputs, verbose=0).flatten()[0], 0, None))

    draw_thr = _meta.get("draw_threshold", 0.3)
    outcome = score_to_outcome(t1_raw, t2_raw, draw_thr)

    return {
        "team1_score_pred": round(t1_raw, 2),
        "team2_score_pred": round(t2_raw, 2),
        "team1_score_rounded": max(0, round(t1_raw)),
        "team2_score_rounded": max(0, round(t2_raw)),
        "score_diff": round(t1_raw - t2_raw, 2),
        "outcome": outcome,
    }


# python3 -m app.ai_models.match_score
if __name__ == "__main__":
    # compile_and_save_model()

    def print_predictions(team1_name: str, team2_name: str):
        db = SessionLocal()
        team1 = db.query(Club).filter(Club.name == team1_name).first()
        team2 = db.query(Club).filter(Club.name == team2_name).first()

        result = predict_match(
            team1.name, team2.name,
            {"attack": team1.attack, "midfield": team1.midfield,
            "defence": team1.defence, "overall": team1.overall},
            {"attack": team2.attack, "midfield": team2.midfield,
            "defence": team2.defence, "overall": team2.overall},
        )

        print("\n--- Match Prediction ---")
        print(f"{team1.name:<20} {result['team1_score_rounded']} - {result['team2_score_rounded']}  {team2.name}")
        print(f"Raw expected goals:  {result['team1_score_pred']:.2f} - {result['team2_score_pred']:.2f}")
        print(f"Outcome: {result['outcome']}")


    print_predictions("Bayern", "Real Madrid")
    print_predictions("Man City", "Arsenal")
    print_predictions("Liverpool", "Man United")
    print_predictions("Real Madrid", "Barça")