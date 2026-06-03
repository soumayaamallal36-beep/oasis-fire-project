"""
src/ai/explanator.py
─────────────────────
Analyse intelligente des facteurs de risque.
Explique POURQUOI le risque est faible, moyen, élevé ou très élevé
en langage naturel, basé sur les conditions réelles.
"""

from src.utils.config_loader import CFG

RISQUE_CLASSES = CFG["risque"]["classes"]

SEUILS = {
    "temperature": {"critique": 32, "eleve": 28, "moyen": 24},
    "humidite": {"critique": 15, "eleve": 25, "moyen": 40},
    "vent": {"critique": 6.0, "eleve": 4.5, "moyen": 3.0},
    "precipitation": {"critique": 1.0, "eleve": 5.0, "moyen": 15.0},
    "ndvi_avant": {"critique": 0.12, "eleve": 0.18, "moyen": 0.25},
    "indice_secheresse": {"critique": 2.0, "eleve": 1.2, "moyen": 0.6},
    "indice_propagation": {"critique": 0.7, "eleve": 0.5, "moyen": 0.3},
    "stress_vegetal": {"critique": 3.0, "eleve": 2.5, "moyen": 2.0},
}


def _analyser_facteur(nom, valeur, facteurs_aggravants, facteurs_favorables):
    if valeur is None:
        return
    seuils = SEUILS.get(nom)
    if not seuils:
        return
    if valeur >= seuils["critique"]:
        facteurs_aggravants.append((nom, valeur, "CRITIQUE"))
    elif valeur >= seuils["eleve"]:
        facteurs_aggravants.append((nom, valeur, "ÉLEVÉ"))
    elif valeur >= seuils["moyen"]:
        pass
    else:
        facteurs_favorables.append((nom, valeur, "FAVORABLE"))


def analyser_risque(temperature, humidite, precipitation, vent,
                    ndvi=0.144, risque_predit="",
                    indice_secheresse=None, indice_propagation=None,
                    stress_vegetal=None) -> dict:
    facteurs_aggravants = []
    facteurs_favorables = []

    if indice_secheresse is None:
        indice_secheresse = (temperature - humidite) / (precipitation + 0.1)
    if indice_propagation is None:
        import numpy as np
        indice_propagation = vent * np.sin(np.radians(CFG["zone"]["pente_moy_deg"]))
    if stress_vegetal is None:
        stress_vegetal = (1 - ndvi) * temperature / 10

    _analyser_facteur("temperature", temperature, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("humidite", humidite, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("vent", vent, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("precipitation", precipitation, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("ndvi_avant", ndvi, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("indice_secheresse", indice_secheresse, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("indice_propagation", indice_propagation, facteurs_aggravants, facteurs_favorables)
    _analyser_facteur("stress_vegetal", stress_vegetal, facteurs_aggravants, facteurs_favorables)

    return {
        "risque": risque_predit,
        "facteurs_aggravants": facteurs_aggravants,
        "facteurs_favorables": facteurs_favorables,
        "nb_critiques": sum(1 for _, _, s in facteurs_aggravants if s == "CRITIQUE"),
        "nb_eleves": sum(1 for _, _, s in facteurs_aggravants if s == "ÉLEVÉ"),
        "indice_secheresse": round(indice_secheresse, 2),
        "indice_propagation": round(indice_propagation, 3),
        "stress_vegetal": round(stress_vegetal, 2),
    }


NOMS_FACTEURS = {
    "temperature": ("🌡️ Température", "°C", "élevée", "basse"),
    "humidite": ("💧 Humidité", "%", "basse", "normale"),
    "vent": ("💨 Vent", "m/s", "élevé", "faible"),
    "precipitation": ("🌧️ Précipitations", "mm", "insuffisantes", "suffisantes"),
    "ndvi_avant": ("🌿 Végétation (NDVI)", "", "sèche", "verte"),
    "indice_secheresse": ("🔥 Indice sécheresse", "", "critique", "normal"),
    "indice_propagation": ("📐 Propagation", "", "favorable", "limitée"),
    "stress_vegetal": ("🌱 Stress hydrique", "", "élevé", "faible"),
}


def generer_explication(analyse: dict) -> str:
    risque = analyse["risque"]
    aggravants = analyse["facteurs_aggravants"]
    favorables = analyse["facteurs_favorables"]

    if not aggravants:
        return "✅ **Aucun facteur de risque critique détecté.** Les conditions actuelles sont favorables."

    lignes = []

    if risque in ("Très élevé", "Élevé"):
        lignes.append(f"**Facteurs critiques ({len(aggravants)}) :**")
        for nom, val, sev in aggravants[:5]:
            info = NOMS_FACTEURS.get(nom, (nom, "", "", ""))
            label = info[0]
            unite = info[1]
            if nom == "humidite":
                desc = f"{val}{unite} — humidité très basse, végétation inflammable"
            elif nom == "temperature":
                desc = f"{val}{unite} — chaleur extrême assèche les sols"
            elif nom == "vent":
                desc = f"{val}{unite} — accélère la propagation"
            elif nom == "precipitation":
                desc = f"{val}{unite} — sol sec, pas d'effet protecteur"
            elif nom == "ndvi_avant":
                desc = f"{val} — végétation sèche, combustible disponible"
            elif nom == "indice_secheresse":
                desc = f"{val} — combinaison chaleur + sécheresse critique"
            elif nom == "indice_propagation":
                desc = f"{val} — vent + pente favorisent la propagation"
            elif nom == "stress_vegetal":
                desc = f"{val} — végétation en stress hydrique sévère"
            else:
                desc = f"{val}{unite}"
            ic = "🔴" if sev == "CRITIQUE" else "🟠"
            lignes.append(f"  {ic} **{label}** : {desc}")

    elif risque == "Moyen":
        lignes.append(f"**Facteurs modérés ({len(aggravants)}) :**")
        for nom, val, sev in aggravants[:3]:
            info = NOMS_FACTEURS.get(nom, (nom, "", "", ""))
            label = info[0]
            unite = info[1]
            lignes.append(f"  🟡 **{label}** : {val}{unite}")

    if favorables:
        lignes.append(f"\n✅ **Facteurs favorables ({len(favorables)}) :**")
        for nom, val, _ in favorables[:3]:
            info = NOMS_FACTEURS.get(nom, (nom, "", "", ""))
            lignes.append(f"  ✅ {info[0]} : {val}{info[1]}")

    nb_critiques = analyse["nb_critiques"]
    if nb_critiques >= 3:
        lignes.append(f"\n⚠️ **{nb_critiques} facteurs critiques simultanés** — situation très dangereuse.")
    elif nb_critiques >= 1:
        lignes.append(f"\n⚠️ **{nb_critiques} facteur(s) critique(s)** — vigilance requise.")

    return "\n".join(lignes)
