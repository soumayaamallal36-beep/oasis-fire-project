"""
src/prediction/scenario_runner.py
-----------------------------------
Étape 4 du pipeline ML. ← IDÉE AJOUTÉE

Responsabilité :
  • Définir les scénarios futurs (2026, changement climatique)
  • Lancer les prédictions en batch via model_inference
  • Afficher + exporter les résultats dans models/metadata/

Scénarios couverts
──────────────────
  Normaux     → conditions moyennes de chaque mois estival 2026
  Extrêmes    → canicule, sécheresse sévère
  CC (+2°C)   → projection changement climatique +2°C sur 2025
  Mitigés     → après pluies significatives, vent faible

Usage :
    python -m src.prediction.scenario_runner
"""

from pathlib import Path

import pandas as pd

from src.prediction.model_inference import predict_batch
from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "models" / "metadata"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ICONES = {
    "Faible":      "🟢",
    "Moyen":       "🟡",
    "Élevé":       "🟠",
    "Très élevé":  "🔴",
}


def build_scenarios() -> pd.DataFrame:
    """Retourne le DataFrame des scénarios à évaluer."""
    return pd.DataFrame([
        # ── Scénarios normaux ──────────────────────────────
        {"categorie": "Normal",
         "scenario": "Juin 2026 (conditions moyennes)",
         "mois": "Juin",    "temperature": 29.5,  "humidite": 19.5, "precipitation": 2.5,  "vent": 4.5},
        {"categorie": "Normal",
         "scenario": "Juillet 2026 (conditions moyennes)",
         "mois": "Juillet", "temperature": 32.8,  "humidite": 16.5, "precipitation": 10.0, "vent": 4.0},
        {"categorie": "Normal",
         "scenario": "Août 2026 (conditions moyennes)",
         "mois": "Aout",    "temperature": 31.5,  "humidite": 20.0, "precipitation": 0.5,  "vent": 3.8},

        # ── Scénarios extrêmes ─────────────────────────────
        {"categorie": "Extrême",
         "scenario": "Canicule juillet 2026 (T>34°C)",
         "mois": "Juillet", "temperature": 34.5,  "humidite": 13.0, "precipitation": 2.0,  "vent": 4.8},
        {"categorie": "Extrême",
         "scenario": "Sécheresse août 2026 (Prec<1mm)",
         "mois": "Aout",    "temperature": 33.0,  "humidite": 16.0, "precipitation": 0.05, "vent": 3.5},
        {"categorie": "Extrême",
         "scenario": "Tempête de vent juin 2026 (V>6m/s)",
         "mois": "Juin",    "temperature": 30.0,  "humidite": 18.0, "precipitation": 1.0,  "vent": 6.2},

        # ── Changement climatique ─────────────────────────
        {"categorie": "CC +2°C",
         "scenario": "Juillet 2026 + réchauffement +2°C",
         "mois": "Juillet", "temperature": 34.69, "humidite": 13.0, "precipitation": 1.0,  "vent": 4.5},
        {"categorie": "CC +2°C",
         "scenario": "Août 2026 + réchauffement +2°C",
         "mois": "Aout",    "temperature": 33.4,  "humidite": 17.0, "precipitation": 0.1,  "vent": 3.8},

        # ── Scénarios atténués ─────────────────────────────
        {"categorie": "Atténué",
         "scenario": "Après pluies intenses (P>40mm)",
         "mois": "Juillet", "temperature": 28.0,  "humidite": 35.0, "precipitation": 45.0, "vent": 3.0},
        {"categorie": "Atténué",
         "scenario": "Vent faible + humidité élevée",
         "mois": "Juin",    "temperature": 27.0,  "humidite": 38.0, "precipitation": 30.0, "vent": 2.0},
    ])


# ─────────────────────────────────────────────────────────────
def run_scenarios() -> pd.DataFrame:
    """Lance les prédictions et retourne le DataFrame complet."""
    log.info("Lancement des scénarios 2026...")

    scenarios = build_scenarios()
    results   = predict_batch(scenarios)

    # ── Affichage console ────────────────────────────────────
    print("\n" + "=" * 70)
    print("  🔮 PRÉDICTIONS RISQUE INCENDIE — SCÉNARIOS 2026")
    print("=" * 70)

    for cat, grp in results.groupby("categorie"):
        print(f"\n  ── {cat} ──")
        for _, r in grp.iterrows():
            ic = ICONES.get(r["risque_predit"], "⚪")
            print(f"  {ic}  {r['scenario']}")
            print(f"     T={r['temperature']}°C | H={r['humidite']}% | "
                  f"P={r['precipitation']}mm | V={r['vent']}m/s")
            print(f"     → Risque : {r['risque_predit']}  "
                  f"(confiance {r['confiance']:.0%})")

    # ── Export CSV ───────────────────────────────────────────
    out_path = OUT_DIR / "predictions_scenarios_2026.csv"
    results.to_csv(out_path, index=False)
    log.info("Résultats exportés → %s", out_path)

    return results


if __name__ == "__main__":
    run_scenarios()
