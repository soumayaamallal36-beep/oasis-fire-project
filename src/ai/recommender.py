"""
src/ai/recommender.py
───────────────────────
Génération de recommandations opérationnelles dynamiques
adaptées au niveau de risque et aux conditions réelles.
"""

from src.ai.explanator import SEUILS


def generer_recommandations(risque: str, temperature=None, humidite=None,
                             vent=None, precipitation=None, ndvi=None,
                             indice_secheresse=None) -> str:
    recommandations = []

    if risque == "Faible":
        recommandations = [
            "✅ Surveillance standard — conditions favorables.",
            "📋 Vérification quotidienne des équipements de détection.",
            "🌿 Poursuivre la veille météorologique normale.",
            "📝 Aucune mesure exceptionnelle requise.",
        ]

    elif risque == "Moyen":
        recommandations = [
            "⚠️ Vigilance renforcée recommandée.",
            "🔍 Vérifier les équipements de détection et les réserves d'eau.",
            "📡 Surveiller l'évolution des conditions météo (température, humidité).",
            "👀 Signaler tout comportement suspect ou départ de fumée.",
        ]

    elif risque == "Élevé":
        recommandations = [
            "🟠 **ALERTE RISQUE ÉLEVÉ**",
            "🚁 Activer les patrouilles terrain renforcées.",
            "📡 Surveillance continue des points chauds (FIRMS/Sentinel-2).",
            "🚫 Interdire les brûlages agricoles et les feux de camp.",
            "📢 Diffuser un message d'alerte à la population.",
            "🔧 Vérifier la disponibilité des moyens aériens et terrestres.",
            "📋 Pré-positionner les équipes d'intervention rapide.",
            "📊 Réévaluer le risque toutes les 6 heures.",
        ]
        if temperature is not None and temperature > 35:
            recommandations.insert(2, "🔴 **Température extrême (>35°C)** — risque de départs multiples.")
        if humidite is not None and humidite < 10:
            recommandations.insert(2, "🔴 **Humidité critique (<10%)** — végétation extrêmement inflammable.")
        if vent is not None and vent > 6:
            recommandations.insert(2, "🔴 **Vent fort (>6 m/s)** — propagation rapide en cas de départ.")

    elif risque == "Très élevé":
        recommandations = [
            "🔴 **DANGER CRITIQUE — ACTIVER LE PLAN ORSEC INCENDIE**",
            "🚨 **Déclencher l'alerte générale immédiatement.**",
            "✈️ Mobiliser les moyens aériens (Canadair, hélicoptères).",
            "🚒 Déployer toutes les équipes terrain disponibles.",
            "🚫 **Interdire l'accès aux massifs forestiers et zones à risque.**",
            "🏠 Préparer les plans d'évacuation des zones habitées.",
            "📢 Diffuser un message d'alerte URGENT à la population.",
            "🔴 Établir un périmètre de sécurité autour des zones sensibles.",
            "📡 Activer la surveillance satellite en continu.",
            "⏱️ Réévaluer la situation toutes les 2 heures.",
            "📞 Contacter les autorités provinciales et la protection civile.",
        ]
        if temperature is not None and temperature > 38:
            recommandations.insert(1, "🔥 **Température extrême (>38°C)** situation de canicule + incendie.")
        if vent is not None and vent > 7:
            recommandations.insert(1, "💨 **Vent tempétueux (>7 m/s)** — propagation foudroyante.")
        if ndvi is not None and ndvi < 0.12:
            recommandations.insert(1, "🌿 **Végétation sèche critique (NDVI<0.12)** — combustible abondant.")
        if indice_secheresse is not None and indice_secheresse > 3:
            recommandations.insert(1, "🔥 **Indice de sécheresse extrême** — conditions de combustion maximales.")

    return recommandations
