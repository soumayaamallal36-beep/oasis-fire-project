# ============================================================================
# systeme_alertes.py — Système d'Alerte Automatique · Agdez Fire Risk
# ============================================================================
# Usage :
#   python systeme_alertes.py                  → surveillance continue
#   python systeme_alertes.py --test           → test email immédiat
#   python systeme_alertes.py --once           → une seule vérification
# ============================================================================

import json, smtplib, time, argparse, logging, sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("alertes.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("AgdezAlert")

BASE = Path(__file__).parent
RPT  = BASE / "reports"
RPT.mkdir(parents=True, exist_ok=True)

# ── Couleurs & emojis risque ─────────────────────────────────────────────────
RISQUE_COLOR = {
    "Faible":     "#27ae60",
    "Moyen":      "#e67e22",
    "Élevé":      "#e74c3c",
    "Très élevé": "#8e1a1a",
}
RISQUE_EMOJI = {
    "Faible":     "🟢",
    "Moyen":      "🟡",
    "Élevé":      "🟠",
    "Très élevé": "🔴",
}
NIVEAUX_ALERTE = {"Élevé", "Très élevé"}

# ============================================================================
# ── Configuration ─────────────────────────────────────────────────────────────
# ============================================================================
class Config:
    def __init__(self, path: str = "config_alertes.json"):
        self.path = Path(path)
        # Valeurs par défaut
        self.email_actif        = False
        self.smtp_host          = "smtp.gmail.com"
        self.smtp_port          = 587
        self.smtp_user          = ""
        self.smtp_password      = ""
        self.destinataires      = []
        self.expediteur_nom     = "Système Alerte Incendie Agdez"
        self.webhook_actif      = False
        self.webhook_url        = ""
        self.webhook_type       = "slack"
        self.cooldown_minutes   = 60
        self.intervalle_minutes = 30
        self.sauvegarder_json   = True
        self.niveaux_alerte     = ["Élevé", "Très élevé"]
        self.charger()

    def charger(self):
        if not self.path.exists():
            log.warning(f"⚠️  {self.path} introuvable → valeurs par défaut")
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            em   = data.get("email", {})
            self.email_actif       = em.get("actif", False)
            self.smtp_host         = em.get("smtp_host",     self.smtp_host)
            self.smtp_port         = em.get("smtp_port",     self.smtp_port)
            self.smtp_user         = em.get("smtp_user",     "")
            self.smtp_password     = em.get("smtp_password", "")
            self.destinataires     = em.get("destinataires", [])
            self.expediteur_nom    = em.get("expediteur_nom", self.expediteur_nom)
            wh = data.get("webhook", {})
            self.webhook_actif     = wh.get("actif", False)
            self.webhook_url       = wh.get("url",   "")
            self.webhook_type      = wh.get("type",  "slack")
            opt = data.get("options", {})
            self.cooldown_minutes   = opt.get("cooldown_minutes",   60)
            self.intervalle_minutes = opt.get("intervalle_minutes", 30)
            self.sauvegarder_json   = opt.get("sauvegarder_json",   True)
            self.niveaux_alerte     = opt.get("niveaux_alerte",
                                              ["Élevé","Très élevé"])
            log.info("✅ Configuration chargée depuis %s", self.path)
        except Exception as e:
            log.error("❌ Erreur lecture config : %s", e)

    def valider(self) -> list[str]:
        erreurs = []
        if self.email_actif:
            if not self.smtp_user:      erreurs.append("smtp_user vide")
            if not self.smtp_password:  erreurs.append("smtp_password vide")
            if not self.destinataires:  erreurs.append("destinataires vide")
        if self.webhook_actif and not self.webhook_url:
            erreurs.append("webhook_url vide")
        return erreurs

# ============================================================================
# ── Gestion du cooldown ───────────────────────────────────────────────────────
# ============================================================================
COOLDOWN_FILE = BASE / "reports" / ".derniere_alerte.json"

def lire_derniere_alerte() -> dict:
    try:
        if COOLDOWN_FILE.exists():
            return json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def ecrire_derniere_alerte(risque: str):
    try:
        COOLDOWN_FILE.write_text(
            json.dumps({"risque": risque,
                        "timestamp": datetime.now().isoformat()}),
            encoding="utf-8"
        )
    except Exception as e:
        log.warning("Impossible d'écrire le cooldown : %s", e)

def cooldown_actif(cfg: Config) -> bool:
    """Retourne True si on doit attendre avant d'envoyer une nouvelle alerte."""
    d = lire_derniere_alerte()
    if not d.get("timestamp"):
        return False
    try:
        derniere = datetime.fromisoformat(d["timestamp"])
        ecart    = (datetime.now() - derniere).total_seconds() / 60
        if ecart < cfg.cooldown_minutes:
            restant = cfg.cooldown_minutes - ecart
            log.info("⏳ Cooldown actif — prochaine alerte dans %.0f min", restant)
            return True
    except Exception:
        pass
    return False

# ============================================================================
# ── Récupération météo temps réel ────────────────────────────────────────────
# ============================================================================
LAT, LON = 30.69, -6.45

def fetch_meteo() -> dict | None:
    try:
        import requests
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            "&current=temperature_2m,relative_humidity_2m,"
            "precipitation,wind_speed_10m"
            "&wind_speed_unit=ms&timezone=Africa%2FCasablanca"
        )
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            c = r.json()["current"]
            return {
                "temperature":   round(c["temperature_2m"], 1),
                "humidite":      round(c["relative_humidity_2m"], 1),
                "precipitation": round(c["precipitation"], 2),
                "vent":          round(c["wind_speed_10m"], 1),
                "source":        "Open-Meteo (temps réel)",
                "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    except Exception as e:
        log.warning("API météo indisponible : %s", e)
    return None

# ============================================================================
# ── Prédiction risque ─────────────────────────────────────────────────────────
# ============================================================================
ALTITUDE, PENTE, EXPOSITION = 1169.3, 5.73, 165.51
FEAT_ORDER = [
    "temperature","humidite","precipitation","vent",
    "pente","altitude","exposition","ndvi_avant",
    "indice_secheresse","indice_propagation","stress_vegetal",
    "exposition_sud","mois_num",
]

def predire_risque(t: float, h: float, p: float, v: float,
                   mois_num: int = 1, ndvi: float = 0.144):
    """Charge le modèle RF et prédit le niveau de risque."""
    try:
        import joblib, numpy as np, pandas as pd
        from pathlib import Path
        mdl = BASE / "models" / "trained"
        model = joblib.load(mdl / "model_risque_incendie.pkl")
        le    = joblib.load(mdl / "label_encoder.pkl")

        row = dict(temperature=t, humidite=h, precipitation=p, vent=v,
                   pente=PENTE, altitude=ALTITUDE, exposition=EXPOSITION,
                   ndvi_avant=ndvi, mois_num=mois_num)
        df  = pd.DataFrame([row])
        df["indice_secheresse"]  = (t - h) / (p + 0.1)
        df["indice_propagation"] = v * np.sin(np.radians(PENTE))
        df["stress_vegetal"]     = (1 - ndvi) * t / 10
        df["exposition_sud"]     = float(np.cos(np.radians(EXPOSITION - 180)))
        X = df[FEAT_ORDER]

        y      = model.predict(X)[0]
        probas = model.predict_proba(X)[0]
        label  = le.inverse_transform([y])[0]
        return label, float(probas.max()), {
            c: float(pb) for c, pb in zip(le.classes_, probas)
        }
    except Exception as e:
        log.warning("Modèle ML indisponible (%s) → évaluation heuristique", e)
        return _heuristique_risque(t, h, p, v)

def _heuristique_risque(t, h, p, v):
    """Évaluation sans modèle ML — règles métier."""
    score = 0
    if t >= 35:     score += 3
    elif t >= 32:   score += 2
    elif t >= 28:   score += 1
    if h <= 15:     score += 3
    elif h <= 25:   score += 2
    elif h <= 35:   score += 1
    if p <= 1:      score += 2
    elif p <= 10:   score += 1
    if v >= 6:      score += 2
    elif v >= 4:    score += 1

    if score >= 8:
        risque, conf = "Très élevé", 0.88
    elif score >= 5:
        risque, conf = "Élevé",      0.76
    elif score >= 3:
        risque, conf = "Moyen",      0.70
    else:
        risque, conf = "Faible",     0.82

    probas_vals = {"Faible": 0.05, "Moyen": 0.10, "Élevé": 0.25, "Très élevé": 0.60}
    if risque == "Faible":
        probas_vals = {"Faible": 0.75, "Moyen": 0.15, "Élevé": 0.07, "Très élevé": 0.03}
    elif risque == "Moyen":
        probas_vals = {"Faible": 0.15, "Moyen": 0.62, "Élevé": 0.18, "Très élevé": 0.05}
    elif risque == "Élevé":
        probas_vals = {"Faible": 0.05, "Moyen": 0.12, "Élevé": 0.66, "Très élevé": 0.17}
    else:
        probas_vals = {"Faible": 0.02, "Moyen": 0.06, "Élevé": 0.18, "Très élevé": 0.74}

    return risque, conf, probas_vals

def recommandation(risque: str) -> str:
    return {
        "Faible":     "✅ Surveillance standard. Conditions favorables.",
        "Moyen":      "⚠️ Vigilance modérée. Vérifier les équipements.",
        "Élevé":      "🟠 Patrouilles terrain actives. Alerter les équipes locales.",
        "Très élevé": "🔴 DANGER — Activer plan ORSEC. Interdire accès zones boisées.",
    }.get(risque, "—")

# ============================================================================
# ── Construction de l'email HTML ─────────────────────────────────────────────
# ============================================================================
def construire_email(risque: str, conf: float, meteo: dict, probas: dict,
                     cfg: Config) -> tuple[str, str, str]:
    """Retourne (sujet, corps_texte, corps_html)."""
    now     = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    prio    = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
    couleur = RISQUE_COLOR.get(risque, "#888")
    emoji   = RISQUE_EMOJI.get(risque, "⚠️")
    mois_fr = datetime.now().strftime("%B %Y")
    reco    = recommandation(risque)
    t       = meteo.get("temperature", "—")
    h       = meteo.get("humidite",    "—")
    p       = meteo.get("precipitation","—")
    v       = meteo.get("vent",        "—")
    source  = meteo.get("source",      "Manuel")

    ind_sec = round((float(t) - float(h)) / (float(p) + 0.1), 2) if p != "—" else "—"

    sujet = (
        f"🔥 ALERTE {prio} — Risque Incendie {risque}"
        f" · Agdez · {now}"
    )

    # ── Texte brut ────────────────────────────────────────────────────────────
    prob_txt = "\n".join(f"  {k}: {v:.0%}" for k, v in probas.items())
    corps_txt = f"""
⚡ ALERTE {prio} — RISQUE INCENDIE {risque.upper()}
{'='*58}
📍 Zone        : Agdez, Drâa-Tafilalet, Maroc
📅 Date/Heure  : {now}
📊 Confiance   : {conf:.0%}
🌐 Source météo: {source}

CONDITIONS MÉTÉOROLOGIQUES
  🌡️ Température    : {t}°C
  💧 Humidité       : {h}%
  🌧️ Précipitations : {p} mm
  💨 Vent           : {v} m/s
  🔥 Ind. sécheresse: {ind_sec}

PROBABILITÉS (Random Forest)
{prob_txt}

RECOMMANDATION
  {reco}

─────────────────────────────────────────────────────
Système Automatique d'Alerte · Agdez 🇲🇦
Ne pas répondre à cet email.
""".strip()

    # ── HTML ──────────────────────────────────────────────────────────────────
    prob_rows = "".join(
        f"""
        <tr>
          <td style="padding:7px 14px;color:#555;font-size:13px">{k}</td>
          <td style="padding:7px 14px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="background:#eee;border-radius:5px;
                          height:14px;width:150px;overflow:hidden">
                <div style="background:{RISQUE_COLOR.get(k,'#888')};
                            width:{pv*100:.0f}%;height:14px"></div>
              </div>
              <span style="font-weight:700;font-size:13px">{pv:.0%}</span>
            </div>
          </td>
        </tr>"""
        for k, pv in probas.items()
    )

    corps_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Alerte Incendie Agdez</title>
</head>
<body style="margin:0;padding:20px;background:#f0f2f5;
             font-family:Arial,Helvetica,sans-serif">

  <div style="max-width:620px;margin:0 auto;background:#fff;
              border-radius:14px;overflow:hidden;
              box-shadow:0 6px 30px rgba(0,0,0,0.12)">

    <!-- HEADER -->
    <div style="background:{couleur};padding:28px 32px;color:#fff">
      <div style="font-size:36px;line-height:1">{emoji}</div>
      <h1 style="margin:10px 0 4px;font-size:22px;font-weight:800;letter-spacing:-0.5px">
        ALERTE {prio} — Risque {risque}
      </h1>
      <p style="margin:0;font-size:13px;opacity:0.85">
        📍 Agdez, Drâa-Tafilalet, Maroc &nbsp;·&nbsp; {now}
      </p>
    </div>

    <!-- CONFIANCE -->
    <div style="background:{couleur}22;padding:14px 32px;
                border-bottom:1px solid {couleur}44">
      <span style="font-size:13px;color:#444">Confiance du modèle : </span>
      <span style="font-size:16px;font-weight:800;color:{couleur}">{conf:.0%}</span>
      &nbsp;&nbsp;
      <span style="font-size:12px;color:#888">Source : {source}</span>
    </div>

    <!-- CONDITIONS MÉTÉO -->
    <div style="padding:24px 32px">
      <h2 style="margin:0 0 14px;font-size:15px;font-weight:700;
                 color:#333;text-transform:uppercase;letter-spacing:0.5px">
        🌤️ Conditions météorologiques
      </h2>
      <table style="width:100%;border-collapse:collapse">
        <tr style="background:#f8f9fb">
          <td style="padding:9px 14px;font-size:13px;color:#555;width:55%">
            🌡️ Température
          </td>
          <td style="padding:9px 14px;font-size:14px;font-weight:700;color:#222">
            {t}°C
          </td>
        </tr>
        <tr>
          <td style="padding:9px 14px;font-size:13px;color:#555">
            💧 Humidité relative
          </td>
          <td style="padding:9px 14px;font-size:14px;font-weight:700;color:#222">
            {h}%
          </td>
        </tr>
        <tr style="background:#f8f9fb">
          <td style="padding:9px 14px;font-size:13px;color:#555">
            🌧️ Précipitations
          </td>
          <td style="padding:9px 14px;font-size:14px;font-weight:700;color:#222">
            {p} mm
          </td>
        </tr>
        <tr>
          <td style="padding:9px 14px;font-size:13px;color:#555">
            💨 Vitesse du vent
          </td>
          <td style="padding:9px 14px;font-size:14px;font-weight:700;color:#222">
            {v} m/s
          </td>
        </tr>
        <tr style="background:#f8f9fb">
          <td style="padding:9px 14px;font-size:13px;color:#555">
            🔥 Indice de sécheresse
          </td>
          <td style="padding:9px 14px;font-size:14px;font-weight:700;color:{couleur}">
            {ind_sec}
          </td>
        </tr>
      </table>
    </div>

    <!-- PROBABILITÉS -->
    <div style="padding:0 32px 24px">
      <h2 style="margin:0 0 14px;font-size:15px;font-weight:700;
                 color:#333;text-transform:uppercase;letter-spacing:0.5px">
        📊 Probabilités — Modèle Random Forest
      </h2>
      <table style="width:100%;border-collapse:collapse">
        {prob_rows}
      </table>
    </div>

    <!-- RECOMMANDATION -->
    <div style="margin:0 32px 24px;background:#fff8e6;
                border-left:5px solid #f59e0b;border-radius:0 10px 10px 0;
                padding:14px 18px">
      <p style="margin:0;font-size:13px;font-weight:700;color:#7c5310">
        📋 Recommandation
      </p>
      <p style="margin:8px 0 0;font-size:14px;color:#5a3c0a;line-height:1.6">
        {reco}
      </p>
    </div>

    <!-- ZONE GÉOGRAPHIQUE -->
    <div style="margin:0 32px 24px;background:#f0f4ff;
                border-radius:10px;padding:14px 18px">
      <p style="margin:0;font-size:13px;font-weight:700;color:#2d4a8a">
        📍 Zone d'alerte
      </p>
      <table style="margin-top:8px;width:100%;font-size:12px;color:#444">
        <tr>
          <td style="padding:3px 0;width:50%">🌐 Coordonnées : 30.69°N 6.45°W</td>
          <td style="padding:3px 0">⛰️ Altitude : 1 169 m</td>
        </tr>
        <tr>
          <td style="padding:3px 0">📐 Pente : 5.73°</td>
          <td style="padding:3px 0">🧭 Exposition : 165.51° (S-E)</td>
        </tr>
      </table>
    </div>

    <!-- FOOTER -->
    <div style="background:#f9f9f9;padding:16px 32px;
                border-top:1px solid #eee;text-align:center">
      <p style="margin:0;font-size:11px;color:#aaa;line-height:1.8">
        Système Automatique d'Alerte Incendie · Agdez 🇲🇦<br>
        Modèle : Random Forest v1.0.0 · Données 2017–2025<br>
        <strong>Ne pas répondre à cet email.</strong>
      </p>
    </div>

  </div>
</body>
</html>"""

    return sujet, corps_txt, corps_html

# ============================================================================
# ── Envoi email ───────────────────────────────────────────────────────────────
# ============================================================================
def envoyer_email(cfg: Config, sujet: str, txt: str, html: str) -> dict:
    try:
        msg          = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = f"{cfg.expediteur_nom} <{cfg.smtp_user}>"
        msg["To"]      = ", ".join(cfg.destinataires)
        msg.attach(MIMEText(txt,  "plain", "utf-8"))
        msg.attach(MIMEText(html, "html",  "utf-8"))

        srv = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
        srv.ehlo()
        srv.starttls()
        srv.ehlo()
        srv.login(cfg.smtp_user, cfg.smtp_password)
        srv.sendmail(cfg.smtp_user, cfg.destinataires, msg.as_string())
        srv.quit()

        log.info("✅ Email envoyé → %s", cfg.destinataires)
        return {"succes": True, "destinataires": cfg.destinataires}

    except smtplib.SMTPAuthenticationError:
        msg_err = "❌ Authentification SMTP échouée — vérifiez smtp_user/password"
        log.error(msg_err)
        return {"succes": False, "erreur": msg_err}
    except smtplib.SMTPRecipientsRefused as e:
        msg_err = f"❌ Destinataire refusé : {e}"
        log.error(msg_err)
        return {"succes": False, "erreur": msg_err}
    except Exception as e:
        log.error("❌ Erreur email : %s", e)
        return {"succes": False, "erreur": str(e)}

# ============================================================================
# ── Envoi webhook (Slack / Discord / Teams) ───────────────────────────────────
# ============================================================================
def envoyer_webhook(cfg: Config, risque: str, conf: float,
                    meteo: dict, probas: dict) -> dict:
    try:
        import requests
        couleur = RISQUE_COLOR.get(risque, "#888")
        emoji   = RISQUE_EMOJI.get(risque, "⚠️")
        prio    = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
        now     = datetime.now().strftime("%d/%m/%Y %H:%M")
        t, h, p, v = (meteo.get("temperature","—"), meteo.get("humidite","—"),
                      meteo.get("precipitation","—"), meteo.get("vent","—"))
        prob_txt = " | ".join(f"{k}: {pv:.0%}" for k, pv in probas.items())
        titre    = f"{emoji} ALERTE {prio} — Risque {risque} · Agdez · {now}"
        texte    = (f"📍 Agdez, Maroc · Confiance : {conf:.0%}\n"
                    f"🌡️ T={t}°C | 💧 H={h}% | 🌧️ P={p}mm | 💨 V={v}m/s\n"
                    f"Probabilités : {prob_txt}\n"
                    f"💬 {recommandation(risque)}")

        if cfg.webhook_type == "slack":
            data = {"text": titre,
                    "attachments": [{"color": couleur, "text": texte,
                                     "footer": f"Agdez Fire Risk · {now}"}]}
        elif cfg.webhook_type == "discord":
            data = {"username": "🔥 Agdez Fire Alert",
                    "content": titre,
                    "embeds": [{"description": texte,
                                "color": int(couleur.lstrip("#"), 16),
                                "footer": {"text": f"Agdez · {now}"}}]}
        elif cfg.webhook_type == "teams":
            data = {"@type": "MessageCard",
                    "@context": "https://schema.org/extensions",
                    "themeColor": couleur.lstrip("#"),
                    "summary": titre,
                    "sections": [{"activityTitle": titre,
                                  "text": texte.replace("\n", "<br>")}]}
        else:
            data = {"titre": titre, "texte": texte,
                    "risque": risque, "confiance": conf}

        r = requests.post(cfg.webhook_url, json=data, timeout=8,
                          headers={"Content-Type": "application/json"})
        if r.status_code in (200, 204):
            log.info("✅ Webhook envoyé (%s)", cfg.webhook_type)
            return {"succes": True, "status": r.status_code}
        log.warning("⚠️  Webhook HTTP %d : %s", r.status_code, r.text[:100])
        return {"succes": False, "status": r.status_code, "erreur": r.text[:200]}
    except Exception as e:
        log.error("❌ Webhook : %s", e)
        return {"succes": False, "erreur": str(e)}

# ============================================================================
# ── Sauvegarde JSON ───────────────────────────────────────────────────────────
# ============================================================================
def sauvegarder_json(risque: str, conf: float, meteo: dict, probas: dict) -> dict:
    try:
        nom    = f"alerte_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{risque.replace(' ','_')}.json"
        chemin = RPT / nom
        payload = {
            "timestamp": datetime.now().isoformat(),
            "risque":    risque,
            "priorite":  "CRITIQUE" if risque == "Très élevé" else "HAUTE",
            "confiance": round(conf, 4),
            "zone":      "Agdez, Drâa-Tafilalet, Maroc",
            "conditions": meteo,
            "probabilites": probas,
            "recommandation": recommandation(risque),
        }
        chemin.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        log.info("💾 Alerte sauvegardée : %s", chemin.name)
        return {"succes": True, "fichier": str(chemin)}
    except Exception as e:
        log.error("❌ Sauvegarde JSON : %s", e)
        return {"succes": False, "erreur": str(e)}

# ============================================================================
# ── Vérification principale ───────────────────────────────────────────────────
# ============================================================================
def verifier_et_alerter(cfg: Config, forcer: bool = False) -> dict:
    """
    Vérifie les conditions météo en temps réel et envoie
    une alerte si le risque est Élevé ou Très élevé.
    """
    log.info("🔍 Vérification en cours — %s",
             datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    # 1. Météo temps réel
    meteo = fetch_meteo()
    if meteo is None:
        log.warning("⚠️  Données météo indisponibles — vérification annulée")
        return {"succes": False, "raison": "API météo indisponible"}

    t, h, p, v = (meteo["temperature"], meteo["humidite"],
                  meteo["precipitation"], meteo["vent"])
    log.info("🌡️  T=%.1f°C H=%.1f%% P=%.2fmm V=%.1fm/s", t, h, p, v)

    # 2. Prédiction risque
    mois_num = {1:0,2:0,3:0,4:0,5:0,6:0,7:1,8:2}.get(datetime.now().month, 1)
    risque, conf, probas = predire_risque(t, h, p, v, mois_num)
    log.info("%s Risque prédit : %s (confiance %.0f%%)",
             RISQUE_EMOJI.get(risque,"⚪"), risque, conf*100)

    # 3. Seuil d'alerte
    if risque not in cfg.niveaux_alerte:
        log.info("✅ Risque %s — pas d'alerte nécessaire", risque)
        return {"succes": True, "risque": risque, "alerte_envoyee": False}

    # 4. Cooldown (sauf si forcer=True)
    if not forcer and cooldown_actif(cfg):
        return {"succes": True, "risque": risque, "alerte_envoyee": False,
                "raison": "cooldown"}

    log.warning("🚨 ALERTE %s — envoi en cours…",
                "CRITIQUE" if risque == "Très élevé" else "HAUTE")

    resultats = {"risque": risque, "confiance": conf}

    # 5. Email
    if cfg.email_actif:
        sujet, txt, html = construire_email(risque, conf, meteo, probas, cfg)
        resultats["email"] = envoyer_email(cfg, sujet, txt, html)

    # 6. Webhook
    if cfg.webhook_actif and cfg.webhook_url:
        resultats["webhook"] = envoyer_webhook(cfg, risque, conf, meteo, probas)

    # 7. JSON
    if cfg.sauvegarder_json:
        resultats["json"] = sauvegarder_json(risque, conf, meteo, probas)

    # 8. Marquer cooldown
    ecrire_derniere_alerte(risque)

    resultats["alerte_envoyee"] = True
    return resultats

# ============================================================================
# ── Surveillance continue ─────────────────────────────────────────────────────
# ============================================================================
def surveillance_continue(cfg: Config):
    log.info("🔄 Surveillance continue démarrée")
    log.info("   Intervalle : %d min | Cooldown : %d min",
             cfg.intervalle_minutes, cfg.cooldown_minutes)
    log.info("   Niveaux d'alerte : %s", ", ".join(cfg.niveaux_alerte))
    if cfg.email_actif:
        log.info("   📧 Email → %s", ", ".join(cfg.destinataires))
    if cfg.webhook_actif:
        log.info("   🔗 Webhook (%s)", cfg.webhook_type)
    log.info("   Appuyez sur Ctrl+C pour arrêter\n")

    try:
        while True:
            try:
                verifier_et_alerter(cfg)
            except Exception as e:
                log.error("Erreur lors de la vérification : %s", e)

            prochaine = datetime.now() + timedelta(minutes=cfg.intervalle_minutes)
            log.info("⏰ Prochaine vérification : %s\n",
                     prochaine.strftime("%H:%M:%S"))
            time.sleep(cfg.intervalle_minutes * 60)

    except KeyboardInterrupt:
        log.info("\n🛑 Surveillance arrêtée par l'utilisateur.")

# ============================================================================
# ── Point d'entrée ────────────────────────────────────────────────────────────
# ============================================================================
def generer_config_exemple():
    """Génère un fichier config_alertes.json d'exemple."""
    exemple = {
        "email": {
            "actif":          True,
            "smtp_host":      "smtp.gmail.com",
            "smtp_port":      587,
            "smtp_user":      "votre.email@gmail.com",
            "smtp_password":  "mot_de_passe_application_google",
            "destinataires":  [
                "pompiers@agdez.ma",
                "commune@agdez.ma",
                "protection.civile@zagora.ma"
            ],
            "expediteur_nom": "Système Alerte Incendie Agdez"
        },
        "webhook": {
            "actif": False,
            "url":   "https://hooks.slack.com/services/XXX/YYY/ZZZ",
            "type":  "slack"
        },
        "options": {
            "cooldown_minutes":   60,
            "intervalle_minutes": 30,
            "sauvegarder_json":   True,
            "niveaux_alerte":     ["Élevé", "Très élevé"]
        }
    }
    path = Path("config_alertes.json")
    path.write_text(json.dumps(exemple, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"✅ Fichier créé : {path.resolve()}")
    print("   → Modifiez smtp_user, smtp_password et destinataires")
    print("   → Pour Gmail : utilisez un mot de passe d'application")
    print("     (myaccount.google.com → Sécurité → Mots de passe des applications)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Système d'Alerte Automatique — Risque Incendie Agdez"
    )
    parser.add_argument(
        "--test",    action="store_true",
        help="Envoyer une alerte de test immédiatement (ignore le cooldown)"
    )
    parser.add_argument(
        "--once",    action="store_true",
        help="Vérifier une seule fois et quitter"
    )
    parser.add_argument(
        "--config",  action="store_true",
        help="Générer un fichier config_alertes.json d'exemple"
    )
    parser.add_argument(
        "--cfg",     default="config_alertes.json",
        help="Chemin vers le fichier de configuration (défaut: config_alertes.json)"
    )
    args = parser.parse_args()

    if args.config:
        generer_config_exemple()
        sys.exit(0)

    cfg = Config(args.cfg)
    erreurs = cfg.valider()
    if erreurs and not args.test:
        log.error("❌ Configuration invalide : %s", " · ".join(erreurs))
        log.error("   Lancez : python systeme_alertes.py --config")
        sys.exit(1)

    if args.test:
        log.info("🧪 Mode TEST — envoi forcé d'une alerte")
        res = verifier_et_alerter(cfg, forcer=True)
        log.info("Résultat : %s", json.dumps(res, ensure_ascii=False, indent=2))
    elif args.once:
        res = verifier_et_alerter(cfg)
        log.info("Résultat : %s", json.dumps(res, ensure_ascii=False, indent=2))
    else:
        surveillance_continue(cfg)