"""
src/ops/stats.py
──────────────────
Statistiques opérationnelles en temps réel :
  - alertes aujourd'hui / semaine / mois
  - dernière alerte
  - temps écoulé depuis dernière alerte
  - répartition des niveaux de risque
  - tendances temporelles
"""

import glob
import json
import os
from datetime import datetime, timedelta

ALERTES_DIR = "reports"


def _charger_alertes():
    pattern = os.path.join(ALERTES_DIR, "alerte_*.json")
    fichiers = sorted(glob.glob(pattern), reverse=True)
    alertes = []
    for f in fichiers:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                data["_fichier"] = f
                alertes.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return alertes


def kpi_alertes():
    alertes = _charger_alertes()
    maintenant = datetime.now()

    aujourd_hui = maintenant.date()
    debut_semaine = maintenant - timedelta(days=maintenant.weekday())

    count_aujourdhui = 0
    count_semaine = 0
    count_mois = 0
    derniere_alerte = None
    temps_ecoule = None

    for a in alertes:
        ts = a.get("timestamp", a.get("date", ""))
        try:
            dt = datetime.fromisoformat(ts) if "T" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            continue

        if dt.date() == aujourd_hui:
            count_aujourdhui += 1
        if dt >= debut_semaine:
            count_semaine += 1
        if dt.month == maintenant.month and dt.year == maintenant.year:
            count_mois += 1

    if alertes:
        ts = alertes[0].get("timestamp", alertes[0].get("date", ""))
        try:
            derniere_alerte = datetime.fromisoformat(ts) if "T" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            temps_ecoule = maintenant - derniere_alerte
        except (ValueError, TypeError):
            pass

    return {
        "aujourdhui": count_aujourdhui,
        "semaine": count_semaine,
        "mois": count_mois,
        "total": len(alertes),
        "derniere_alerte": derniere_alerte,
        "temps_ecoule": temps_ecoule,
        "temps_ecoule_str": str(temps_ecoule).split(".")[0] if temps_ecoule else "N/A",
    }


def repartition_niveaux():
    alertes = _charger_alertes()
    niveaux = {"Faible": 0, "Moyen": 0, "Élevé": 0, "Très élevé": 0}
    for a in alertes:
        risque = a.get("risque", a.get("niveau", "")).lower()
        if risque in ("très élevé", "tres eleve", "critique"):
            niveaux["Très élevé"] += 1
        elif risque == "élevé":
            niveaux["Élevé"] += 1
        elif risque == "moyen":
            niveaux["Moyen"] += 1
        else:
            niveaux["Faible"] += 1
    return {k: v for k, v in niveaux.items() if v > 0 or k == "Faible"}
