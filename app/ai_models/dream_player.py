import os
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
from sklearn.model_selection import train_test_split

CSV_FILE = os.path.join(os.path.dirname(__file__), "stats.csv")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "compiled_models")

COLUMNS = [
    "player_positions",
    "pace", "shooting", "passing",
    "dribbling", "defending", "physic",
    "overall",
]

FEATURES = [
    "pace", "shooting", "passing", "dribbling",
    "defending", "physic",
]

POSITION_GROUPS = {
    "GK": "GK",
    "CB": "DEF", "LB": "DEF", "RB": "DEF", "LWB": "DEF", "RWB": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "LW": "ATT", "RW": "ATT", "CF": "ATT", "ST": "ATT", "LF": "ATT", "RF": "ATT",
}


def load_data(csv_file):
    df = pd.read_csv(csv_file, usecols=COLUMNS)
    df = df.dropna(subset=COLUMNS)

    df["positions_list"] = (
        df["player_positions"]
        .str.split(",")
        .apply(lambda lst: [p.strip() for p in lst if p.strip()])
    )

    df["primary_position"] = df["positions_list"].str[0]

    capped = []
    for pos, group in df.groupby("primary_position"):
        capped.append(group.sample(min(len(group), 200_000), random_state=42))
    df = pd.concat(capped, ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


def preprocess_data(df):
    mlb = MultiLabelBinarizer()
    y_positions = mlb.fit_transform(df["positions_list"]).astype("float32")

    X = df[FEATURES].values.astype("float32")
    y_rating = df["overall"].values.astype("float32")

    return X, y_rating, y_positions, mlb


def build_position_model(input_dim, num_classes):
    model = Sequential([
        Input(shape=(input_dim,)),
        Dense(128, activation="relu"),
        BatchNormalization(),
        Dropout(0.3),
        Dense(64, activation="relu"),
        BatchNormalization(),
        Dropout(0.2),
        Dense(32, activation="relu"),
        Dense(num_classes, activation="sigmoid"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=[tf.keras.metrics.BinaryAccuracy(name="binary_acc"),
                 tf.keras.metrics.AUC(name="auc", multi_label=True)],
    )
    return model


def build_rating_model(input_dim):
    model = Sequential([
        Input(shape=(input_dim,)),
        Dense(64, activation="relu"),
        BatchNormalization(),
        Dropout(0.2),
        Dense(32, activation="relu"),
        Dense(1, activation="linear"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="mae",
        metrics=["mae"],
    )
    return model


def evaluate_position_model(model, X_test, y_test, mlb):
    probs = model.predict(X_test, verbose=0)

    top1_idx = np.argmax(probs, axis=1)
    rows = np.arange(len(y_test))
    top1_hits = y_test[rows, top1_idx] > 0.5
    top1_acc = top1_hits.mean()

    top2_idx = np.argsort(probs, axis=1)[:, -2:]
    top2_hits = (y_test[rows[:, None], top2_idx] > 0.5).any(axis=1)
    top2_acc = top2_hits.mean()

    classes = list(mlb.classes_)
    pred_groups = np.array([POSITION_GROUPS.get(classes[i], "?") for i in top1_idx])

    group_hits = np.zeros(len(y_test), dtype=bool)
    for i, true_row in enumerate(y_test):
        true_pos_idx = np.where(true_row > 0.5)[0]
        true_groups = {POSITION_GROUPS.get(classes[j], "?") for j in true_pos_idx}
        group_hits[i] = pred_groups[i] in true_groups
    group_acc = group_hits.mean()

    return top1_acc, top2_acc, group_acc


def train_position_model(X_train, X_test, y_train, y_test, mlb):
    early_stop = EarlyStopping(monitor="val_loss", patience=3, min_delta=1e-4, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)

    model = build_position_model(X_train.shape[1], y_train.shape[1])
    model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=50,
        batch_size=4096,
        callbacks=[early_stop, reduce_lr],
        verbose=2,
    )

    evaluate_position_model(model, X_test, y_test, mlb)
    return model


def train_rating_model(X_train, X_test, y_train, y_test):
    early_stop = EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)

    model = build_rating_model(X_train.shape[1])
    model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=50,
        batch_size=4096,
        callbacks=[early_stop, reduce_lr],
        verbose=2,
    )

    _, mae = model.evaluate(X_test, y_test, verbose=0)
    print(f"Rating MAE: {mae:.2f}")

    return model


def compile_and_save_models():
    df = load_data(CSV_FILE)
    X, y_rating, y_positions, mlb = preprocess_data(df)

    stratify_key = df["primary_position"].values
    X_train, X_test, y_rating_train, y_rating_test, y_pos_train, y_pos_test = train_test_split(
        X, y_rating, y_positions,
        test_size=0.2, random_state=42,
        stratify=stratify_key
    )

    feature_scaler = StandardScaler()
    X_train_scaled = feature_scaler.fit_transform(X_train)
    X_test_scaled = feature_scaler.transform(X_test)

    position_model = train_position_model(
        X_train_scaled, X_test_scaled,
        y_pos_train, y_pos_test,
        mlb,
    )

    rating_model = train_rating_model(
        X_train_scaled, X_test_scaled,
        y_rating_train, y_rating_test,
    )


    os.makedirs(MODELS_DIR, exist_ok=True)
    position_model.save(os.path.join(MODELS_DIR, "position_model.keras"))
    rating_model.save(os.path.join(MODELS_DIR, "rating_model.keras"))
    joblib.dump(feature_scaler, os.path.join(MODELS_DIR, "feature_scaler.pkl"))
    joblib.dump(mlb, os.path.join(MODELS_DIR, "position_binarizer.pkl"))


def predict_players(players):
    position_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "position_model.keras"))
    rating_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "rating_model.keras"))
    feature_scaler = joblib.load(os.path.join(MODELS_DIR, "feature_scaler.pkl"))
    mlb = joblib.load(os.path.join(MODELS_DIR, "position_binarizer.pkl"))

    df = pd.DataFrame(players)
    X_new = df[FEATURES].values.astype("float32")
    X_new_scaled = feature_scaler.transform(X_new)

    rating_preds = rating_model.predict(X_new_scaled, verbose=0).flatten()
    position_probs = position_model.predict(X_new_scaled, verbose=0)

    classes = list(mlb.classes_)

    results = []
    for i, (rating, probs) in enumerate(zip(rating_preds, position_probs)):
        order = np.argsort(probs)[::-1]
        top1, top2 = order[0], order[1]
        primary_pos = classes[top1]
        results.append({
            "player": i + 1,
            "rating": round(float(np.clip(rating, 0, 100)), 1),
            "position": primary_pos,
            "position_confidence": round(float(probs[top1]), 3),
            "alt_position": classes[top2],
            "alt_confidence": round(float(probs[top2]), 3),
            "group": POSITION_GROUPS.get(primary_pos, "?"),
        })

    return results


# python3 -m app.ai_models.dream_player
if __name__ == "__main__":
    compile_and_save_models()
    sample_players = [
        {
            "pace": 88, "shooting": 92, "passing": 80,
            "dribbling": 89, "defending": 35, "physic": 78
        },
        {
            "pace": 65, "shooting": 40, "passing": 70,
            "dribbling": 60, "defending": 88, "physic": 85
        },
        {
            "pace": 75, "shooting": 70, "passing": 88,
            "dribbling": 82, "defending": 60, "physic": 70
        },
        {
            "pace": 90, "shooting": 75, "passing": 78,
            "dribbling": 92, "defending": 40, "physic": 65
        },
        {
            "pace": 70, "shooting": 55, "passing": 75,
            "dribbling": 68, "defending": 80, "physic": 78
        },
    ]

    results = predict_players(sample_players)

    for r in results:
        print(f"\nPlayer {r['player']}:")
        print(f"  Rating: {r['rating']}")
        print(f"  Position: {r['position']} ({r['position_confidence'] * 100:.1f}%) [{r['group']}]")
        print(f"  Alt position: {r['alt_position']} ({r['alt_confidence'] * 100:.1f}%)")