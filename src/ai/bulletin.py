"""
src/ai/bulletin.py
────────────────────
Génération automatique d'un bulletin d'analyse complet
après chaque prédiction. Synthèse professionnelle prête
à être affichée, exportée ou imprimée.
"""

from datetime import datetime

from src.ai.explanator import analyser_risque, generer_explication
from src.ai.recommender import generer_recommandations
from src.ai.awareness import generer_message_population, generer_message_autorites


def generer_bulletin(risque: str, confiance: float, temperature: float,
                     humidite: float, precipitation: float, vent: float,
                     ndvi: float = 0.144, mois: str = "",
                     annee: int = 2026, probas: dict = None,
                     indice_secheresse: float = None,
                     indice_propagation: float = None,
                     stress_vegetal: float = None) -> dict:
    if probas is None:
        probas = {}

    analyse = analyser_risque(
        temperature=temperature,
        humidite=humidite,
        precipitation=precipitation,
        vent=vent,
        ndvi=ndvi,
        risque_predit=risque,
        indice_secheresse=indice_secheresse,
        indice_propagation=indice_propagation,
        stress_vegetal=stress_vegetal,
    )

    explication = generer_explication(analyse)
    recommandations = generer_recommandations(
        risque, temperature, humidite, vent, precipitation, ndvi,
        analyse["indice_secheresse"],
    )
    message_population = generer_message_population(risque, temperature, vent)
    message_autorites = generer_message_autorites(risque)

    nb_critiques = analyse["nb_critiques"]
    nb_eleves = analyse["nb_eleves"]
    nb_favorables = len(analyse["facteurs_favorables"])

    if risque in ("Très élevé", "Élevé"):
        tendance = "↗️ **Aggravation possible** — les conditions météo prévues restent défavorables dans les prochaines 48h."
        if nb_critiques >= 3:
            tendance = "🔴 **Situation critique** — multiples facteurs de risque simultanés. Dégradation attendue."
    elif risque == "Moyen":
        tendance = "➡️ **Stable** — surveillance nécessaire. Une hausse de température pourrait faire basculer le risque."
    else:
        tendance = "↘️ **Amélioration ou maintien** — les conditions restent favorables."

    synthese = {
        "resume": _generer_resume(risque, nb_critiques),
        "niveau_de_risque": risque,
        "confiance_modele": f"{confiance:.0%}",
        "date_analyse": datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "periode": f"{mois} {annee}" if mois else str(annee),
        "conditions_meteo": {
            "temperature": f"{temperature}°C",
            "humidite": f"{humidite}%",
            "precipitation": f"{precipitation} mm",
            "vent": f"{vent} m/s",
            "ndvi_vegetation": f"{ndvi}",
            "indice_secheresse": analyse["indice_secheresse"],
            "indice_propagation": analyse["indice_propagation"],
            "stress_vegetal": analyse["stress_vegetal"],
        },
        "probabilites": {k: f"{v:.0%}" for k, v in probas.items()} if probas else {},
        "facteurs_aggravants": analyse["facteurs_aggravants"],
        "facteurs_favorables": analyse["facteurs_favorables"],
        "explication": explication,
        "tendance": tendance,
        "recommandations": recommandations,
        "message_population": message_population,
        "message_autorites": message_autorites,
        "nb_facteurs_critiques": nb_critiques,
        "nb_facteurs_eleves": nb_eleves,
    }

    synthese["bulletin_texte"] = _format_bulletin_texte(synthese)
    return synthese


def _generer_resume(risque: str, nb_critiques: int) -> str:
    resumes = {
        "Très élevé": "🔴 **SITUATION CRITIQUE** — Danger immédiat de départ de feu. "
                      f"({nb_critiques} facteur(s) critique(s) détecté(s)). "
                      "Activation du plan ORSEC requise.",
        "Élevé": "🟠 **RISQUE IMPORTANT** — Conditions favorables au départ et à la propagation "
                 "d'un incendie. Surveillance renforcée obligatoire.",
        "Moyen": "🟡 **RISQUE MODÉRÉ** — Conditions qui nécessitent une vigilance "
                 "accrue. Éviter toute activité à risque.",
        "Faible": "🟢 **RISQUE FAIBLE** — Conditions météorologiques et environnementales "
                  "favorables. Aucune mesure exceptionnelle requise.",
    }
    return resumes.get(risque, "")


def _format_bulletin_texte(s: dict) -> str:
    lignes = []
    lignes.append("=" * 65)
    lignes.append(f"  BULLETIN DE RISQUE INCENDIE — AGDEZ")
    lignes.append(f"  Date : {s['date_analyse']}")
    lignes.append("=" * 65)
    lignes.append("")
    lignes.append(f"📊 NIVEAU DE RISQUE : {s['niveau_de_risque']}")
    lignes.append(f"📈 Confiance du modèle : {s['confiance_modele']}")
    lignes.append(f"📅 Période : {s['periode']}")
    lignes.append("")
    lignes.append(s['resume'])
    lignes.append("")
    lignes.append("── CONDITIONS MÉTÉO ──")
    for k, v in s['conditions_meteo'].items():
        lignes.append(f"  • {k.replace('_', ' ').title()} : {v}")
    lignes.append("")
    if s['probabilites']:
        lignes.append("── PROBABILITÉS MODÈLE ──")
        for k, v in s['probabilites'].items():
            lignes.append(f"  • {k} : {v}")
        lignes.append("")
    lignes.append("── ANALYSE ---")
    lignes.append(s['explication'])
    lignes.append("")
    lignes.append("── TENDANCE ---")
    lignes.append(s['tendance'])
    lignes.append("")
    lignes.append("── RECOMMANDATIONS ---")
    for r in s['recommandations']:
        lignes.append(f"  • {r}")
    lignes.append("")
    lignes.append("── MESSAGE POPULATION ---")
    lignes.append(s['message_population'])
    lignes.append("")
    lignes.append("── MESSAGE AUTORITÉS ---")
    lignes.append(s['message_autorites'])
    lignes.append("")
    lignes.append("=" * 65)
    lignes.append("  Généré automatiquement par OASIS Fire AI")
    lignes.append("  Système de Prédiction et d'Alerte — Agdez, Maroc")
    lignes.append("=" * 65)

    return "\n".join(lignes)
