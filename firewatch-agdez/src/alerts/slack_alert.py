"""
FireWatch Agdez - Alertes Slack
Envoi d'alertes de risque d'incendie via Slack webhook.
"""
import os, logging, json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import requests, yaml
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SlackAlert")

RISK_COLORS = {"Faible": "#22c55e", "Moyen": "#f59e0b", "Élevé": "#ef4444", "Très Élevé": "#dc2626"}
RISK_EMOJI = {"Faible": ":large_green_circle:", "Moyen": ":warning:",
              "Élevé": ":red_circle:", "Très Élevé": ":fire:"}

class SlackAlert:
    """Système d'alertes Slack via webhook avec cooldown."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le service d'alerte Slack."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        sc = self.config["alerts"]["slack"]
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", sc["webhook_url"])
        self.channel = sc["channel"]
        self.cooldown_hours = sc["cooldown_hours"]
        self.cooldown_file = sc["cooldown_file"]
        logger.info("SlackAlert initialisé (channel: %s)", self.channel)

    def _check_cooldown(self) -> bool:
        """Vérifie le respect du cooldown."""
        if not os.path.exists(self.cooldown_file):
            return True
        try:
            with open(self.cooldown_file, "r") as f:
                last = datetime.fromisoformat(json.load(f)["last_sent"])
            return datetime.now() - last > timedelta(hours=self.cooldown_hours)
        except Exception:
            return True

    def _update_cooldown(self) -> None:
        with open(self.cooldown_file, "w") as f:
            json.dump({"last_sent": datetime.now().isoformat()}, f)

    def _build_blocks(self, risk_level: str, confidence: float, factors: List[str]) -> List[Dict[str, Any]]:
        """Construit les blocs Slack pour l'alerte."""
        emoji = RISK_EMOJI.get(risk_level, ":warning:")
        factors_text = "\n".join(f"• {f}" for f in factors)
        return [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"{emoji} Alerte FireWatch Agdez — Risque {risk_level}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Niveau :* {risk_level}"},
                {"type": "mrkdwn", "text": f"*Confiance :* {confidence*100:.1f}%"},
                {"type": "mrkdwn", "text": f"*Région :* Drâa-Tafilalet"},
                {"type": "mrkdwn", "text": f"*Heure :* {datetime.now().strftime('%H:%M %d/%m/%Y')}"}]},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*Facteurs de risque :*\n{factors_text}"}},
            {"type": "context", "elements": [{"type": "mrkdwn",
                "text": f"FireWatch Agdez v{self.config['api']['model_version']} | "
                        f"Lat: {self.config['location']['latitude']} | "
                        f"Lon: {self.config['location']['longitude']}"}]},
        ]

    def send_risk_alert(self, risk_level: str, confidence: float,
                         factors: List[str], force: bool = False) -> bool:
        """Envoie une alerte de risque via Slack webhook."""
        if not force and not self._check_cooldown():
            logger.info("Cooldown Slack actif, alerte non envoyée")
            return False
        color = RISK_COLORS.get(risk_level, "#666666")
        payload = {
            "channel": self.channel,
            "username": "FireWatch Agdez",
            "icon_emoji": ":fire:",
            "attachments": [{"color": color, "blocks": self._build_blocks(risk_level, confidence, factors)}],
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                self._update_cooldown()
                logger.info("Alerte Slack envoyée (risque: %s)", risk_level)
                return True
            logger.warning("Slack réponse: %d %s", resp.status_code, resp.text)
            return False
        except Exception as e:
            logger.error("Échec envoi Slack: %s", e)
            return False

if __name__ == "__main__":
    alert = SlackAlert()
    blocks = alert._build_blocks("Élevé", 0.87, ["Température 42°C", "Humidité 8%"])
    print("=== Slack Blocks Preview ===")
    print(json.dumps(blocks, indent=2, ensure_ascii=False))
    print("✅ Bloc Slack généré avec succès.")
