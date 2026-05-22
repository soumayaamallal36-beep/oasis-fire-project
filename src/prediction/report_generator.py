"""
src/prediction/report_generator.py
-----------------------------------
Étape 6 du pipeline ML.

Responsabilité :
  • Générer un rapport texte récapitulatif (rapport_prediction.txt)
  • Générer un fichier JSON de synthèse (synthese_risque.json)
  • Intégrer les résultats des scénarios, des projections climatiques
    et des alertes déclenchées.

Usage :
    from src.prediction.report_generator import generate_report
    report_path = generate_report()
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MODELS_METADATA = ROOT / "models" / "metadata"
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
def generate_report() -> Path:
    """
    Génère les rapports texte et JSON à partir des résultats existants
    (scénarios, projections climatiques, alertes).

    Returns
    -------
    Path vers le fichier rapport texte principal.
    """
    log.info("Génération du rapport final...")

    # 1. Charger les prédictions des scénarios 2026 (si disponibles)
    scenarios_path = MODELS_METADATA / "predictions_scenarios_2026.csv"
    scenarios_df = None
    if scenarios_path.exists():
        scenarios_df = pd.read_csv(scenarios_path)
        log.info("Scénarios 2026 chargés : %d lignes", len(scenarios_df))
    else:
        log.warning("Fichier des scénarios introuvable : %s", scenarios_path)

    # 2. Charger les projections climatiques 2026-2035
    climate_path = MODELS_METADATA / "projections_climatiques.csv"
    climate_df = None
    if climate_path.exists():
        climate_df = pd.read_csv(climate_path)
        log.info("Projections climatiques chargées : %d années", len(climate_df))
    else:
        log.warning("Projections climatiques introuvables : %s", climate_path)

    # 3. Lister les alertes générées (fichiers JSON dans reports/)
    alert_files = sorted(REPORTS_DIR.glob("alerte_*.json"))
    alerts = []
    for fpath in alert_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                alerts.append(json.load(f))
        except Exception:
            log.exception("Erreur lecture alerte %s", fpath)
    log.info("Alertes chargées : %d", len(alerts))

    # 4. Génération du rapport texte
    txt_path = REPORTS_DIR / "rapport_prediction.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("RAPPORT PRÉDICTION RISQUE INCENDIE — AGDEZ\n")
        f.write(f"Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. ZONE D'ÉTUDE\n")
        f.write(f"   Nom      : {CFG['zone']['nom']}\n")
        f.write(f"   Pays     : {CFG['zone']['pays']}\n")
        f.write(f"   Coordonnées : {CFG['zone']['latitude']}, {CFG['zone']['longitude']}\n")
        f.write(f"   Altitude : {CFG['zone']['altitude_m']} m\n")
        f.write(f"   Pente    : {CFG['zone']['pente_moy_deg']}°\n\n")

        f.write("2. MODÈLE UTILISÉ\n")
        model_info_path = MODELS_METADATA / "model_info.json"
        if model_info_path.exists():
            with open(model_info_path, "r", encoding="utf-8") as mf:
                model_info = json.load(mf)
            f.write(f"   Meilleur algorithme : {model_info.get('modele', 'Inconnu')}\n")
            f.write(f"   Précision CV (5 folds) : {model_info.get('accuracy_cv', 0.0):.3f}\n")
            f.write(f"   Features utilisées : {len(model_info.get('features', []))}\n\n")
        else:
            f.write("   (Informations modèle non disponibles)\n\n")

        f.write("3. SCÉNARIOS 2026\n")
        if scenarios_df is not None:
            f.write("   Résultats par catégorie :\n")
            for cat in scenarios_df["categorie"].unique():
                sub = scenarios_df[scenarios_df["categorie"] == cat]
                f.write(f"   • {cat} : {len(sub)} scénario(s)\n")
                # Compter les risques élevés/très élevés
                eleves = sub[sub["risque_predit"].isin(["Élevé", "Très élevé"])]
                f.write(f"     → {len(eleves)} scénario(s) avec risque Élevé ou Très élevé\n")
            f.write("\n   Détail complet dans models/metadata/predictions_scenarios_2026.csv\n\n")
        else:
            f.write("   Aucune donnée de scénario disponible.\n\n")

        f.write("4. PROJECTIONS CLIMATIQUES (2026-2035)\n")
        if climate_df is not None:
            f.write("   Tendances linéaires estimées sur la base des années 2017-2025.\n")
            eleves_clim = climate_df[climate_df["risque_predit"].isin(["Élevé", "Très élevé"])]
            f.write(f"   Années avec risque Élevé ou Très élevé : {len(eleves_clim)} sur {len(climate_df)}\n")
            if len(eleves_clim) > 0:
                f.write("   Années critiques : " + ", ".join(map(str, eleves_clim["annee"].astype(int).tolist())) + "\n")
            f.write("\n   Fichier complet : models/metadata/projections_climatiques.csv\n\n")
        else:
            f.write("   Projections non disponibles.\n\n")

        f.write("5. ALERTES DÉCLENCHÉES\n")
        if alerts:
            for a in alerts:
                f.write(f"   • {a.get('timestamp', '')[:16]} : {a.get('risque', '?')} ({a.get('priorite', '?')}) - {a.get('scenario', '')}\n")
        else:
            f.write("   Aucune alerte enregistrée.\n")
        f.write("\n")

        f.write("6. RECOMMANDATIONS\n")
        if alerts:
            max_prio = max(alerts, key=lambda x: 2 if x.get('priorite')=='CRITIQUE' else 1)
            if max_prio.get('priorite') == 'CRITIQUE':
                f.write("   ⚠️  Risque TRÈS ÉLEVÉ détecté dans certains scénarios.\n")
                f.write("      → Activer immédiatement les mesures de surveillance renforcée.\n")
            else:
                f.write("   ⚠️  Risque ÉLEVÉ détecté. Maintenir une vigilance active.\n")
        else:
            f.write("   📊 Aucune alerte requise dans les projections actuelles.\n")
        f.write("      → Continuer la collecte de données pour affiner les modèles.\n")

    # 5. Génération du JSON de synthèse
    json_path = REPORTS_DIR / "synthese_risque.json"
    synthesis = {
        "date_generation": datetime.now().isoformat(),
        "zone": CFG["zone"],
        "scenarios_2026": {
            "fichier": str(scenarios_path) if scenarios_path.exists() else None,
            "nb_scenarios": len(scenarios_df) if scenarios_df is not None else 0,
            "nb_alertes_eleve": int(len(scenarios_df[scenarios_df["risque_predit"].isin(["Élevé", "Très élevé"])])) if scenarios_df is not None else 0,
        },
        "projections_climatiques": {
            "fichier": str(climate_path) if climate_path.exists() else None,
            "nb_annees": len(climate_df) if climate_df is not None else 0,
            "annees_critiques": [int(a) for a in climate_df[climate_df["risque_predit"].isin(["Élevé", "Très élevé"])]["annee"].tolist()] if climate_df is not None else [],
        },
        "alertes": alerts,
        "recommandations": (
            "Activer les mesures d'urgence pour les scénarios à risque très élevé"
            if any(a.get('priorite')=='CRITIQUE' for a in alerts) else
            "Surveillance renforcée recommandée pour les scénarios à risque élevé"
            if alerts else
            "Risque modéré – suivi standard"
        )
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(synthesis, f, ensure_ascii=False, indent=2)

    log.info("Rapport texte sauvegardé : %s", txt_path)
    log.info("Synthèse JSON sauvegardée : %s", json_path)

    return txt_path


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test simple
    generate_report()