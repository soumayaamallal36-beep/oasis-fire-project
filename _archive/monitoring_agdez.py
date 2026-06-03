# ============================================================================
# monitoring_agdez.py — Système de Monitoring & Alertes Automatiques
# Agdez Fire Risk System · Version 1.1 (corrigé)
# ============================================================================
# Lancement :
#   python monitoring_agdez.py                # surveillance continue
#   python monitoring_agdez.py --test         # test immédiat (1 cycle)
#   python monitoring_agdez.py --simulate     # simule risque "Très élevé"
# ============================================================================

import argparse
import json
import logging
import smtplib
import sys
import time
import traceback
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import numpy as np
import requests

try:
    import joblib
    ML_DISPO = True
except ImportError:
    ML_DISPO = False

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent
MDL      = BASE / "models" / "trained"
RPT      = BASE / "reports"
CONFIG   = BASE / "config_alertes.json"

# CRITIQUE : créer reports/ AVANT toute tentative de log fichier
RPT.mkdir(parents=True, exist_ok=True)

LOG_FILE = RPT / "monitoring_log.jsonl"

# ── Constantes Agdez ─────────────────────────────────────────────────────────
LAT, LON   = 30.69, -6.45
ALTITUDE   = 1169.3
PENTE      = 5.73
EXPOSITION = 165.51

RISQUE_EMOJI = {
    "Faible": "🟢", "Moyen": "🟡", "Élevé": "🟠", "Très élevé": "🔴",
}
RISQUE_COLOR = {
    "Faible":     "#27ae60",
    "Moyen":      "#e67e22",
    "Élevé":      "#e74c3c",
    "Très élevé": "#8e1a1a",
}
NIVEAUX_ALERTE = {"Élevé", "Très élevé"}

FEAT_ORDER = [
    "temperature", "humidite", "precipitation", "vent",
    "pente", "altitude", "exposition", "ndvi_avant",
    "indice_secheresse", "indice_propagation", "stress_vegetal",
    "exposition_sud", "mois_num",
]

# ── Logging (après création du dossier) ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(RPT / "monitoring.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("MonitoringAgdez")


# ============================================================================
# ── Configuration ─────────────────────────────────────────────────────────────
# ============================================================================

class Config:
    """Charge config_alertes.json et expose tous les paramètres."""

    def __init__(self):
        self.email_actif        = False
        self.smtp_host          = "smtp.gmail.com"
        self.smtp_port          = 587
        self.smtp_user          = ""
        self.smtp_password      = ""
        self.destinataires      = []
        self.expediteur_nom     = "Système Alerte Incendie Agdez"
        self.cooldown_minutes   = 60
        self.intervalle_minutes = 30
        self.sauvegarder_json   = True
        self.niveaux_alerte     = ["Élevé", "Très élevé"]
        self._charger()

    def _charger(self):
        if not CONFIG.exists():
            logger.warning(f"⚠️  {CONFIG} introuvable — valeurs par défaut utilisées")
            return
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

            em = cfg.get("email", {})
            self.email_actif    = em.get("actif", False)
            self.smtp_host      = em.get("smtp_host", "smtp.gmail.com")
            self.smtp_port      = em.get("smtp_port", 587)
            self.smtp_user      = em.get("smtp_user", "")
            self.smtp_password  = em.get("smtp_password", "")
            self.destinataires  = em.get("destinataires", [])
            self.expediteur_nom = em.get("expediteur_nom", self.expediteur_nom)

            opt = cfg.get("options", {})
            self.cooldown_minutes   = opt.get("cooldown_minutes",   60)
            self.intervalle_minutes = opt.get("intervalle_minutes", 30)
            self.sauvegarder_json   = opt.get("sauvegarder_json",   True)
            self.niveaux_alerte     = opt.get("niveaux_alerte", ["Élevé", "Très élevé"])

            logger.info(f"✅ Configuration chargée depuis {CONFIG}")
        except Exception as e:
            logger.error(f"❌ Erreur lecture config : {e}")

    def valider(self) -> list:
        err = []
        if self.email_actif:
            if not self.smtp_user:     err.append("smtp_user vide")
            if not self.smtp_password: err.append("smtp_password vide")
            if not self.destinataires: err.append("destinataires vide")
        return err

    def afficher(self):
        sep = "=" * 56
        print(f"\n{sep}")
        print("  ⚙️  CONFIGURATION MONITORING — Agdez Fire Risk")
        print(sep)
        print(f"  📧 Email actif       : {'✅ OUI' if self.email_actif else '❌ NON'}")
        if self.email_actif:
            print(f"  📤 Expéditeur        : {self.smtp_user}")
            for d in self.destinataires:
                print(f"  📬 Destinataire      : {d}")
        print(f"  ⏱️  Intervalle        : toutes les {self.intervalle_minutes} min")
        print(f"  🔕 Cooldown          : {self.cooldown_minutes} min entre 2 alertes")
        print(f"  🚨 Niveaux alertés   : {', '.join(self.niveaux_alerte)}")
        erreurs = self.valider()
        if erreurs:
            print(f"  ⚠️  Erreurs config   : {', '.join(erreurs)}")
        else:
            print("  ✅ Configuration valide")
        print(f"{sep}\n")


# ============================================================================
# ── Météo temps réel ──────────────────────────────────────────────────────────
# ============================================================================

def fetch_meteo() -> dict | None:
    """Récupère les conditions météo actuelles via Open-Meteo (gratuit)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        "&wind_speed_unit=ms&timezone=Africa%2FCasablanca"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        c = r.json()["current"]
        return {
            "temperature":   round(c["temperature_2m"], 1),
            "humidite":      round(c["relative_humidity_2m"], 1),
            "precipitation": round(c["precipitation"], 2),
            "vent":          round(c["wind_speed_10m"], 1),
        }
    except requests.exceptions.Timeout:
        logger.warning("⏳ Timeout API météo")
    except requests.exceptions.ConnectionError:
        logger.warning("🌐 Connexion impossible — API météo")
    except Exception as e:
        logger.warning(f"⚠️  API météo : {e}")
    return None


# ============================================================================
# ── Prédiction risque ────────────────────────────────────────────────────────
# ============================================================================

def predire_ml(model, le, t, h, p, v) -> tuple:
    """Prédiction via Random Forest."""
    try:
        import pandas as pd
        mois_num = datetime.now().month
        ndvi = 0.144
        row = {
            "temperature":          t,
            "humidite":             h,
            "precipitation":        p,
            "vent":                 v,
            "pente":                PENTE,
            "altitude":             ALTITUDE,
            "exposition":           EXPOSITION,
            "ndvi_avant":           ndvi,
            "indice_secheresse":    (t - h) / (p + 0.1),
            "indice_propagation":   v * float(np.sin(np.radians(PENTE))),
            "stress_vegetal":       (1 - ndvi) * t / 10,
            "exposition_sud":       float(np.cos(np.radians(EXPOSITION - 180))),
            "mois_num":             mois_num,
        }
        X = pd.DataFrame([[row[f] for f in FEAT_ORDER]], columns=FEAT_ORDER)
        y      = model.predict(X)[0]
        probas = model.predict_proba(X)[0]
        label  = le.inverse_transform([y])[0]
        return label, float(probas.max()), {c: float(pb) for c, pb in zip(le.classes_, probas)}
    except Exception as e:
        logger.error(f"❌ Prédiction ML : {e}")
        return None, 0.0, {}


def predire_heuristique(t: float, h: float, p: float, v: float) -> tuple:
    """Règles terrain — utilisées si le modèle ML est absent."""
    score = 0
    if t >= 35:      score += 3
    elif t >= 30:    score += 2
    elif t >= 25:    score += 1
    if h <= 10:      score += 3
    elif h <= 20:    score += 2
    elif h <= 30:    score += 1
    if p == 0:       score += 2
    elif p < 5:      score += 1
    if v >= 6:       score += 2
    elif v >= 4:     score += 1

    if score >= 8:   label, conf = "Très élevé", 0.80
    elif score >= 5: label, conf = "Élevé",      0.70
    elif score >= 3: label, conf = "Moyen",      0.65
    else:            label, conf = "Faible",     0.75

    base = {"Faible": 0.05, "Moyen": 0.10, "Élevé": 0.15, "Très élevé": 0.05}
    base[label] = conf
    total = sum(base.values())
    probas = {k: round(v / total, 4) for k, v in base.items()}
    return label, conf, probas


RECO = {
    "Faible":     "✅ Surveillance standard. Conditions favorables.",
    "Moyen":      "⚠️  Vigilance modérée. Vérifier les équipements.",
    "Élevé":      "🟠 Patrouilles terrain actives. Alerter les équipes.",
    "Très élevé": "🔴 DANGER EXTRÊME — Activer plan ORSEC immédiatement. "
                  "Interdire l'accès aux zones boisées. Pré-positionner les moyens.",
}


# ============================================================================
# ── Email HTML ────────────────────────────────────────────────────────────────
# ============================================================================

def _html_email(risque, confiance, t, h, p, v, probas, reco, ts) -> str:
    couleur = RISQUE_COLOR.get(risque, "#888")
    emoji   = RISQUE_EMOJI.get(risque, "⚠️")
    prio    = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
    ts_str  = ts.strftime("%d/%m/%Y à %H:%M:%S")

    barres = ""
    for k, val in probas.items():
        bc = RISQUE_COLOR.get(k, "#888")
        barres += f"""
        <tr>
          <td style="padding:6px 12px;font-size:13px;color:#555;width:120px">{k}</td>
          <td style="padding:6px 12px">
            <div style="background:#f0f0f0;border-radius:4px;height:14px;
                        width:160px;display:inline-block;vertical-align:middle">
              <div style="background:{bc};width:{val*100:.0f}%;height:14px;border-radius:4px"></div>
            </div>
            <span style="margin-left:8px;font-size:13px;font-weight:600">{val:.0%}</span>
          </td>
        </tr>"""

    badge_bg = "#fee2e2" if prio == "CRITIQUE" else "#ffedd5"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="background:#fff;border-radius:12px;max-width:620px;margin:auto;
            overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.15)">
  <div style="background:{couleur};padding:28px 32px;color:#fff">
    <div style="font-size:42px;margin-bottom:8px">{emoji}</div>
    <h1 style="margin:0;font-size:22px">ALERTE {prio} — Risque Incendie {risque}</h1>
    <p style="margin:8px 0 0;opacity:.85;font-size:13px">
      📍 Agdez, Drâa-Tafilalet, Maroc &nbsp;·&nbsp; 🕐 {ts_str}
    </p>
  </div>
  <div style="padding:28px 32px">
    <div style="display:inline-block;background:{badge_bg};color:{couleur};
                border-radius:20px;padding:5px 16px;font-size:12px;
                font-weight:700;margin-bottom:20px">
      ⚡ {prio} &nbsp;·&nbsp; Confiance {confiance:.0%}
    </div>
    <p style="margin:0 0 10px;font-weight:700;font-size:14px;color:#222">
      📡 Conditions météo temps réel
    </p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      <tr style="background:#f9f9f9">
        <td style="padding:9px 12px;color:#555;font-size:13px;width:45%">🌡️ Température</td>
        <td style="padding:9px 12px;font-weight:700;font-size:13px">{t}°C</td>
      </tr>
      <tr>
        <td style="padding:9px 12px;color:#555;font-size:13px">💧 Humidité relative</td>
        <td style="padding:9px 12px;font-weight:700;font-size:13px">{h}%</td>
      </tr>
      <tr style="background:#f9f9f9">
        <td style="padding:9px 12px;color:#555;font-size:13px">🌧️ Précipitations</td>
        <td style="padding:9px 12px;font-weight:700;font-size:13px">{p} mm</td>
      </tr>
      <tr>
        <td style="padding:9px 12px;color:#555;font-size:13px">💨 Vitesse du vent</td>
        <td style="padding:9px 12px;font-weight:700;font-size:13px">{v} m/s</td>
      </tr>
    </table>
    <p style="margin:0 0 10px;font-weight:700;font-size:14px;color:#222">
      🤖 Probabilités — Modèle Random Forest
    </p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      {barres}
    </table>
    <div style="background:#fff8e6;border-left:5px solid #f59e0b;
                border-radius:0 10px 10px 0;padding:14px 18px;
                font-size:13px;color:#7c5310;line-height:1.7">
      <strong>📋 Recommandation opérationnelle :</strong><br>{reco}
    </div>
    <div style="margin-top:18px;padding:12px;background:#f0f4ff;
                border-radius:8px;font-size:11px;color:#445;text-align:center">
      🗺️ Zone : Agdez (30.69°N, 6.45°W) · Alt. 1 169 m · Commune Agdez, Province de Zagora 🇲🇦
    </div>
  </div>
  <div style="background:#f9f9f9;padding:14px 32px;font-size:11px;
              color:#aaa;text-align:center;border-top:1px solid #eee">
    Système Automatique de Monitoring · Agdez Fire Risk v1.1 ·
    Random Forest · Open-Meteo · Ne pas répondre à cet email.
  </div>
</div>
</body></html>"""


def _texte_email(risque, confiance, t, h, p, v, probas, reco, ts) -> str:
    prio     = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
    prob_txt = "\n".join([f"  {k:14s}: {vv:.0%}" for k, vv in probas.items()])
    return f"""
⚡ ALERTE {prio} — RISQUE INCENDIE {risque.upper()}
{'='*55}
📍 Zone        : Agdez, Drâa-Tafilalet, Maroc
🕐 Timestamp   : {ts.strftime('%d/%m/%Y à %H:%M:%S')}
🔥 Risque      : {risque}
📊 Confiance   : {confiance:.0%}

CONDITIONS MÉTÉO (temps réel — Open-Meteo)
  🌡️  Température    : {t}°C
  💧  Humidité       : {h}%
  🌧️  Précipitations : {p} mm
  💨  Vent           : {v} m/s

PROBABILITÉS — Random Forest
{prob_txt}

RECOMMANDATION
  {reco}

{'─'*55}
Système Automatique Agdez Fire Risk v1.1 · Ne pas répondre.
""".strip()


def envoyer_email(cfg: Config, risque, confiance, t, h, p, v,
                  probas, reco, ts) -> dict:
    prio = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
    msg  = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"🔥 ALERTE {prio} — Risque Incendie {risque} "
        f"· Agdez · {ts.strftime('%d/%m/%Y %H:%M')}"
    )
    msg["From"] = f"{cfg.expediteur_nom} <{cfg.smtp_user}>"
    msg["To"]   = ", ".join(cfg.destinataires)
    msg.attach(MIMEText(_texte_email(risque, confiance, t, h, p, v, probas, reco, ts), "plain", "utf-8"))
    msg.attach(MIMEText(_html_email(risque, confiance, t, h, p, v, probas, reco, ts),  "html",  "utf-8"))

    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as srv:
            srv.ehlo()                                   # 1. identification
            srv.starttls()                               # 2. chiffrement TLS
            srv.ehlo()                                   # 3. ré-identification après TLS (obligatoire Gmail)
            srv.login(cfg.smtp_user, cfg.smtp_password)  # 4. authentification
            srv.sendmail(cfg.smtp_user, cfg.destinataires, msg.as_string())  # 5. envoi
        logger.info(f"✅ Email envoyé → {cfg.destinataires}")
        return {"succes": True, "destinataires": cfg.destinataires}
    except smtplib.SMTPAuthenticationError:
        err = "Authentification échouée — utilisez un mot de passe d'application Gmail (16 caractères)"
        logger.error(f"❌ {err}")
        return {"succes": False, "erreur": err}
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP : {e}")
        return {"succes": False, "erreur": str(e)}
    except OSError as e:
        logger.error(f"❌ Connexion réseau : {e}")
        return {"succes": False, "erreur": f"Connexion impossible : {e}"}
    except Exception as e:
        logger.error(f"❌ Email : {e}")
        return {"succes": False, "erreur": str(e)}


# ============================================================================
# ── Journal ───────────────────────────────────────────────────────────────────
# ============================================================================

def log_jsonl(entree: dict):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"⚠️  Log JSONL : {e}")


def sauvegarder_alerte(risque, confiance, t, h, p, v, probas, reco, ts, envoi):
    try:
        nom    = f"alerte_{ts.strftime('%Y%m%d_%H%M%S')}_{risque.replace(' ','_')}.json"
        chemin = RPT / nom
        data   = {
            "timestamp":      ts.isoformat(),
            "risque":         risque,
            "priorite":       "CRITIQUE" if risque == "Très élevé" else "HAUTE",
            "confiance":      round(confiance, 4),
            "zone":           "Agdez, Drâa-Tafilalet, Maroc",
            "conditions":     {"temperature": t, "humidite": h,
                               "precipitation": p, "vent": v},
            "probabilites":   probas,
            "recommandation": reco,
            "envoi":          envoi,
        }
        chemin.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"💾 Alerte archivée : {chemin.name}")
        return str(chemin)
    except Exception as e:
        logger.warning(f"⚠️  Sauvegarde JSON : {e}")
        return None


# ============================================================================
# ── Moteur de monitoring ──────────────────────────────────────────────────────
# ============================================================================

class MonitoringAgdez:

    def __init__(self, cfg: Config, model=None, le=None):
        self.cfg       = cfg
        self.model     = model
        self.le        = le
        self._cooldown : dict[str, datetime] = {}
        self.stats     = {"cycles": 0, "alertes": 0,
                          "emails_ok": 0, "emails_err": 0, "api_err": 0}

    def _en_cooldown(self, risque: str) -> bool:
        derniere = self._cooldown.get(risque)
        if not derniere:
            return False
        return (datetime.now() - derniere) < timedelta(minutes=self.cfg.cooldown_minutes)

    def _mins_restant(self, risque: str) -> int:
        derniere = self._cooldown.get(risque)
        if not derniere:
            return 0
        delta = timedelta(minutes=self.cfg.cooldown_minutes) - (datetime.now() - derniere)
        return max(0, int(delta.total_seconds() / 60))

    # ── Cycle principal ───────────────────────────────────────────────────────

    def executer_cycle(self, simuler: bool = False) -> dict:
        self.stats["cycles"] += 1
        ts = datetime.now()
        rapport = {
            "timestamp": ts.isoformat(),
            "cycle":     self.stats["cycles"],
            "meteo":     None,
            "risque":    None,
            "alerte":    False,
            "envoi":     None,
            "erreur":    None,
        }

        # 1. Météo
        if simuler:
            meteo = {"temperature": 38.0, "humidite": 8.0,
                     "precipitation": 0.0, "vent": 6.5}
            logger.info("🔬 SIMULATION — conditions extrêmes injectées")
        else:
            meteo = fetch_meteo()

        if not meteo:
            self.stats["api_err"] += 1
            rapport["erreur"] = "API météo indisponible"
            log_jsonl(rapport)
            return rapport

        t, h, p, v = (meteo["temperature"], meteo["humidite"],
                      meteo["precipitation"], meteo["vent"])
        rapport["meteo"] = {"temperature": t, "humidite": h,
                            "precipitation": p, "vent": v}
        logger.info(f"🌡️  Météo → T={t}°C | H={h}% | P={p}mm | V={v}m/s")

        # 2. Prédiction
        if self.model and self.le:
            risque, confiance, probas = predire_ml(self.model, self.le, t, h, p, v)
            methode = "Random Forest ML"
        else:
            risque, confiance, probas = predire_heuristique(t, h, p, v)
            methode = "Heuristique (ML absent)"

        if not risque:
            rapport["erreur"] = "Prédiction échouée"
            log_jsonl(rapport)
            return rapport

        rapport["risque"]    = risque
        rapport["confiance"] = round(confiance, 4)
        rapport["methode"]   = methode
        emoji = RISQUE_EMOJI.get(risque, "⚠️")
        logger.info(f"{emoji} Risque : {risque} ({confiance:.0%}) — {methode}")

        # 3. Alerte nécessaire ?
        if risque not in self.cfg.niveaux_alerte:
            logger.info(f"✅ Risque {risque} → aucune alerte")
            log_jsonl(rapport)
            return rapport

        if self._en_cooldown(risque):
            mins = self._mins_restant(risque)
            logger.info(f"⏳ Cooldown {risque} — {mins} min restantes")
            rapport["cooldown_restant"] = mins
            log_jsonl(rapport)
            return rapport

        # 4. Envoi
        self.stats["alertes"] += 1
        rapport["alerte"] = True
        reco  = RECO.get(risque, "")
        prio  = "CRITIQUE" if risque == "Très élevé" else "HAUTE"
        logger.warning(f"🚨 ALERTE {prio} — {risque} | T={t} H={h} P={p} V={v}")

        envoi = {}
        errs  = self.cfg.valider()

        if self.cfg.email_actif and not errs:
            res = envoyer_email(self.cfg, risque, confiance, t, h, p, v, probas, reco, ts)
            envoi["email"] = res
            if res.get("succes"):
                self.stats["emails_ok"] += 1
            else:
                self.stats["emails_err"] += 1
        elif not self.cfg.email_actif:
            logger.info("📧 Email désactivé dans la config")
            envoi["email"] = {"info": "désactivé"}
        else:
            logger.warning(f"⚠️  Config email invalide : {errs}")
            envoi["email"] = {"succes": False, "erreur": str(errs)}

        self._cooldown[risque] = ts
        rapport["envoi"] = envoi

        if self.cfg.sauvegarder_json:
            rapport["fichier"] = sauvegarder_alerte(
                risque, confiance, t, h, p, v, probas, reco, ts, envoi
            )

        log_jsonl(rapport)
        return rapport

    # ── Affichage ─────────────────────────────────────────────────────────────

    def afficher_rapport(self, r: dict):
        risque = r.get("risque", "—")
        conf   = r.get("confiance", 0) or 0
        meteo  = r.get("meteo") or {}
        emoji  = RISQUE_EMOJI.get(risque, "⚪")

        print(f"\n  {emoji} Risque : {risque}  ({conf:.0%} confiance)")
        if meteo:
            print(f"     🌡️  {meteo.get('temperature','?')}°C  "
                  f"💧 {meteo.get('humidite','?')}%  "
                  f"🌧️  {meteo.get('precipitation','?')}mm  "
                  f"💨 {meteo.get('vent','?')}m/s")

        if r.get("erreur"):
            print(f"  ⚠️  Erreur : {r['erreur']}")
        elif r.get("alerte"):
            em = (r.get("envoi") or {}).get("email", {})
            if em.get("succes"):
                print(f"  ✅ Email envoyé → {em['destinataires']}")
            elif "info" in em:
                print(f"  📧 Email {em['info']}")
            else:
                print(f"  ❌ Email échoué : {em.get('erreur','?')}")
            if r.get("fichier"):
                print(f"  💾 Archivé : {Path(r['fichier']).name}")
        elif r.get("cooldown_restant"):
            print(f"  ⏳ Cooldown — {r['cooldown_restant']} min restantes")
        else:
            print("  ✅ Aucune alerte requise")

        print(f"\n  📊 Cycles:{self.stats['cycles']}  "
              f"Alertes:{self.stats['alertes']}  "
              f"Emails OK:{self.stats['emails_ok']}  "
              f"Emails ERR:{self.stats['emails_err']}")

    def _bilan(self):
        sep = "=" * 46
        print(f"\n{sep}\n  📊 BILAN FINAL\n{sep}")
        for k, v in self.stats.items():
            print(f"  {k:20s}: {v}")
        print(sep)

    # ── Boucle principale ─────────────────────────────────────────────────────

    def surveiller(self, simuler_premier: bool = False):
        intervalle = self.cfg.intervalle_minutes * 60
        logger.info(
            f"🔍 Surveillance démarrée "
            f"(cycle toutes les {self.cfg.intervalle_minutes} min)"
        )
        simuler = simuler_premier
        try:
            while True:
                sep = "─" * 56
                print(f"\n{sep}")
                print(f"  🔄 CYCLE #{self.stats['cycles']+1} — "
                      f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                print(sep)

                rapport = self.executer_cycle(simuler=simuler)
                self.afficher_rapport(rapport)
                simuler = False

                prochaine = datetime.now() + timedelta(minutes=self.cfg.intervalle_minutes)
                print(f"\n  ⏰ Prochain cycle : {prochaine.strftime('%H:%M:%S')}")
                time.sleep(intervalle)

        except KeyboardInterrupt:
            print("\n\n⛔ Surveillance arrêtée (Ctrl+C).")
            self._bilan()


# ============================================================================
# ── Point d'entrée ────────────────────────────────────────────────────────────
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Monitoring incendie automatique — Agdez, Maroc 🇲🇦"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="1 seul cycle avec météo temps réel, puis quitte"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simule conditions extrêmes (Très élevé) pour tester l'email"
    )
    args = parser.parse_args()

    # Bannière
    print("\n" + "🔥 " * 14)
    print("  SYSTÈME DE MONITORING INCENDIE — AGDEZ, MAROC 🇲🇦")
    print("  Version 1.1 — Surveillance automatique + Alertes email")
    print("🔥 " * 14)

    # Config
    cfg = Config()
    cfg.afficher()

    # Modèle ML
    model, le = None, None
    if ML_DISPO:
        mp = MDL / "model_risque_incendie.pkl"
        lp = MDL / "label_encoder.pkl"
        if mp.exists() and lp.exists():
            try:
                model = joblib.load(mp)
                le    = joblib.load(lp)
                logger.info("✅ Modèle Random Forest chargé")
            except Exception as e:
                logger.warning(f"⚠️  Modèle non chargé : {e} — mode heuristique")
        else:
            logger.info("ℹ️  Modèle ML absent — mode heuristique activé")
    else:
        logger.info("ℹ️  joblib absent — mode heuristique activé")

    monitoring = MonitoringAgdez(cfg, model=model, le=le)

    if args.test or args.simulate:
        print(f"\n{'─'*56}")
        print(f"  🔄 CYCLE UNIQUE — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'─'*56}")
        rapport = monitoring.executer_cycle(simuler=args.simulate)
        monitoring.afficher_rapport(rapport)
        print("\n✅ Terminé.\n")
    else:
        monitoring.surveiller(simuler_premier=False)


if __name__ == "__main__":
    main()