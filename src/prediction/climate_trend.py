"""
src/prediction/climate_trend.py
---------------------------------
IDÉE AJOUTÉE — Analyse des tendances climatiques.

Responsabilité :
  • Ajuster linéairement les variables climatiques sur 2017-2025
  • Projeter les conditions futures (2026-2035)
  • Évaluer l'évolution du risque selon le changement climatique

Méthode
-------
Régression linéaire simple sur chaque variable :
  f(année) = a × année + b
Projection : f(2026), f(2027), …, f(2035)

Cela permet de répondre à la question :
  "Si les tendances actuelles continuent, quel sera le risque
   d'incendie à Agdez en 2030 ?"

Usage :
    python -m src.prediction.climate_trend
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.prediction.feature_engineering import load_and_prepare_training_data
from src.prediction.model_inference import predict_batch
from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "models" / "metadata"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def project_climate(horizon: int = 2035) -> pd.DataFrame:
    """
    Projette les conditions climatiques estivales jusqu'à `horizon`.

    Paramètres
    ----------
    horizon : année cible maximale

    Retour
    ------
    DataFrame des projections avec risque prédit
    """
    df = load_and_prepare_training_data()

    # Sélectionner juillet uniquement (mois le plus critique)
    df_juil = df[df["mois"] == "Juillet"].copy()

    variables = ["temperature", "humidite", "precipitation", "vent"]
    annees    = df_juil["annee"].values.reshape(-1, 1)
    modeles_reg = {}

    for v in variables:
        reg = LinearRegression().fit(annees, df_juil[v].values)
        modeles_reg[v] = reg
        slope = reg.coef_[0]
        log.info("Tendance %s : %+.3f par an", v, slope)

    # Projection
    futures = list(range(df_juil["annee"].max() + 1, horizon + 1))
    rows = []
    for annee in futures:
        row = {"annee": annee, "mois": "Juillet"}
        for v in variables:
            row[v] = float(modeles_reg[v].predict([[annee]])[0])
        rows.append(row)

    df_proj = pd.DataFrame(rows)

    # Prédire le risque pour chaque année projetée
    results = predict_batch(df_proj)

    # Exporter
    out_path = OUT_DIR / "projections_climatiques.csv"
    results.to_csv(out_path, index=False)

    print("\n── PROJECTION CLIMATIQUE JUILLET (tendances 2017-2025) ──")
    for _, r in results.iterrows():
        print(f"  {int(r['annee'])}  T={r['temperature']:.1f}°C  "
              f"H={r['humidite']:.1f}%  → {r['risque_predit']}  "
              f"({r['confiance']:.0%})")

    log.info("Projections climatiques → %s", out_path)
    return results


if __name__ == "__main__":
    project_climate()
