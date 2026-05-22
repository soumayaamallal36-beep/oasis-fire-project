"""
src/prediction/risk_alert.py
------------------------------
Étape 5 du pipeline ML. ← IDÉE AJOUTÉE

Responsabilité :
  • Évaluer si un niveau de risque prédit dépasse un seuil critique
  • Générer un message d'alerte structuré (console + JSON + webhook)
  • Loguer chaque alerte déclenchée avec horodatage

Ce module simule un système d'alerte précoce (Early Warning System).
En production, il s'interfacerait avec :
  - des notifications email / SMS (smtplib, twilio)
  - un webhook Slack / Teams
  - une API REST de la protection civile

Usage :
    from src.prediction.risk_alert import evaluate_and_alert
    evaluate_and_alert(label="Très élevé", confiance=0.99,
                       scenario="Juillet 2026 canicule")
"""

import json
from datetime import datetime
from pathlib import Path

from src.utils.config_loader import CFG
from src.utils.logger import get_logger

log = get_logger(__name__)

ROOT       = Path(__file__).resolve().parents[2]
ALERTS_DIR = ROOT / "reports"
ALERTS_DIR.mkdir(exist_ok=True)

SEUILS         = CFG["risque"]["seuils_alerte"]
NIVEAU_ORANGE  = SEUILS["orange"]   # "Élevé"
NIVEAU_ROUGE   = SEUILS["rouge"]    # "Très élevé"

ORDRE_RISQUE = {
    "Faible": 0, "Moyen": 1, "Élevé": 2, "Très élevé": 3
}


def _niveau_atteint(label: str, seuil: str) -> bool:
    return ORDRE_RISQUE.get(label, 0) >= ORDRE_RISQUE.get(seuil, 0)


def evaluate_and_alert(
    label: str,
    confiance: float,
    scenario: str = "",
    probas: dict | None = None,
) -> dict | None:
    """
    Évalue le niveau de risque et déclenche une alerte si nécessaire.

    Paramètres
    ----------
    label      : risque prédit ("Faible", "Moyen", "Élevé", "Très élevé")
    confiance  : probabilité du label prédit [0, 1]
    scenario   : description libre du scénario
    probas     : dict complet des probabilités par classe

    Retour
    ------
    dict d'alerte si seuil dépassé, None sinon
    """
    if _niveau_atteint(label, NIVEAU_ROUGE):
        couleur  = "🔴 ROUGE"
        message  = "DANGER IMMÉDIAT — activation du plan ORSEC forêt"
        priorite = "CRITIQUE"
    elif _niveau_atteint(label, NIVEAU_ORANGE):
        couleur  = "🟠 ORANGE"
        message  = "VIGILANCE RENFORCÉE — patrouilles et surveillance active"
        priorite = "HAUTE"
    else:
        log.debug("Risque %s — aucune alerte requise", label)
        return None

    alerte = {
        "timestamp":  datetime.now().isoformat(),
        "zone":       CFG["zone"]["nom"],
        "pays":       CFG["zone"]["pays"],
        "scenario":   scenario,
        "risque":     label,
        "confiance":  round(confiance, 4),
        "priorite":   priorite,
        "message":    message,
        "probas":     probas or {},
    }

    # ── Log console ──────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  ALERTE {couleur}")
    print(f"  Zone     : {CFG['zone']['nom']}, {CFG['zone']['pays']}")
    print(f"  Scénario : {scenario}")
    print(f"  Risque   : {label}  ({confiance:.0%} de confiance)")
    print(f"  Action   : {message}")
    print(f"{'='*55}\n")

    # ── Sauvegarde fichier JSON ───────────────────────────────
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ALERTS_DIR / f"alerte_{priorite.lower()}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerte, f, ensure_ascii=False, indent=2)
    log.warning("ALERTE %s générée → %s", priorite, path)

    # ── Webhook (simulé) ─────────────────────────────────────
    _send_webhook(alerte)

    return alerte


def _send_webhook(payload: dict) -> None:
    """
    Envoie l'alerte à un webhook externe (Slack, Teams, API REST…).
    En développement : log seulement.
    En production : remplacer par requests.post(url, json=payload).
    """
    url = CFG["alertes"].get("webhook_url", "")
    if url:
        log.info("Webhook → %s", url)
        # import requests
        # requests.post(url, json=payload, timeout=5)
    else:
        log.debug("Webhook non configuré — alerte logguée localement")
