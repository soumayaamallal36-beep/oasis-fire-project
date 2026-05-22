"""
src/prediction/model_inference.py
-----------------------------------
Étape 3 du pipeline ML.

Responsabilité :
  • Charger le modèle entraîné (singleton, chargement unique)
  • Prédire le risque pour un point unique ou un batch
  • Produire une sortie structurée (label + confiance + probabilités)

Usage :
    from src.prediction.model_inference import predict_risque, predict_batch

    label, conf, probas = predict_risque(
        temperature=33, humidite=15, precipitation=1, vent=4.5
    )

    # Batch
    results = predict_batch(df_scenarios)
"""

from pathlib import Path

import joblib
import pandas as pd

from src.prediction.feature_engineering import FEATURE_COLUMNS, prepare_input
from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT       = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / CFG["chemins"]["modele"]
LE_PATH    = ROOT / CFG["chemins"]["encodeur"]

_model = None
_le    = None


def _load_model():
    """Charge le modèle en mémoire une seule fois (singleton)."""
    global _model, _le
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Modèle introuvable : {MODEL_PATH}\n"
                "Lancez d'abord : python -m src.prediction.model_training"
            )
        _model = joblib.load(MODEL_PATH)
        _le    = joblib.load(LE_PATH)
        log.info("Modèle chargé depuis %s", MODEL_PATH)


# ─────────────────────────────────────────────────────────────
def predict_risque(
    temperature: float,
    humidite: float,
    precipitation: float,
    vent: float,
    mois: str = "Juillet",
    ndvi_avant: float = 0.144,
    **topo_kwargs,
) -> tuple[str, float, dict]:
    """
    Prédit le niveau de risque pour un jeu de conditions climatiques.

    Paramètres
    ----------
    temperature   : °C (température moyenne du mois)
    humidite      : % (humidité relative)
    precipitation : mm (précipitations du mois)
    vent          : m/s (vitesse moyenne du vent)
    mois          : "Juin" | "Juillet" | "Aout"
    ndvi_avant    : NDVI avant incendie (défaut zone Agdez)
    **topo_kwargs : pente, altitude, exposition (optionnel)

    Retour
    ------
    (label: str, confiance: float, probas: dict)

    Exemple
    -------
    >>> label, conf, p = predict_risque(33, 15, 1, 4.5)
    >>> print(label, f"{conf:.0%}")
    Très élevé  99%
    """
    _load_model()
    X = prepare_input(temperature, humidite, precipitation, vent,
                      mois=mois, ndvi_avant=ndvi_avant, **topo_kwargs)

    y_num  = _model.predict(X)[0]
    probas = _model.predict_proba(X)[0]
    label  = _le.inverse_transform([y_num])[0]
    conf   = float(probas.max())

    proba_dict = {
        cls: round(float(p), 4)
        for cls, p in zip(_le.classes_, probas)
    }

    log.debug("predict_risque → %s (%.1f%%)", label, conf * 100)
    return label, conf, proba_dict


# ─────────────────────────────────────────────────────────────
def predict_batch(df_scenarios: pd.DataFrame) -> pd.DataFrame:
    """
    Prédictions en lot sur un DataFrame de scénarios.

    Colonnes attendues dans df_scenarios :
        temperature, humidite, precipitation, vent
        mois (optionnel, défaut "Juillet")
        ndvi_avant (optionnel, défaut 0.144)

    Retour
    ------
    DataFrame original + colonnes :
        risque_predit, confiance, prob_faible, prob_moyen,
        prob_eleve, prob_tres_eleve
    """
    _load_model()
    records = []
    for _, row in df_scenarios.iterrows():
        label, conf, probas = predict_risque(
            temperature   = row["temperature"],
            humidite      = row["humidite"],
            precipitation = row["precipitation"],
            vent          = row["vent"],
            mois          = row.get("mois", "Juillet"),
            ndvi_avant    = row.get("ndvi_avant", 0.144),
        )
        records.append({
            "risque_predit":   label,
            "confiance":       round(conf, 4),
            "prob_faible":     probas.get("Faible", 0),
            "prob_moyen":      probas.get("Moyen", 0),
            "prob_eleve":      probas.get("Élevé", 0),
            "prob_tres_eleve": probas.get("Très élevé", 0),
        })

    return pd.concat(
        [df_scenarios.reset_index(drop=True), pd.DataFrame(records)],
        axis=1
    )
