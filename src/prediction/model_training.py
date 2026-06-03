"""
src/prediction/model_training.py
----------------------------------
Étape 2 du pipeline ML.

Responsabilité :
  • Comparer Random Forest, Gradient Boosting, Logistic Regression
  • Sélectionner automatiquement le meilleur par validation croisée 5-fold
  • Sauvegarder le modèle final + encodeur + métadonnées JSON
  • Exporter l'importance des features (Random Forest)

Usage en ligne de commande :
    python -m src.prediction.model_training

Usage depuis un autre module :
    from src.prediction.model_training import train
    model, le = train()
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from src.prediction.feature_engineering import (
    FEATURE_COLUMNS,
    load_and_prepare_training_data,
)
from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR   = ROOT / "models" / "trained"
METADATA_DIR = ROOT / "models" / "metadata"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)

RISQUE_CLASSES: list[str] = CFG["risque"]["classes"]


# ─────────────────────────────────────────────────────────────
def _build_pipelines() -> dict[str, Pipeline]:
    """Retourne les pipelines ML à comparer."""
    hp = CFG["modele"]["hyperparams"]
    return {
        "Random Forest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                **hp["random_forest"],
                random_state=CFG["modele"]["random_seed"],
            )),
        ]),
        "Gradient Boosting": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                **hp["gradient_boosting"],
                random_state=CFG["modele"]["random_seed"],
            )),
        ]),
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                **hp["logistic_regression"],
                random_state=CFG["modele"]["random_seed"],
            )),
        ]),
    }


# ─────────────────────────────────────────────────────────────
def train() -> tuple:
    """
    Pipeline complet d'entraînement.

    Retour
    ------
    (meilleur_modele: Pipeline, label_encoder: LabelEncoder)
    """
    log.info("=" * 55)
    log.info("DÉMARRAGE ENTRAÎNEMENT — Risque Incendie Agdez")
    log.info("=" * 55)

    # 1. Chargement données ───────────────────────────────────
    df = load_and_prepare_training_data()
    X  = df[FEATURE_COLUMNS]

    le = LabelEncoder()
    le.classes_ = np.array(RISQUE_CLASSES)
    y  = le.transform(df["risque"])

    log.info("Features : %d | Classes : %s", len(FEATURE_COLUMNS), RISQUE_CLASSES)

    # 2. Validation croisée ───────────────────────────────────
    cv       = StratifiedKFold(
        n_splits=CFG["modele"]["cv_folds"],
        shuffle=True,
        random_state=CFG["modele"]["random_seed"],
    )
    pipelines = _build_pipelines()
    resultats: dict = {}

    log.info("Validation croisée %d-fold :", CFG["modele"]["cv_folds"])
    for nom, pipeline in pipelines.items():
        scores = cross_val_score(pipeline, X, y, cv=cv, scoring="accuracy")
        pipeline.fit(X, y)
        resultats[nom] = {
            "accuracy_mean": float(scores.mean()),
            "accuracy_std":  float(scores.std()),
            "pipeline":      pipeline,
        }
        log.info("  %-25s  acc=%.3f ± %.3f",
                 nom, scores.mean(), scores.std())

    # 3. Sélection du meilleur ────────────────────────────────
    meilleur_nom = max(resultats, key=lambda k: resultats[k]["accuracy_mean"])
    meilleur     = resultats[meilleur_nom]
    log.info("Meilleur modèle : %s  (acc=%.3f)", meilleur_nom,
             meilleur["accuracy_mean"])

    # 4. Sauvegarde modèle + encodeur ─────────────────────────
    model_path = MODELS_DIR / "model_risque_incendie.pkl"
    le_path    = MODELS_DIR / "label_encoder.pkl"
    joblib.dump(meilleur["pipeline"], model_path)
    joblib.dump(le, le_path)
    log.info("Modèle sauvegardé → %s", model_path)

    # 5. Importance des features (RF) ─────────────────────────
    rf_clf = resultats["Random Forest"]["pipeline"].named_steps["clf"]
    imp_df = pd.DataFrame({
        "feature":    FEATURE_COLUMNS,
        "importance": rf_clf.feature_importances_,
    }).sort_values("importance", ascending=False)
    imp_df.to_csv(METADATA_DIR / "feature_importance.csv", index=False)

    # 6. Métadonnées JSON ─────────────────────────────────────
    meta = {
        "modele":            meilleur_nom,
        "features":          FEATURE_COLUMNS,
        "classes":           RISQUE_CLASSES,
        "accuracy_cv":       round(meilleur["accuracy_mean"], 4),
        "accuracy_cv_std":   round(meilleur["accuracy_std"], 4),
        "n_echantillons":    len(df),
        "annees_train":      "2017–2025",
        "validation":        "StratifiedKFold 5-fold (pas de split train/test)",
        "zone":              CFG["zone"]["nom"],
        "pays":              CFG["zone"]["pays"],
        "version":           "1.0.0",
    }
    meta_path = METADATA_DIR / "model_info.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log.info("Métadonnées → %s", meta_path)

    log.info("Entraînement terminé.")
    return meilleur["pipeline"], le


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    train()
