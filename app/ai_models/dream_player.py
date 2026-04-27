import os
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import SGDClassifier, LinearRegression
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.utils.class_weight import compute_class_weight

CSV_FILE = os.path.join(os.path.dirname(__file__), "stats.csv")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "compiled_models")

COLUMNS = [
    "player_positions",
    "pace", "shooting", "passing",
    "dribbling", "defending", "physic",
    "overall",
]


def load_data(csv_file):
    df = pd.read_csv(csv_file, usecols=COLUMNS)
    df = df.dropna(subset=COLUMNS)

    df["player_positions"] = (
        df["player_positions"]
        .str.split(",")
        .str[0]
        .str.strip()
    )

    capped = []
    for pos, group in df.groupby("player_positions"):
        capped.append(group.sample(min(len(group), 200_000), random_state=42))
    df = pd.concat(capped, ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


def preprocess_data(df):
    le = LabelEncoder()
    y_encoded = le.fit_transform(df["player_positions"])

    df["att_ratio"] = (df["shooting"] + df["dribbling"]) / (df["defending"] + 1)
    df["def_ratio"] = df["defending"] / (df["physic"] + 1)
    df["pass_ratio"] = df["passing"] / (df["pace"] + 1)

    features = ["pace", "shooting", "passing", "dribbling",
                "defending", "physic", "att_ratio", "def_ratio", "pass_ratio"]
    X = df[features].values.astype("float32")
    y_rating = df["overall"].values.astype("float32")

    return X, y_rating, y_encoded, le


def train_models():
    df = load_data(CSV_FILE)
    X, y_rating, y_encoded, le = preprocess_data(df)

    X_train, X_test, y_rating_train, y_rating_test, y_encoded_train, y_encoded_test = train_test_split(
        X, y_rating, y_encoded,
        test_size=0.2, random_state=42,
        stratify=y_encoded
    )

    feature_scaler = StandardScaler()
    X_train_scaled = feature_scaler.fit_transform(X_train)
    X_test_scaled = feature_scaler.transform(X_test)

    num_classes = len(le.classes_)
    classes = np.arange(num_classes)

    weights = compute_class_weight(
        class_weight='balanced',
        classes=classes,
        y=y_encoded_train
    )
    class_weight_dict = {i: w for i, w in enumerate(weights)}

    position_model = SGDClassifier(
        loss='log_loss',
        class_weight=class_weight_dict,
        random_state=42,
        learning_rate='optimal'
    )

    epochs = 20
    batch_size = 4096
    n_samples = len(X_train_scaled)
    n_batches = (n_samples + batch_size - 1) // batch_size

    for epoch in range(1, epochs + 1):
        shuffle_idx = np.random.permutation(n_samples)
        X_shuffled = X_train_scaled[shuffle_idx]
        y_shuffled = y_encoded_train[shuffle_idx]

        for i in range(n_batches):
            start = i * batch_size
            end = min(start + batch_size, n_samples)
            X_batch = X_shuffled[start:end]
            y_batch = y_shuffled[start:end]
            position_model.partial_fit(X_batch, y_batch, classes=classes)

        train_acc = accuracy_score(y_encoded_train, position_model.predict(X_train_scaled))
        val_acc = accuracy_score(y_encoded_test, position_model.predict(X_test_scaled))
        print(f"\rEpoch {epoch}/{epochs} - train_acc: {train_acc:.4f} - val_acc: {val_acc:.4f}")

    rating_model = LinearRegression()
    rating_model.fit(X_train_scaled, y_rating_train)

    position_preds = position_model.predict(X_test_scaled)
    position_accuracy = accuracy_score(y_encoded_test, position_preds)

    rating_preds = rating_model.predict(X_test_scaled)
    rating_mae = mean_absolute_error(y_rating_test, rating_preds)

    print(f"Position accuracy: {position_accuracy:.3f}")
    print(f"Rating MAE: {rating_mae:.2f}")

    return position_model, rating_model, feature_scaler, le


def save_models(position_model, rating_model, feature_scaler, le):
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(position_model, os.path.join(MODELS_DIR, 'position_model.pkl'))
    joblib.dump(rating_model, os.path.join(MODELS_DIR, 'rating_model.pkl'))
    joblib.dump(feature_scaler, os.path.join(MODELS_DIR, 'feature_scaler.pkl'))
    joblib.dump(le, os.path.join(MODELS_DIR, 'label_encoder.pkl'))


def predict_players(players):
    position_model = joblib.load(os.path.join(MODELS_DIR, 'position_model.pkl'))
    rating_model = joblib.load(os.path.join(MODELS_DIR, 'rating_model.pkl'))
    feature_scaler = joblib.load(os.path.join(MODELS_DIR, 'feature_scaler.pkl'))
    le = joblib.load(os.path.join(MODELS_DIR, 'label_encoder.pkl'))

    rows = []
    for p in players:
        pace = p['pace']
        shooting = p['shooting']
        passing = p['passing']
        dribbling = p['dribbling']
        defending = p['defending']
        physic = p['physic']
        att_ratio = (shooting + dribbling) / (defending + 1)
        def_ratio = defending / (physic + 1)
        pass_ratio = passing / (pace + 1)
        rows.append([pace, shooting, passing, dribbling, defending, physic,
                     att_ratio, def_ratio, pass_ratio])

    X_new = np.array(rows, dtype="float32")
    X_new_scaled = feature_scaler.transform(X_new)

    rating_preds = rating_model.predict(X_new_scaled)
    position_probs = position_model.predict_proba(X_new_scaled)

    results = []
    for i, (rating, probs) in enumerate(zip(rating_preds, position_probs)):
        top2 = np.argsort(probs)[::-1][:2]
        results.append({
            "player": i + 1,
            "rating": round(float(np.clip(rating, 0, 100)), 1),
            "position": le.classes_[top2[0]],
            "position_confidence": round(float(probs[top2[0]]), 3),
            "alt_position": le.classes_[top2[1]],
            "alt_confidence": round(float(probs[top2[1]]), 3),
        })

    return results


# python3 -m app.ai_models.dream_player
if __name__ == "__main__":
    position_model, rating_model, feature_scaler, le = train_models()
    save_models(position_model, rating_model, feature_scaler, le)

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
        print(f"  Position: {r['position']} ({r['position_confidence'] * 100:.1f}%)")
        print(f"  Alt position: {r['alt_position']} ({r['alt_confidence'] * 100:.1f}%)")