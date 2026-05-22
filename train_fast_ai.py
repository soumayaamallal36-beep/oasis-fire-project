import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

# =========================
# LOAD DATA
# =========================

df = pd.read_csv(
    "data/final/final_dataset.csv"
)

# =========================
# CLEAN
# =========================

df = df.dropna()

# =========================
# LABELS
# =========================

risk_map = {
    "Faible": 0,
    "Moyen": 0,
    "Élevé": 1,
    "Très élevé": 1
}

df["risk"] = df["risk"].map(risk_map)

print(df["risk"].value_counts())

# =========================
# FEATURES
# =========================

X = df[
    [
        "temperature",
        "humidity",
        "precipitation",
        "wind"
    ]
]

# TARGET
y = df["risk"]

# =========================
# RANDOM FOREST
# =========================

rf_model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

rf_model.fit(X, y)

print("\n✅ RandomForest trained")

# =========================
# XGBOOST
# =========================

xgb_model = XGBClassifier()

xgb_model.fit(X, y)

print("✅ XGBoost trained")

# =========================
# SAVE MODEL
# =========================

joblib.dump(xgb_model, "best_model.pkl")

print("\n🔥 AI Model saved successfully")
