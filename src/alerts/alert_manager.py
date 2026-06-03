"""
src/alerts/alert_manager.py
─────────────────────────────
Module d'alertes centralisé — Agdez Fire Risk System.

Fonctionnalités :
  - Évaluation des seuils de risque
  - Notification email SMTP
  - Webhook (Slack, Discord, Teams, générique)
  - Journalisation JSON automatique
  - Anti-doublon (cooldown configurable)
  - Console logging
  - Configuration via config.yaml
"""

import json
import logging
import smtplib
import traceback
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.utils.config_loader import CFG

log = logging.getLogger("AlertManager")

ROOT = Path(__file__).resolve().parents[2]
ALERTS_DIR = ROOT / "reports"
ALERTS_DIR.mkdir(exist_ok=True)

RISQUE_EMOJI = {
    "Faible": "\U0001f7e2", "Moyen": "\U0001f7e1",
    "Élevé": "\U0001f7e0", "Très élevé": "\U0001f534",
}
RISQUE_COLOR_HEX = {
    "Faible": "#27ae60", "Moyen": "#e67e22",
    "Élevé": "#e74c3c", "Très élevé": "#8e1a1a",
}
ORDRE_RISQUE = {"Faible": 0, "Moyen": 1, "Élevé": 2, "Très élevé": 3}
NIVEAUX_ALERTE = {"Élevé", "Très élevé"}

COOLDOWN = timedelta(minutes=CFG["alertes"].get("cooldown_minutes", 60))
_last_alert_time = None
_last_alert_key = None


def _niveau_atteint(label: str, seuil: str) -> bool:
    return ORDRE_RISQUE.get(label, 0) >= ORDRE_RISQUE.get(seuil, 0)


def evaluer_et_alerter(
    label: str,
    confiance: float,
    scenario: str = "",
    probas: dict | None = None,
    temperature: float | None = None,
    humidite: float | None = None,
    precipitation: float | None = None,
    vent: float | None = None,
    mois: str = "",
    annee: int = 2026,
) -> dict | None:
    """Évalue le risque et déclenche les notifications si nécessaire."""
    global _last_alert_time, _last_alert_key

    if label not in NIVEAUX_ALERTE:
        log.debug("Risque %s — aucune alerte requise", label)
        return None

    # Cooldown
    now = datetime.now()
    alert_key = f"{label}|{scenario}"
    if _last_alert_time and _last_alert_key == alert_key:
        if now - _last_alert_time < COOLDOWN:
            remaining = COOLDOWN - (now - _last_alert_time)
            log.info("Cooldown actif — alerte ignorée (%s restant)", remaining)
            return None

    priorite = "CRITIQUE" if label == "Très élevé" else "HAUTE"
    message = (
        "DANGER IMMÉDIAT — activation du plan ORSEC forêt"
        if priorite == "CRITIQUE"
        else "VIGILANCE RENFORCÉE — patrouilles et surveillance active"
    )

    alerte = {
        "timestamp": now.isoformat(),
        "zone": CFG["zone"]["nom"],
        "pays": CFG["zone"]["pays"],
        "scenario": scenario,
        "risque": label,
        "confiance": round(confiance, 4),
        "priorite": priorite,
        "message": message,
        "probas": probas or {},
        "temperature": temperature,
        "humidite": humidite,
        "precipitation": precipitation,
        "vent": vent,
        "mois": mois,
        "annee": annee,
    }

    # Console
    print(f"\n{'='*55}")
    print(f"  ALERTE {priorite} — {label}")
    print(f"  Zone     : {CFG['zone']['nom']}, {CFG['zone']['pays']}")
    print(f"  Scénario : {scenario}")
    print(f"  Risque   : {label}  ({confiance:.0%})")
    print(f"  Action   : {message}")
    print(f"{'='*55}\n")

    # JSON
    _sauvegarder_json(alerte)
    _envoyer_email(alerte)
    _envoyer_webhook(alerte)

    _last_alert_time = now
    _last_alert_key = alert_key
    log.warning("ALERTE %s — %s (%s)", priorite, label, scenario)
    return alerte


def _sauvegarder_json(alerte: dict) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ALERTS_DIR / f"alerte_{alerte['priorite'].lower()}_{ts}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(alerte, f, ensure_ascii=False, indent=2)
        log.info("Alerte sauvegardée → %s", path)
    except Exception as e:
        log.error("Erreur sauvegarde JSON: %s", e)


def _envoyer_email(alerte: dict) -> dict:
    cfg_email = CFG["alertes"].get("email", {})
    if not cfg_email.get("actif", False):
        log.debug("Email désactivé dans la configuration")
        return {"status": "desactive"}

    smtp_host = cfg_email.get("smtp_host", "smtp.gmail.com")
    smtp_port = cfg_email.get("smtp_port", 587)
    smtp_user = cfg_email.get("smtp_user", "")
    smtp_password = cfg_email.get("smtp_password", "")
    expediteur = cfg_email.get("expediteur_nom", "Alerte Incendie")
    destinataires = cfg_email.get("destinataires", [])

    if not smtp_user or not smtp_password or not destinataires:
        log.warning("Email config incomplète — envoi ignoré")
        return {"status": "incomplet"}

    risque = alerte["risque"]
    priorite = alerte["priorite"]
    icone = RISQUE_EMOJI.get(risque, "")
    color = RISQUE_COLOR_HEX.get(risque, "#333")
    probas_html = "".join(
        f'<div style="margin:2px 0;">'
        f'<span style="color:{RISQUE_COLOR_HEX.get(k, "#888")};">{k}</span>: '
        f'<span style="float:right;">{v:.0%}</span>'
        f'<div style="background:#333;height:6px;border-radius:3px;margin-top:2px;">'
        f'<div style="background:{RISQUE_COLOR_HEX.get(k, "#888")};width:{v*100}%;height:6px;border-radius:3px;"></div>'
        f'</div></div>'
        for k, v in (alerte.get("probas") or {}).items()
    )

    txt_body = (
        f"{icone} ALERTE INCENDIE — Agdez, Maroc\n"
        f"{'='*40}\n"
        f"Niveau : {risque} ({priorite})\n"
        f"Confiance : {alerte['confiance']:.0%}\n"
        f"Date : {alerte['timestamp']}\n"
        f"Scénario : {alerte['scenario']}\n\n"
        f"Message : {alerte['message']}"
    )

    html_body = f"""<html><body style="font-family:sans-serif;background:#1a1a2e;color:#e2e8f0;padding:20px;">
    <div style="max-width:600px;margin:auto;background:#0d0d1a;border-radius:12px;padding:24px;border-left:6px solid {color};">
    <h1 style="margin:0;color:{color};">{icone} Alerte Incendie</h1>
    <p style="color:#888;">{alerte['timestamp']}</p>
    <hr style="border-color:#333;">
    <p><strong>Zone</strong> : Agdez, Maroc</p>
    <p><strong>Niveau</strong> : <span style="color:{color};font-weight:bold;">{risque}</span>
    <span style="color:#888;">({priorite})</span></p>
    <p><strong>Confiance</strong> : {alerte['confiance']:.0%}</p>
    <p><strong>Scénario</strong> : {alerte['scenario']}</p>
    <hr style="border-color:#333;">
    <p style="font-size:14px;">{alerte['message']}</p>
    {probas_html}
    <hr style="border-color:#333;">
    <p style="font-size:11px;color:#666;">Généré automatiquement par OASIS Fire Alert System</p>
    </div></body></html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{icone} ALERTE {priorite} — Risque Incendie {risque} · Agdez"
        msg["From"] = f"{expediteur} <{smtp_user}>"
        msg["To"] = ", ".join(destinataires)
        msg.attach(MIMEText(txt_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, destinataires, msg.as_string())
        server.quit()
        log.info("Email envoyé à %s", ", ".join(destinataires))
        return {"status": "envoye", "destinataires": destinataires}

    except smtplib.SMTPAuthenticationError:
        log.error("Authentification SMTP échouée")
        return {"status": "erreur", "detail": "Authentification SMTP échouée"}
    except smtplib.SMTPException as e:
        log.error("Erreur SMTP: %s", e)
        return {"status": "erreur", "detail": str(e)}
    except OSError as e:
        log.error("Erreur réseau SMTP: %s", e)
        return {"status": "erreur", "detail": str(e)}
    except Exception as e:
        log.error("Erreur email: %s", traceback.format_exc())
        return {"status": "erreur", "detail": str(e)}


def _envoyer_webhook(alerte: dict) -> dict:
    url = CFG["alertes"].get("webhook_url", "")
    if not url:
        log.debug("Webhook non configuré")
        return {"status": "non_configure"}

    risque = alerte["risque"]
    color = RISQUE_COLOR_HEX.get(risque, "#333")
    emoji = RISQUE_EMOJI.get(risque, "")

    payload = {
        "text": f"{emoji} ALERTE INCENDIE — {risque} ({alerte['priorite']})",
        "attachments": [{
            "color": color,
            "title": f"{emoji} Risque Incendie {risque} — Agdez",
            "fields": [
                {"title": "Niveau", "value": risque, "short": True},
                {"title": "Confiance", "value": f"{alerte['confiance']:.0%}", "short": True},
                {"title": "Message", "value": alerte["message"], "short": False},
            ],
            "footer": "OASIS Fire Alert System",
            "ts": datetime.now().timestamp(),
        }],
    }

    try:
        import requests
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        log.info("Webhook envoyé → %s", url)
        return {"status": "envoye", "url": url}
    except Exception as e:
        log.error("Erreur webhook: %s", e)
        return {"status": "erreur", "detail": str(e)}
