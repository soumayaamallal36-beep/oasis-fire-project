"""
run_prediction_pipeline.py
---------------------------
Point d'entrée unique du module de prédiction.

Exécute les étapes dans l'ordre :
  1. Feature engineering + chargement données
  2. Entraînement & évaluation des modèles
  3. Prédictions sur scénarios 2026
  4. Alertes automatiques (seuils orange/rouge)
  5. Projections climatiques 2026-2035
  6. Génération du rapport final

Usage :
    python run_prediction_pipeline.py
    python run_prediction_pipeline.py --skip-train   # si modèle déjà entraîné
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.prediction.climate_trend import project_climate
from src.prediction.model_training import train
from src.prediction.report_generator import generate_report
from src.utils.logger import get_logger
from src.alerts.email_alert import send_fire_alert
from src.alerts.email_alert import send_fire_alert

# Fake simulation

risk = "Très élevé"

temperature = 45
humidity = 8
wind_speed = 35

if risk in ["Élevé", "Très élevé"]:

    send_fire_alert(
        risk_level=risk,
        temperature=temperature,
        humidity=humidity,
        wind_speed=wind_speed
    )
log = get_logger("pipeline")


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de prédiction risque incendie — Agdez"
    )
    parser.add_argument(
        "--skip-train", action="store_true",
        help="Sauter l'entraînement si le modèle existe déjà"
    )
    args = parser.parse_args()

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  PIPELINE PRÉDICTION — RISQUE INCENDIE       ║")
    log.info("║  Zone : Agdez, Maroc                         ║")
    log.info("╚══════════════════════════════════════════════╝")

    # ÉTAPE 1 & 2 : Entraînement ─────────────────────────────
    model_path = ROOT / "models" / "trained" / "model_risque_incendie.pkl"
    if not args.skip_train or not model_path.exists():
        log.info("ÉTAPE 1-2 : Entraînement des modèles")
        train()
    else:
        log.info("ÉTAPE 1-2 : Modèle existant — entraînement ignoré")

    # ÉTAPE 3-4-5 : Scénarios, alertes, rapport ──────────────
    log.info("ÉTAPE 3-4-5 : Scénarios 2026 + alertes + rapport")
    report_path = generate_report()
    log.info("Rapport → %s", report_path)

    # ÉTAPE 6 : Projections climatiques ──────────────────────
    log.info("ÉTAPE 6 : Projections climatiques 2026-2035")
    project_climate(horizon=2035)

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  PIPELINE TERMINÉ                            ║")
    log.info("╚══════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
