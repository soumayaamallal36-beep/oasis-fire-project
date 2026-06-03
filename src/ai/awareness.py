"""
src/ai/awareness.py
────────────────────
Génération automatique de messages de sensibilisation
destinés à la population et aux autorités locales,
adaptés au niveau de risque actuel.
"""


def generer_message_population(risque: str, temperature=None, vent=None) -> str:
    messages = {}

    messages["Faible"] = (
        "🟢 **Risque incendie FAIBLE** sur la commune d'Agdez.\n\n"
        "Les conditions météorologiques sont favorables.\n"
        "✅ Vous pouvez vaquer à vos occupations en toute sérénité.\n"
        "Rappel : respectez toujours les règles de base de prévention.\n\n"
        "---\n"
        "📞 Urgences : 15 (SAMU) / 19 (Protection Civile)"
    )

    messages["Moyen"] = (
        "🟡 **Risque incendie MODÉRÉ** — soyez vigilants.\n\n"
        "⚠️ Évitez les brûlages à l'air libre.\n"
        "⚠️ Ne jetez pas de mégots sur la voie publique ou en pleine nature.\n"
        "⚠️ Surveillez vos feux de camp et éteignez-les complètement.\n"
        "🔍 Signalez tout départ de fumée ou comportement suspect.\n\n"
        "---\n"
        "📞 Signalez au 15/19 — Ne faites rien sans l'accord des autorités."
    )

    messages["Élevé"] = (
        "🟠 **ALERTE RISQUE INCENDIE ÉLEVÉ — Commune d'Agdez**\n\n"
        "🔴 **MESURES OBLIGATOIRES :**\n"
        "• Interdiction TOTALE de tout brûlage à l'air libre\n"
        "• Interdiction des feux de camp et barbecues en extérieur\n"
        "• Ne jetez PAS de mégots (amende et poursuites)\n\n"
        "⚠️ **RECOMMANDATIONS :**\n"
        "• Tenez-vous prêts à évacuer si nécessaire\n"
        "• Rassemblez vos documents importants\n"
        "• Dégagez les abords de votre habitation (végétation sèche)\n"
        "• Prévenez vos voisins et les personnes âgées\n\n"
        "📢 **RASSUREZ-VOUS** : Les équipes de la Protection Civile sont mobilisées.\n"
        f"{'Temperature elevee — restez a l ombre et hydratez-vous.' if temperature and temperature > 35 else ''}"
        "\n---\n"
        "📞 **URGENCES : 15 / 19 / 112** — Signalez immédiatement tout départ de feu."
    )

    messages["Très élevé"] = (
        "🔴 **🚨 ALERTE RISQUE INCENDIE CRITIQUE — DANGER IMMÉDIAT**\n"
        "🔴 **Commune d'Agdez — Message des Autorités**\n\n"
        "🔥 **SITUATION D'URGENCE** 🔥\n\n"
        "🚨 **CONSIGNES OBLIGATOIRES :**\n"
        "1. Évacuez IMMÉDIATEMENT si les autorités vous le demandent\n"
        "2. Suivez UNIQUEMENT les consignes officielles\n"
        "3. N'utilisez PAS les routes non sécurisées\n"
        "4. Protégez votre vie, pas vos biens\n\n"
        "❌ **INTERDICTIONS STRICTES :**\n"
        "• Tout brûlage est FORMELLEMENT INTERDIT\n"
        "• Accès aux forêts et zones boisées INTERDIT\n"
        "• Rassemblements en plein air INTERDITS\n\n"
        "✅ **À FAIRE :**\n"
        "• Restez à l'écoute des autorités (radio, haut-parleurs)\n"
        "• Préparez un sac d'urgence (documents, médicaments, eau)\n"
        "• Protégez les animaux domestiques\n"
        "• N'appelez le 15/19 qu'EN CAS D'URGENCE VITALE\n\n"
        f"{'🔥 Canicule + Incendie = DANGER MORTEL. Restez chez vous.' if temperature and temperature > 38 else ''}"
        f"{'💨 Vent violent détecté — le feu peut se propager très rapidement.' if vent and vent > 7 else ''}"
        "\n---\n"
        "📞 **URGENCES : 15 (SAMU) / 19 (Pompiers) / 112 (UE)**"
    )

    return messages.get(risque, messages["Moyen"])


def generer_message_autorites(risque: str) -> str:
    messages = {
        "Faible": (
            "📋 **BULLETIN DE SÉCURITÉ — Risque Faible**\n"
            "Destinataire : Autorités communales et services de sécurité\n\n"
            "Aucune action urgente requise.\n"
            "• Surveillance de routine maintenue\n"
            "• Vérification périodique des équipements\n"
            "• Veille météorologique standard"
        ),
        "Moyen": (
            "📋 **BULLETIN DE SÉCURITÉ — Risque Modéré**\n"
            "Destinataire : Autorités communales et services de sécurité\n\n"
            "Actions recommandées :\n"
            "• Sensibilisation de la population\n"
            "• Vérification des réserves d'eau et des accès pompiers\n"
            "• Surveillance météo renforcée\n"
            "• Pré-alerte des équipes d'intervention"
        ),
        "Élevé": (
            "📋 **BULLETIN DE SÉCURITÉ — Risque ÉLEVÉ**\n"
            "Destinataire : Autorités communales, Protection Civile, Services techniques\n\n"
            "🔴 **MESURES OBLIGATOIRES :**\n"
            "1. Activer le plan communal de sauvegarde (PCS)\n"
            "2. Mobiliser les équipes d'intervention\n"
            "3. Diffuser l'alerte à la population\n"
            "4. Interdire les brûlages et les accès aux massifs\n"
            "5. Pré-positionner les moyens matériels\n"
            "6. Réquisitionner les points d'eau privés si nécessaire\n\n"
            "Veuillez accuser réception et confirmer les mesures prises."
        ),
        "Très élevé": (
            "📋 **BULLETIN DE SÉCURITÉ — RISQUE CRITIQUE / DANGER IMMÉDIAT**\n"
            "Destinataire : **⚠️ URGENT — Province / Protection Civile / ANEF / Wali**\n\n"
            "🔴 **ACTIVATION DU PLAN ORSEC INCENDIE DE FORÊT**\n\n"
            "1. Déclencher l'alerte générale (sirènes, SMS, médias)\n"
            "2. Mobiliser tous les moyens : pompiers, eaux et forêts, gendarmerie\n"
            "3. Activer les moyens aériens (Canadair, hélicoptères)\n"
            "4. Évacuer les zones à risque\n"
            "5. Fermer les routes forestières et axes secondaires\n"
            "6. Établir un poste de commandement avancé\n"
            "7. Activer les réservistes et la protection civile\n\n"
            "⏱️ **Prochaine évaluation dans 2 heures.**\n"
            "📞 Confirmez immédiatement la réception de ce message."
        ),
    }
    return messages.get(risque, messages["Moyen"])
