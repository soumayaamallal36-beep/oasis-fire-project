"""
src/ops/timeline.py
────────────────────
Timeline chronologique des alertes déclenchées.
Lecture depuis les fichiers reports/alerte_*.json.
"""

import glob
import json
import os
from datetime import datetime

ALERTES_DIR = "reports"


def charger_timeline(limite=20, ordre="desc") -> list:
    pattern = os.path.join(ALERTES_DIR, "alerte_*.json")
    fichiers = sorted(glob.glob(pattern), reverse=(ordre == "desc"))

    entries = []
    for f in fichiers:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, IOError):
            continue

        ts = data.get("timestamp", data.get("date", ""))
        try:
            dt = datetime.fromisoformat(ts) if "T" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            dt = None

        entries.append({
            "date": dt,
            "date_str": dt.strftime("%d/%m/%Y %H:%M") if dt else ts,
            "risque": data.get("risque", data.get("niveau", "Inconnu")),
            "temperature": data.get("temperature", data.get("conditions_meteo", {}).get("temperature", "N/A")),
            "humidite": data.get("humidite", data.get("conditions_meteo", {}).get("humidite", "N/A")),
            "vent": data.get("vent", data.get("conditions_meteo", {}).get("vent", "N/A")),
            "classe": _classe_alerte(data.get("risque", data.get("niveau", ""))),
        })

        if len(entries) >= limite:
            break

    return entries


COULEURS_ALERTES = {
    "Faible": "🟢",
    "Moyen": "🟡",
    "Élevé": "🟠",
    "Très élevé": "🔴",
    "Critique": "🔴",
}


def _classe_alerte(risque: str) -> str:
    risque_lower = risque.lower()
    if risque_lower in ("très élevé", "tres eleve", "critique"):
        return "danger"
    elif risque_lower == "élevé" or risque_lower == "eleve":
        return "warning"
    elif risque_lower == "moyen":
        return "moderate"
    return "safe"
