"""
components/prediction.py
─────────────────────────
Centralized prediction wrapper — loads model once via st.cache_resource.
"""

import sys
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.prediction.feature_engineering import FEATURE_COLUMNS, build_features

MODEL_PATH = PROJECT_ROOT / "models" / "trained" / "model_risque_incendie.pkl"
LE_PATH    = PROJECT_ROOT / "models" / "trained" / "label_encoder.pkl"

ZONE = {"pente": 5.73, "altitude": 1169.3, "exposition": 165.51}
MOIS_MAP = {"Juin": 0, "Juillet": 1, "Août": 2, "Aout": 2,
            "Janvier":0,"Février":0,"Mars":0,"Avril":0,"Mai":0,
            "Septembre":2,"Octobre":2,"Novembre":0,"Décembre":0}

RISK_COLORS = {
    "Faible":     "#3fb950",
    "Moyen":      "#d29922",
    "Élevé":      "#f0883e",
    "Très élevé": "#f85149",
}
RISK_BG = {
    "Faible":     "rgba(63,185,80,0.12)",
    "Moyen":      "rgba(210,153,34,0.12)",
    "Élevé":      "rgba(240,136,62,0.12)",
    "Très élevé": "rgba(248,81,73,0.15)",
}


@st.cache_resource(show_spinner=False)
def load_model():
    """Load model and label encoder once for the session."""
    model = joblib.load(MODEL_PATH)
    le    = joblib.load(LE_PATH)
    return model, le


def predict_risk(temperature, humidite, precipitation, vent,
                 mois="Juillet", ndvi=0.144):
    """Return (label, confidence, proba_dict)."""
    model, le = load_model()
    mois_num = MOIS_MAP.get(mois, 1)
    row = {
        "temperature": temperature, "humidite": humidite,
        "precipitation": precipitation, "vent": vent,
        "pente": ZONE["pente"], "altitude": ZONE["altitude"],
        "exposition": ZONE["exposition"],
        "ndvi_avant": ndvi, "mois_num": mois_num,
    }
    df = pd.DataFrame([row])
    df = build_features(df)
    X  = df[FEATURE_COLUMNS]
    y_pred = model.predict(X)[0]
    probas = model.predict_proba(X)[0]
    label  = le.inverse_transform([y_pred])[0]
    conf   = float(probas.max())
    proba_dict = {c: round(float(p), 4) for c, p in zip(le.classes_, probas)}
    return label, conf, proba_dict


def get_current_prediction(weather: dict):
    ts    = weather.get("timestamp", "")
    month = datetime.fromisoformat(ts[:19]).month if ts else datetime.now().month
    month_name = {6:"Juin",7:"Juillet",8:"Août"}.get(month, "Juillet")
    return predict_risk(
        weather["temperature"], weather["humidite"],
        weather["precipitation"], weather["vent"], mois=month_name,
    )


def risk_recommendation(label: str) -> str:
    recs = {
        "Faible":     "✅ Conditions favorables. Surveillance standard.",
        "Moyen":      "⚠️ Vigilance accrue. Vérifier les équipements de détection.",
        "Élevé":      "🟠 Risque important. Activer surveillance renforcée et patrouilles terrain.",
        "Très élevé": "🔴 DANGER CRITIQUE. Activer le plan ORSEC forêt immédiatement.",
    }
    return recs.get(label, "")
