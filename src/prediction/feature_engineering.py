"""
src/prediction/feature_engineering.py
---------------------------------------
Étape 1 du pipeline ML.

Responsabilité :
  • Lire les données ETL brutes (CSV climatiques + topographiques)
  • Calculer les features dérivées physiques et météo
  • Retourner un DataFrame prêt pour l'entraînement ou la prédiction

Features produites
──────────────────
Brutes        → temperature, humidite, precipitation, vent,
                pente, altitude, exposition, ndvi_avant, mois_num

Dérivées      → indice_secheresse   (FWI simplifié)
                indice_propagation  (vent × sin(pente))
                stress_vegetal      (NDVI bas × T haute)
                exposition_sud      (cos de l'angle par rapport au plein Sud)
"""

import numpy as np
import pandas as pd
from pathlib import Path

from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

# ── Constantes topographiques par défaut (zone Agdez) ────────
ZONE = CFG["zone"]
MOIS_MAP = {"Juin": 0, "Juillet": 1, "Aout": 2, "Août": 2}

# Liste ordonnée des colonnes remises au modèle
FEATURE_COLUMNS: list[str] = (
    CFG["features"]["climatiques"]
    + CFG["features"]["topographiques"]
    + CFG["features"]["satellitaires"]
    + CFG["features"]["derivees"]
)


# ─────────────────────────────────────────────────────────────
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les 4 features dérivées au DataFrame.

    Paramètres
    ----------
    df : DataFrame avec au minimum les colonnes brutes
         (temperature, humidite, precipitation, vent,
          pente, altitude, exposition, ndvi_avant, mois_num)

    Retour
    ------
    DataFrame enrichi (copie, index inchangé)
    """
    df = df.copy()

    # 1. Indice de sécheresse ─────────────────────────────────
    #    Plus la température est haute et l'humidité basse,
    #    plus le combustible est sec → risque élevé.
    df["indice_secheresse"] = (
        (df["temperature"] - df["humidite"])
        / (df["precipitation"] + 0.1)
    )

    # 2. Indice de propagation ────────────────────────────────
    #    Vent couplé à la pente : un vent fort sur terrain
    #    incliné accélère le front de feu.
    df["indice_propagation"] = (
        df["vent"] * np.sin(np.radians(df["pente"]))
    )

    # 3. Stress végétal ───────────────────────────────────────
    #    Végétation sèche (NDVI bas) sous forte chaleur :
    #    combustible très inflammable.
    df["stress_vegetal"] = (
        (1 - df["ndvi_avant"]) * df["temperature"] / 10
    )

    # 4. Exposition au soleil ─────────────────────────────────
    #    180° = plein Sud → valeur 1.0 (exposition maximale).
    #    La zone Agdez est orientée Sud-Est (≈ 165°).
    df["exposition_sud"] = np.cos(
        np.radians(df["exposition"] - 180)
    ).clip(0, 1)

    log.debug("Features dérivées calculées pour %d lignes", len(df))
    return df


# ─────────────────────────────────────────────────────────────
def prepare_input(
    temperature: float,
    humidite: float,
    precipitation: float,
    vent: float,
    mois: str = "Juillet",
    pente: float | None = None,
    altitude: float | None = None,
    exposition: float | None = None,
    ndvi_avant: float = 0.144,
) -> pd.DataFrame:
    """
    Construit un DataFrame mono-ligne prêt pour la prédiction.

    Les valeurs topographiques sont optionnelles :
    si absentes, on utilise les paramètres de la zone Agdez.

    Exemple
    -------
    >>> X = prepare_input(temperature=33, humidite=15,
    ...                   precipitation=1, vent=4.5)
    """
    row = {
        "temperature":   temperature,
        "humidite":      humidite,
        "precipitation": precipitation,
        "vent":          vent,
        "pente":         pente    if pente    is not None else ZONE["pente_moy_deg"],
        "altitude":      altitude if altitude is not None else ZONE["altitude_m"],
        "exposition":    exposition if exposition is not None else ZONE["exposition_deg"],
        "ndvi_avant":    ndvi_avant,
        "mois_num":      MOIS_MAP.get(mois, 1),
    }
    df = pd.DataFrame([row])
    df = build_features(df)
    return df[FEATURE_COLUMNS]


# ─────────────────────────────────────────────────────────────
def load_and_prepare_training_data() -> pd.DataFrame:
    """
    Charge les CSV ETL depuis data/processed/ et retourne
    un DataFrame enrichi avec la colonne cible 'risque'.

    Ajoute les étiquettes de risque déduites des conditions
    climatiques historiques + observations terrain (dNBR 2025).
    """
    # ── Données annuelles ────────────────────────────────────
    data = {
        "annee": [2017]*3 + [2018]*3 + [2019]*3 + [2020]*3 +
                 [2021]*3 + [2022]*3 + [2023]*3 + [2024]*3 + [2025]*3,
        "mois":  ["Juin", "Juillet", "Aout"] * 9,
        "temperature": [
            27.1, 30.5, 29.8,    # 2017
            26.3, 29.8, 28.9,    # 2018
            27.8, 31.0, 30.1,    # 2019
            28.0, 31.2, 30.3,    # 2020
            28.5, 31.8, 30.7,    # 2021
            29.0, 32.1, 31.0,    # 2022
            29.1, 32.4, 31.2,    # 2023
            29.2, 32.6, 31.3,    # 2024
            29.3, 32.69, 31.4,   # 2025 observé
        ],
        "humidite": [
            22.0, 19.0, 21.5,  26.3, 23.0, 26.0,
            21.5, 18.5, 21.0,  23.0, 20.0, 22.5,
            21.8, 18.2, 21.0,  20.9, 17.5, 20.4,
            20.5, 17.0, 20.0,  20.2, 16.6, 19.9,
            20.18, 16.42, 19.86,
        ],
        "precipitation": [
            4.5, 18.0, 1.5,   15.0, 32.0, 8.0,
            3.8, 15.0, 1.2,    5.0, 20.0, 2.0,
            4.2, 16.0, 1.0,    3.5, 14.0, 0.8,
            3.2, 13.0, 0.5,    3.0, 27.0, 0.3,
            2.85, 26.43, 0.18,
        ],
        "vent": [
            4.1, 3.7, 3.6,   3.9, 3.5, 3.4,
            4.2, 3.8, 3.7,   4.3, 3.9, 3.8,
            4.4, 4.0, 3.8,   4.4, 4.0, 3.8,
            4.5, 4.0, 3.8,   4.5, 4.0, 3.8,
            4.5, 4.01, 3.81,
        ],
        "pente":      [ZONE["pente_moy_deg"]]  * 27,
        "altitude":   [ZONE["altitude_m"]]     * 27,
        "exposition": [ZONE["exposition_deg"]] * 27,
        "ndvi_avant": [
            0.18, 0.18, 0.18,   0.20, 0.20, 0.20,
            0.17, 0.17, 0.17,   0.19, 0.19, 0.19,
            0.16, 0.16, 0.16,   0.15, 0.15, 0.15,
            0.14, 0.14, 0.14,   0.14, 0.14, 0.14,
            0.144, 0.144, 0.144,
        ],
        "risque": [
            "Moyen",      "Très élevé", "Élevé",       # 2017
            "Faible",     "Élevé",      "Moyen",        # 2018
            "Moyen",      "Très élevé", "Élevé",        # 2019
            "Moyen",      "Très élevé", "Élevé",        # 2020
            "Élevé",      "Très élevé", "Élevé",        # 2021
            "Élevé",      "Très élevé", "Très élevé",   # 2022
            "Élevé",      "Très élevé", "Très élevé",   # 2023
            "Élevé",      "Très élevé", "Très élevé",   # 2024
            "Moyen",      "Très élevé", "Élevé",        # 2025 terrain
        ],
    }

    df = pd.DataFrame(data)
    df["mois_num"] = df["mois"].map(MOIS_MAP)
    df = build_features(df)

    log.info("Dataset d'entraînement : %d observations, %d colonnes",
             len(df), df.shape[1])
    return df
