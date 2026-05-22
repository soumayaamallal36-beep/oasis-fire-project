"""
FireWatch Agdez - Alertes Email
Envoi d'alertes de risque d'incendie par email SMTP avec template HTML.
"""
import os, logging, smtplib, json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import yaml
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EmailAlert")

RISK_COLORS = {"Faible": "#22c55e", "Moyen": "#f59e0b", "Élevé": "#ef4444", "Très Élevé": "#dc2626"}
RISK_EMOJI = {"Faible": "🟢", "Moyen": "🟡", "Élevé": "🔴", "Très Élevé": "🔴🔴"}

class EmailAlert:
    """Système d'alertes par email avec template HTML et cooldown."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le service d'alerte email."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        ac = self.config["alerts"]["email"]
        self.smtp_server = ac["smtp_server"]
        self.smtp_port = ac["smtp_port"]
        self.sender = os.getenv("EMAIL_SENDER", ac["sender"])
        self.password = os.getenv("EMAIL_PASSWORD", ac["password"])
        self.recipients = ac["recipients"]
        self.cooldown_hours = ac["cooldown_hours"]
        self.cooldown_file = ac["cooldown_file"]
        logger.info("EmailAlert initialisé (SMTP: %s:%d)", self.smtp_server, self.smtp_port)

    def _check_cooldown(self) -> bool:
        """Vérifie si le cooldown est respecté."""
        if not os.path.exists(self.cooldown_file):
            return True
        try:
            with open(self.cooldown_file, "r") as f:
                last = datetime.fromisoformat(json.load(f)["last_sent"])
            return datetime.now() - last > timedelta(hours=self.cooldown_hours)
        except Exception:
            return True

    def _update_cooldown(self) -> None:
        """Met à jour le fichier de cooldown."""
        with open(self.cooldown_file, "w") as f:
            json.dump({"last_sent": datetime.now().isoformat()}, f)

    def _build_html(self, risk_level: str, confidence: float, factors: List[str]) -> str:
        """Construit le template HTML de l'alerte."""
        color = RISK_COLORS.get(risk_level, "#666")
        emoji = RISK_EMOJI.get(risk_level, "⚠️")
        factors_html = "".join(f"<li style='padding:4px 0'>{f}</li>" for f in factors)
        return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#111;color:#eee;padding:20px">
<div style="background:linear-gradient(135deg,{color}33,{color}11);border:1px solid {color};border-radius:12px;padding:24px;margin-bottom:16px">
<h1 style="margin:0;color:{color}">{emoji} Alerte Incendie — {risk_level}</h1>
<p style="margin:8px 0 0;color:#aaa">FireWatch Agdez · {datetime.now().strftime('%d/%m/%Y %H:%M')}</p></div>
<div style="background:#1a1a2e;border-radius:8px;padding:20px;margin-bottom:16px">
<h2 style="color:#fff;margin-top:0">Niveau de risque : <span style="color:{color}">{risk_level}</span></h2>
<p>Confiance du modèle : <strong>{confidence*100:.1f}%</strong></p>
<h3 style="color:#ccc">Facteurs de risque :</h3><ul style="color:#eee">{factors_html}</ul></div>
<div style="text-align:center;padding:16px;color:#666;font-size:12px">
<p>FireWatch Agdez — Système IA v{self.config['api']['model_version']}<br>Drâa-Tafilalet, Maroc</p></div>
</body></html>"""

    def send_risk_alert(self, risk_level: str, confidence: float,
                         factors: List[str], recipient_list: Optional[List[str]] = None,
                         force: bool = False) -> bool:
        """Envoie une alerte de risque par email."""
        if not force and not self._check_cooldown():
            logger.info("Cooldown actif, alerte non envoyée")
            return False
        recipients = recipient_list or self.recipients
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔥 FireWatch Agdez — Risque {risk_level}"
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)
        html = self._build_html(risk_level, confidence, factors)
        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, recipients, msg.as_string())
            self._update_cooldown()
            logger.info("Alerte email envoyée à %s (risque: %s)", recipients, risk_level)
            return True
        except Exception as e:
            logger.error("Échec envoi email: %s", e)
            return False

if __name__ == "__main__":
    alert = EmailAlert()
    print("Test d'alerte email (simulation)...")
    html = alert._build_html("Élevé", 0.87, ["Température 42°C", "Humidité 8%", "FWI 35.2"])
    os.makedirs("reports", exist_ok=True)
    with open("reports/alert_email_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Preview HTML sauvé: reports/alert_email_preview.html")
