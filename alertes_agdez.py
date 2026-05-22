# ============================================================================
# alertes_agdez.py — Module d'alertes complet
# Agdez Fire Risk Dashboard · Version 2.0
# ============================================================================
# Ce module gère l'envoi d'alertes en cas de risque Élevé ou Très élevé :
#   - Email SMTP (Gmail, Outlook, ou tout serveur SMTP)
#   - Webhook (Slack, Discord, Teams, n8n, Make, Zapier…)
#   - Journalisation JSON automatique
#   - Anti-doublon (cooldown configurable)
# ============================================================================
# Installation des dépendances supplémentaires :
#   pip install requests
#   (smtplib est inclus dans la bibliothèque standard Python)
# ============================================================================

import json
import logging
import smtplib
import traceback
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AgdezAlertes")

# ── Constantes ────────────────────────────────────────────────────────────────
RISQUE_EMOJI = {
    "Faible": "🟢", "Moyen": "🟡", "Élevé": "🟠", "Très élevé": "🔴",
}
RISQUE_COLOR_HEX = {
    "Faible": "#27ae60", "Moyen": "#e67e22",
    "Élevé": "#e74c3c", "Très élevé": "#8e1a1a",
}
NIVEAUX_ALERTE = {"Élevé", "Très élevé"}

# Cooldown par défaut : 60 minutes entre deux alertes identiques
DEFAULT_COOLDOWN_MINUTES = 60


# ============================================================================
# ── Configuration des alertes ─────────────────────────────────────────────────
# ============================================================================

class ConfigAlertes:
    """
    Centralise la configuration des alertes.
    Chargez depuis un fichier .json ou remplissez directement.

    Exemple de fichier config_alertes.json :
    {
        "email": {
            "actif": true,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "votre.email@gmail.com",
            "smtp_password": "mot_de_passe_application",
            "destinataires": ["pompiers@agdez.ma", "commune@agdez.ma"],
            "expediteur_nom": "Système Alerte Incendie Agdez"
        },
        "webhook": {
            "actif": true,
            "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
            "type": "slack"
        },
        "options": {
            "cooldown_minutes": 60,
            "sauvegarder_json": true,
            "repertoire_rapports": "reports"
        }
    }
    """

    def __init__(self, config_path: str | Path | None = None):
        self.email_actif       = False
        self.smtp_host         = "smtp.gmail.com"
        self.smtp_port         = 587
        self.smtp_user         = ""
        self.smtp_password     = ""
        self.destinataires     = []
        self.expediteur_nom    = "Système Alerte Incendie Agdez"

        self.webhook_actif     = False
        self.webhook_url       = ""
        self.webhook_type      = "generic"  # "slack" | "discord" | "teams" | "generic"

        self.cooldown_minutes  = DEFAULT_COOLDOWN_MINUTES
        self.sauvegarder_json  = True
        self.repertoire_rapports = Path("reports")

        if config_path:
            self._charger_fichier(Path(config_path))

    def _charger_fichier(self, path: Path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)

            em = cfg.get("email", {})
            self.email_actif    = em.get("actif", False)
            self.smtp_host      = em.get("smtp_host", self.smtp_host)
            self.smtp_port      = em.get("smtp_port", self.smtp_port)
            self.smtp_user      = em.get("smtp_user", "")
            self.smtp_password  = em.get("smtp_password", "")
            self.destinataires  = em.get("destinataires", [])
            self.expediteur_nom = em.get("expediteur_nom", self.expediteur_nom)

            wh = cfg.get("webhook", {})
            self.webhook_actif  = wh.get("actif", False)
            self.webhook_url    = wh.get("url", "")
            self.webhook_type   = wh.get("type", "generic")

            opt = cfg.get("options", {})
            self.cooldown_minutes     = opt.get("cooldown_minutes", self.cooldown_minutes)
            self.sauvegarder_json     = opt.get("sauvegarder_json", True)
            self.repertoire_rapports  = Path(opt.get("repertoire_rapports", "reports"))

            logger.info(f"✅ Configuration alertes chargée depuis {path}")
        except FileNotFoundError:
            logger.warning(f"⚠️ {path} introuvable — utilisation des valeurs par défaut")
        except Exception as e:
            logger.error(f"❌ Erreur lecture config : {e}")

    def valider(self) -> list[str]:
        """Retourne une liste d'erreurs de configuration (vide = OK)."""
        erreurs = []
        if self.email_actif:
            if not self.smtp_user:
                erreurs.append("email.smtp_user est vide")
            if not self.smtp_password:
                erreurs.append("email.smtp_password est vide")
            if not self.destinataires:
                erreurs.append("email.destinataires est vide")
        if self.webhook_actif:
            if not self.webhook_url:
                erreurs.append("webhook.url est vide")
        return erreurs


# ============================================================================
# ── Payload de l'alerte ───────────────────────────────────────────────────────
# ============================================================================

class PayloadAlerte:
    """Représente une alerte à envoyer."""

    def __init__(
        self,
        risque: str,
        confiance: float,
        temperature: float,
        humidite: float,
        precipitation: float,
        vent: float,
        mois: str,
        annee: int,
        zone: str = "Agdez, Drâa-Tafilalet, Maroc",
        recommandation: str = "",
        scenario: str = "",
        probas: dict | None = None,
    ):
        self.risque         = risque
        self.confiance      = confiance
        self.temperature    = temperature
        self.humidite       = humidite
        self.precipitation  = precipitation
        self.vent           = vent
        self.mois           = mois
        self.annee          = annee
        self.zone           = zone
        self.recommandation = recommandation
        self.scenario       = scenario or f"{mois} {annee}"
        self.probas         = probas or {}
        self.timestamp      = datetime.now()
        self.priorite       = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
        self.emoji          = RISQUE_EMOJI.get(risque, "⚠️")
        self.couleur        = RISQUE_COLOR_HEX.get(risque, "#888")

    def to_dict(self) -> dict:
        return {
            "timestamp":     self.timestamp.isoformat(),
            "priorite":      self.priorite,
            "risque":        self.risque,
            "confiance":     round(self.confiance, 4),
            "zone":          self.zone,
            "scenario":      self.scenario,
            "mois":          self.mois,
            "annee":         self.annee,
            "conditions":    {
                "temperature":   self.temperature,
                "humidite":      self.humidite,
                "precipitation": self.precipitation,
                "vent":          self.vent,
            },
            "probabilites":  self.probas,
            "recommandation": self.recommandation,
        }

    def cle_cooldown(self) -> str:
        """Clé unique pour le contrôle du cooldown."""
        return f"{self.risque}_{self.annee}_{self.mois}"


# ============================================================================
# ── Gestionnaire d'alertes ────────────────────────────────────────────────────
# ============================================================================

class GestionnaireAlertes:
    """
    Orchestre l'envoi d'alertes via email et/ou webhook.
    Intègre anti-doublon (cooldown) et journalisation JSON.
    """

    def __init__(self, config: ConfigAlertes):
        self.cfg          = config
        self._historique: dict[str, datetime] = {}  # cooldown en mémoire

    # ── API publique ──────────────────────────────────────────────────────────

    def traiter(self, payload: PayloadAlerte) -> dict:
        """
        Point d'entrée principal.
        Retourne un dict avec les résultats de chaque canal.
        """
        resultats = {
            "timestamp":  payload.timestamp.isoformat(),
            "risque":     payload.risque,
            "priorite":   payload.priorite,
            "email":      None,
            "webhook":    None,
            "json":       None,
            "cooldown":   False,
        }

        # Vérifier le niveau
        if payload.risque not in NIVEAUX_ALERTE:
            logger.info(f"Risque {payload.risque} → aucune alerte nécessaire")
            return resultats

        # Vérifier le cooldown
        if self._en_cooldown(payload):
            logger.info(f"Alerte {payload.cle_cooldown()} en cooldown — ignorée")
            resultats["cooldown"] = True
            return resultats

        # Envoi
        erreurs = self.cfg.valider()
        if erreurs:
            logger.warning(f"⚠️ Config incomplète : {erreurs}")

        if self.cfg.email_actif and not erreurs:
            resultats["email"] = self._envoyer_email(payload)

        if self.cfg.webhook_actif:
            resultats["webhook"] = self._envoyer_webhook(payload)

        if self.cfg.sauvegarder_json:
            resultats["json"] = self._sauvegarder_json(payload)

        # Mettre à jour l'historique cooldown
        self._historique[payload.cle_cooldown()] = payload.timestamp
        return resultats

    # ── Email ─────────────────────────────────────────────────────────────────

    def _envoyer_email(self, p: PayloadAlerte) -> dict:
        """Envoie un email HTML formaté via SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"🔥 ALERTE {p.priorite} — Risque Incendie {p.risque} · "
                f"{p.mois} {p.annee} · Agdez"
            )
            msg["From"]    = f"{self.cfg.expediteur_nom} <{self.cfg.smtp_user}>"
            msg["To"]      = ", ".join(self.cfg.destinataires)

            # Corps texte brut
            corps_txt = self._corps_texte(p)
            # Corps HTML
            corps_html = self._corps_html(p)

            msg.attach(MIMEText(corps_txt,  "plain", "utf-8"))
            msg.attach(MIMEText(corps_html, "html",  "utf-8"))

            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port) as serveur:
                serveur.ehlo()
                serveur.starttls()
                serveur.login(self.cfg.smtp_user, self.cfg.smtp_password)
                serveur.sendmail(
                    self.cfg.smtp_user,
                    self.cfg.destinataires,
                    msg.as_string(),
                )

            logger.info(f"✅ Email envoyé à {self.cfg.destinataires}")
            return {"succes": True, "destinataires": self.cfg.destinataires}

        except smtplib.SMTPAuthenticationError:
            msg_err = "Authentification SMTP échouée — vérifiez smtp_user/smtp_password"
            logger.error(f"❌ {msg_err}")
            return {"succes": False, "erreur": msg_err}

        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP : {e}")
            return {"succes": False, "erreur": str(e)}

        except Exception as e:
            logger.error(f"❌ Email inattendu : {traceback.format_exc()}")
            return {"succes": False, "erreur": str(e)}

    def _corps_texte(self, p: PayloadAlerte) -> str:
        prob_txt = "\n".join([f"  {k}: {v:.0%}" for k, v in p.probas.items()])
        return f"""
⚡ ALERTE {p.priorite} — RISQUE INCENDIE {p.risque.upper()}
{'='*55}
📍 Zone        : {p.zone}
📅 Période     : {p.mois} {p.annee}
🔥 Risque      : {p.risque}
📊 Confiance   : {p.confiance:.0%}
🕐 Généré le   : {p.timestamp.strftime('%d/%m/%Y à %H:%M:%S')}

CONDITIONS MÉTÉO
  🌡️ Température   : {p.temperature}°C
  💧 Humidité      : {p.humidite}%
  🌧️ Précipitations : {p.precipitation} mm
  💨 Vent          : {p.vent} m/s

PROBABILITÉS MODÈLE (Random Forest)
{prob_txt}

RECOMMANDATION
  {p.recommandation}

─────────────────────────────────────────────────────
Système Automatique de Prédiction — Agdez, Maroc 🇲🇦
Random Forest v1.0.0 · Données 2017–2025
Ne pas répondre à cet email.
""".strip()

    def _corps_html(self, p: PayloadAlerte) -> str:
        prob_html = "".join([
            f"""<tr>
              <td style="padding:6px 12px;font-size:13px;color:#555">{k}</td>
              <td style="padding:6px 12px">
                <div style="background:#f0f0f0;border-radius:4px;height:16px;width:160px;display:inline-block;vertical-align:middle">
                  <div style="background:{RISQUE_COLOR_HEX.get(k,'#888')};width:{v*100:.0f}%;height:16px;border-radius:4px"></div>
                </div>
                <span style="margin-left:8px;font-size:13px;font-weight:600">{v:.0%}</span>
              </td>
            </tr>"""
            for k, v in p.probas.items()
        ])

        return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px}}
  .card{{background:#fff;border-radius:12px;max-width:600px;margin:auto;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.12)}}
  .header{{background:{p.couleur};padding:24px 28px;color:#fff}}
  .header h1{{margin:0;font-size:22px;letter-spacing:-0.5px}}
  .header p{{margin:6px 0 0;opacity:.85;font-size:13px}}
  .body{{padding:24px 28px}}
  .badge{{display:inline-block;background:{"#fee2e2" if p.priorite=="CRITIQUE" else "#ffedd5"};
           color:{p.couleur};border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  td{{padding:8px 12px;font-size:14px;border-bottom:1px solid #f0f0f0}}
  td:first-child{{color:#555;width:140px}}
  td:last-child{{font-weight:600;color:#1a1a1a}}
  .reco{{background:#fff8e6;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;
          padding:12px 16px;margin-top:20px;font-size:13px;color:#7c5310;line-height:1.6}}
  .footer{{background:#f9f9f9;padding:14px 28px;font-size:11px;color:#aaa;text-align:center;border-top:1px solid #eee}}
</style></head>
<body>
<div class="card">
  <div class="header">
    <div style="font-size:32px;margin-bottom:8px">{p.emoji}</div>
    <h1>ALERTE {p.priorite} — Risque {p.risque}</h1>
    <p>{p.zone} · {p.mois} {p.annee} · {p.timestamp.strftime('%d/%m/%Y %H:%M')}</p>
  </div>
  <div class="body">
    <div class="badge">⚡ {p.priorite} · Confiance {p.confiance:.0%}</div>
    <table>
      <tr><td>📅 Période</td><td>{p.mois} {p.annee}</td></tr>
      <tr><td>🌡️ Température</td><td>{p.temperature}°C</td></tr>
      <tr><td>💧 Humidité</td><td>{p.humidite}%</td></tr>
      <tr><td>🌧️ Précipitations</td><td>{p.precipitation} mm</td></tr>
      <tr><td>💨 Vent</td><td>{p.vent} m/s</td></tr>
    </table>

    <p style="margin:20px 0 8px;font-size:13px;font-weight:700;color:#333">
      Probabilités — Modèle Random Forest
    </p>
    <table>{prob_html}</table>

    <div class="reco">
      <strong>📋 Recommandation :</strong><br>{p.recommandation}
    </div>
  </div>
  <div class="footer">
    Système Automatique de Prédiction · Agdez, Maroc 🇲🇦 ·
    Random Forest v1.0.0 · Données 2017–2025 · Ne pas répondre à cet email.
  </div>
</div>
</body></html>"""

    # ── Webhook ───────────────────────────────────────────────────────────────

    def _envoyer_webhook(self, p: PayloadAlerte) -> dict:
        """Envoie une notification webhook (Slack / Discord / Teams / générique)."""
        try:
            payload_http = self._build_webhook_payload(p)
            resp = requests.post(
                self.cfg.webhook_url,
                json=payload_http,
                timeout=8,
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code in (200, 204):
                logger.info(f"✅ Webhook envoyé ({resp.status_code})")
                return {"succes": True, "status_code": resp.status_code}
            else:
                logger.error(f"❌ Webhook HTTP {resp.status_code} : {resp.text[:200]}")
                return {"succes": False, "status_code": resp.status_code, "erreur": resp.text[:200]}

        except requests.exceptions.ConnectionError:
            msg_err = "Impossible de joindre le webhook — vérifiez l'URL et la connexion"
            logger.error(f"❌ {msg_err}")
            return {"succes": False, "erreur": msg_err}

        except Exception as e:
            logger.error(f"❌ Webhook inattendu : {e}")
            return {"succes": False, "erreur": str(e)}

    def _build_webhook_payload(self, p: PayloadAlerte) -> dict:
        prob_txt = " | ".join([f"{k}: {v:.0%}" for k, v in p.probas.items()])
        titre    = f"{p.emoji} ALERTE {p.priorite} — Risque {p.risque} · {p.mois} {p.annee}"
        texte    = (
            f"📍 {p.zone}\n"
            f"📊 Confiance : {p.confiance:.0%}\n"
            f"🌡️ T={p.temperature}°C | 💧 H={p.humidite}% | "
            f"🌧️ P={p.precipitation}mm | 💨 V={p.vent}m/s\n"
            f"Probabilités : {prob_txt}\n"
            f"💬 {p.recommandation}"
        )

        if self.cfg.webhook_type == "slack":
            return {
                "text": titre,
                "attachments": [{
                    "color":   p.couleur,
                    "text":    texte,
                    "footer":  f"Agdez Fire Risk · {p.timestamp.strftime('%d/%m/%Y %H:%M')}",
                    "mrkdwn_in": ["text"],
                }],
            }

        elif self.cfg.webhook_type == "discord":
            return {
                "username":  "🔥 Agdez Fire Alert",
                "content":   titre,
                "embeds": [{
                    "description": texte,
                    "color":       int(p.couleur.lstrip("#"), 16),
                    "footer":      {"text": f"Agdez · {p.timestamp.strftime('%d/%m/%Y %H:%M')}"},
                }],
            }

        elif self.cfg.webhook_type == "teams":
            return {
                "@type":     "MessageCard",
                "@context":  "https://schema.org/extensions",
                "themeColor": p.couleur.lstrip("#"),
                "summary":   titre,
                "sections": [{
                    "activityTitle":    titre,
                    "activitySubtitle": f"📍 {p.zone}",
                    "text":             texte.replace("\n", "<br>"),
                }],
            }

        else:  # generic JSON
            return p.to_dict()

    # ── Journalisation JSON ───────────────────────────────────────────────────

    def _sauvegarder_json(self, p: PayloadAlerte) -> dict:
        """Sauvegarde l'alerte dans un fichier JSON horodaté."""
        try:
            self.cfg.repertoire_rapports.mkdir(parents=True, exist_ok=True)
            nom = f"alerte_{p.timestamp.strftime('%Y%m%d_%H%M%S')}_{p.risque.replace(' ','_')}.json"
            chemin = self.cfg.repertoire_rapports / nom
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(p.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Alerte sauvegardée : {chemin}")
            return {"succes": True, "fichier": str(chemin)}
        except Exception as e:
            logger.error(f"❌ Sauvegarde JSON : {e}")
            return {"succes": False, "erreur": str(e)}

    # ── Cooldown ─────────────────────────────────────────────────────────────

    def _en_cooldown(self, p: PayloadAlerte) -> bool:
        cle      = p.cle_cooldown()
        derniere = self._historique.get(cle)
        if derniere is None:
            return False
        return (p.timestamp - derniere) < timedelta(minutes=self.cfg.cooldown_minutes)

    def temps_restant_cooldown(self, payload: PayloadAlerte) -> int | None:
        """Retourne les minutes restantes de cooldown, ou None si pas en cooldown."""
        cle      = payload.cle_cooldown()
        derniere = self._historique.get(cle)
        if derniere is None:
            return None
        delta = timedelta(minutes=self.cfg.cooldown_minutes) - (datetime.now() - derniere)
        mins  = int(delta.total_seconds() / 60)
        return max(0, mins) if mins > 0 else None

    def reinitialiser_cooldown(self, payload: PayloadAlerte | None = None):
        """Réinitialise le cooldown (tout ou pour un payload précis)."""
        if payload:
            self._historique.pop(payload.cle_cooldown(), None)
        else:
            self._historique.clear()
        logger.info("🔄 Cooldown réinitialisé")


# ============================================================================
# ── Intégration Streamlit ─────────────────────────────────────────────────────
# ============================================================================

def render_panneau_alertes_streamlit(
    gestionnaire: GestionnaireAlertes,
    risque: str,
    confiance: float,
    temperature: float,
    humidite: float,
    precipitation: float,
    vent: float,
    mois: str,
    annee: int,
    probas: dict,
    recommandation: str,
):
    """
    Panneau complet d'alertes à insérer dans un onglet Streamlit.
    Remplace l'ancien TAB 6.

    Paramètres :
        gestionnaire : instance de GestionnaireAlertes (instancier avec ConfigAlertes)
        risque, confiance, …  : données courantes du dashboard
    """
    import streamlit as st

    RISQUE_COLOR = {
        "Faible": "#27ae60", "Moyen": "#e67e22",
        "Élevé": "#e74c3c", "Très élevé": "#8e1a1a",
    }

    st.markdown('<div class="sec">Alertes dynamiques — générées à la volée</div>',
                unsafe_allow_html=True)

    # ── Statut configuration ──────────────────────────────────────────────────
    erreurs_cfg = gestionnaire.cfg.valider()
    if erreurs_cfg:
        st.warning(
            "⚙️ **Configuration incomplète** — les envois réels sont désactivés.\n\n"
            + "\n".join([f"• {e}" for e in erreurs_cfg])
            + "\n\nChargez `config_alertes.json` pour activer les notifications.",
            icon="⚠️",
        )
    else:
        canaux = []
        if gestionnaire.cfg.email_actif:
            canaux.append(f"📧 Email → {', '.join(gestionnaire.cfg.destinataires)}")
        if gestionnaire.cfg.webhook_actif:
            canaux.append(f"🔗 Webhook ({gestionnaire.cfg.webhook_type})")
        st.success("✅ " + " · ".join(canaux) if canaux else "✅ Configuration OK")

    st.markdown("---")

    # ── Alerte courante ───────────────────────────────────────────────────────
    st.markdown("**🔴 Alerte courante (conditions sliders)**")

    payload_courant = PayloadAlerte(
        risque=risque, confiance=confiance,
        temperature=temperature, humidite=humidite,
        precipitation=precipitation, vent=vent,
        mois=mois, annee=annee,
        recommandation=recommandation,
        probas=probas,
    )

    if risque in NIVEAUX_ALERTE:
        prio    = payload_courant.priorite
        css     = "alert-r" if risque == "Très élevé" else "alert-o"
        tag_css = "tag-r"   if risque == "Très élevé" else "tag-o"
        color   = RISQUE_COLOR.get(risque, "#888")

        st.markdown(f"""
        <div class="{css}">
          <span class="tag {tag_css}">⚡ {prio}</span>
          <div style="font-weight:700;font-size:0.95rem;margin:5px 0">
            {RISQUE_EMOJI.get(risque,'⚠️')} Risque {risque} — {mois} {annee}
          </div>
          <div style="font-size:0.82rem;color:#ddd;line-height:1.8">
            📍 Agdez, Maroc · Confiance : <b>{confiance:.0%}</b><br>
            🌡️ T={temperature}°C | 💧 H={humidite}% | 🌧️ P={precipitation}mm | 💨 V={vent}m/s<br>
            🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br>
            💬 <b>{recommandation}</b>
          </div>
        </div>""", unsafe_allow_html=True)

        # ── Bouton d'envoi ────────────────────────────────────────────────────
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            en_cooldown = gestionnaire._en_cooldown(payload_courant)
            mins_restant = gestionnaire.temps_restant_cooldown(payload_courant)

            if en_cooldown:
                st.button(
                    f"⏳ Cooldown — {mins_restant} min restantes",
                    disabled=True,
                    help=f"Une alerte identique a déjà été envoyée il y a moins de "
                         f"{gestionnaire.cfg.cooldown_minutes} minutes.",
                )
            else:
                if st.button(
                    "📤 Envoyer l'alerte maintenant",
                    type="primary",
                    help="Envoie l'alerte par email et/ou webhook selon la configuration.",
                ):
                    with st.spinner("⏳ Envoi en cours…"):
                        resultats = gestionnaire.traiter(payload_courant)

                    # Résultats
                    if resultats.get("email"):
                        if resultats["email"].get("succes"):
                            st.success(f"✅ Email envoyé à {resultats['email']['destinataires']}")
                        else:
                            st.error(f"❌ Email échoué : {resultats['email'].get('erreur')}")

                    if resultats.get("webhook"):
                        if resultats["webhook"].get("succes"):
                            st.success("✅ Webhook envoyé avec succès")
                        else:
                            st.error(f"❌ Webhook échoué : {resultats['webhook'].get('erreur')}")

                    if resultats.get("json"):
                        if resultats["json"].get("succes"):
                            st.info(f"💾 Sauvegardée : {resultats['json']['fichier']}")

        with col_info:
            st.caption(
                f"Cooldown : {gestionnaire.cfg.cooldown_minutes} min · "
                f"Email : {'✅' if gestionnaire.cfg.email_actif else '❌'} · "
                f"Webhook : {'✅' if gestionnaire.cfg.webhook_actif else '❌'}"
            )

            # Bouton test (simulation sans envoi réel)
            if st.button("🧪 Simuler (sans envoi)", help="Affiche ce qui serait envoyé, sans envoyer."):
                st.json(payload_courant.to_dict())

    else:
        st.success(f"✅ Risque **{risque}** — Aucune alerte requise pour les conditions actuelles.")

    # ── Scénarios 2026 ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Alertes générées par les scénarios 2026**")

    # Note : df_sc doit être passé depuis le contexte principal
    # Exemple d'utilisation dans main() :
    #   render_panneau_alertes_streamlit(gestionnaire, ..., df_sc=D["sc"])
    # Ici on affiche juste un message si df_sc n'est pas disponible
    st.info(
        "💡 Pour afficher les alertes scénarios, intégrez ce module dans votre `main()` "
        "et passez `D['sc']` à la fonction `render_panneau_alertes_streamlit`."
    )

    st.markdown("---")
    st.markdown("**Réinitialiser le cooldown (tests)**")
    if st.button("🔄 Reset cooldown"):
        gestionnaire.reinitialiser_cooldown()
        st.success("✅ Cooldown réinitialisé — vous pouvez renvoyer l'alerte.")


# ============================================================================
# ── Utilisation autonome (tests hors Streamlit) ───────────────────────────────
# ============================================================================

def creer_gestionnaire(config_path: str | Path | None = None) -> GestionnaireAlertes:
    """
    Factory function : crée un GestionnaireAlertes prêt à l'emploi.
    Utilisez `config_path` pour charger la configuration depuis un JSON.
    """
    cfg = ConfigAlertes(config_path)
    return GestionnaireAlertes(cfg)


if __name__ == "__main__":
    # ── Exemple de test autonome ──────────────────────────────────────────────
    print("🔥 Test module alertes Agdez\n")

    # Configuration de test (sans envoi réel)
    cfg = ConfigAlertes()
    cfg.email_actif      = False   # Mettre True + remplir smtp_user/password pour tester
    cfg.webhook_actif    = False   # Mettre True + remplir webhook_url pour tester
    cfg.sauvegarder_json = True
    cfg.repertoire_rapports = Path("reports_test")

    gestionnaire = GestionnaireAlertes(cfg)

    payload = PayloadAlerte(
        risque="Très élevé",
        confiance=0.82,
        temperature=36.5,
        humidite=12.0,
        precipitation=0.0,
        vent=5.2,
        mois="Juillet",
        annee=2026,
        recommandation="🔴 DANGER — Activer plan ORSEC. Interdire accès zones boisées.",
        probas={"Faible": 0.05, "Moyen": 0.08, "Élevé": 0.05, "Très élevé": 0.82},
    )

    print(f"Payload : {json.dumps(payload.to_dict(), ensure_ascii=False, indent=2)}")
    resultats = gestionnaire.traiter(payload)
    print(f"\nRésultats : {json.dumps(resultats, ensure_ascii=False, indent=2)}")
