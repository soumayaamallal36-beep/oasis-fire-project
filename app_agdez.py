# ============================================================================
# app_agdez.py — Dashboard Prédiction Risque Incendie · Agdez, Maroc
# Version 3.0 — 100% dynamique · API météo temps réel · Données exactes
# ============================================================================
# streamlit run app_agdez.py
#
# Structure attendue :
#   models/trained/  → model_risque_incendie.pkl, label_encoder.pkl
#   models/metadata/ → feature_importance.csv, predictions_scenarios_2026.csv,
#                      projections_climatiques.csv, model_info.json
#   data/csv/climat/ → climat_statistiques_annuelles.csv,
#                      climat_conditions_ete_2025.csv, ...
#   data/csv/incendie/ → indices_stats.xlsx, severity_classes.xlsx,
#                        summary_complete.xlsx
#   reports/         → alerte_*.json (archive), rapport_prediction.txt
# ============================================================================

import glob
import json
import smtplib
import traceback
import warnings
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import folium
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
from streamlit_folium import st_folium

warnings.filterwarnings("ignore")

# ── Chemins ──────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent
MDL      = BASE / "models" / "trained"
META     = BASE / "models" / "metadata"
CSV      = BASE / "data" / "csv" / "climat"
INCENDIE = BASE / "data" / "csv" / "incendie"
RPT      = BASE / "reports"

# ── Constantes Agdez ─────────────────────────────────────────────────────────
LAT, LON   = 30.69, -6.45
ALTITUDE   = 1169.3
PENTE      = 5.73
EXPOSITION = 165.51
MOIS_MAP   = {"Juin": 0, "Juillet": 1, "Août": 2}

# Données historiques réelles 2017–2025 (source : climat_statistiques_annuelles.csv)
HIST = {
    2017: dict(temperature=20.43, humidite=31.5, precipitation=42.3, vent=4.50),
    2018: dict(temperature=19.16, humidite=34.2, precipitation=109.0,vent=4.67),
    2019: dict(temperature=20.34, humidite=30.8, precipitation=67.0, vent=4.67),
    2020: dict(temperature=20.46, humidite=31.9, precipitation=133.0,vent=4.89),
    2021: dict(temperature=20.50, humidite=30.1, precipitation=48.0, vent=4.50),
    2022: dict(temperature=20.76, humidite=31.2, precipitation=50.0, vent=4.33),
    2023: dict(temperature=21.07, humidite=29.4, precipitation=11.0, vent=4.33),
    2024: dict(temperature=21.23, humidite=30.5, precipitation=10.0, vent=4.83),
    2025: dict(temperature=20.25, humidite=30.0, precipitation=57.0, vent=4.50),
}

# Données été réelles 2025 (juillet = mois le plus critique)
ETE_2025 = {
    "Juin":    dict(temperature=29.30, humidite=20.18, precipitation=2.85,  vent=4.50),
    "Juillet": dict(temperature=32.69, humidite=16.42, precipitation=26.43, vent=4.01),
    "Août":    dict(temperature=31.40, humidite=19.86, precipitation=0.18,  vent=3.81),
}

# Risques réels observés (basés sur conditions terrain)
RISQUES_REELS = {
    2017: "Moyen", 2018: "Faible", 2019: "Moyen", 2020: "Moyen",
    2021: "Élevé", 2022: "Élevé", 2023: "Élevé", 2024: "Élevé", 2025: "Très élevé",
}

RISQUE_COLOR = {
    "Faible": "#27ae60", "Moyen": "#e67e22",
    "Élevé":  "#e74c3c", "Très élevé": "#8e1a1a",
}
RISQUE_EMOJI = {
    "Faible": "🟢", "Moyen": "🟡", "Élevé": "🟠", "Très élevé": "🔴",
}

# ============================================================================
# ── Configuration Streamlit ──────────────────────────────────────────────────
# ============================================================================
st.set_page_config(
    page_title="Agdez · Risque Incendie",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"]{
    font-family:'Inter',sans-serif;
    background:#f4f7fb;
    color:#1e293b;
}

/* HEADER */
.app-hdr{
    background:linear-gradient(135deg,#ffffff,#eef4ff);
    border-radius:18px;
    padding:24px 32px;
    margin-bottom:22px;
    border:1px solid #dbeafe;
    box-shadow:0 4px 18px rgba(0,0,0,0.05);
}

.app-hdr h1{
    color:#0f172a;
    font-size:2rem;
    font-weight:700;
    margin:0;
    letter-spacing:-1px;
}

.app-hdr p{
    color:#0f172a;
    font-size:0.88rem;
    margin-top:6px;
}

/* KPI CARDS */
.kpi{
    background:white;
    border-radius:16px;
    padding:22px;
    min-height:140px;
    overflow:visible;
    word-break:break-word;
    border:1px solid #e2e8f0;
    text-align:center;
    height:100%;
    box-shadow:0 2px 10px rgba(0,0,0,0.04);
    transition:0.3s;
}

.kpi:hover{
    transform:translateY(-2px);
}

.kpi .v{
    font-size:1.7rem;
    font-weight:700;
    line-height:1.2;
}

.kpi .l{
    font-size:0.76rem;
    color:#0f172a;
    margin-top:6px;
}

/* SECTION TITLES */
.sec{
    font-size:0.78rem;
    color:#475569;
    text-transform:uppercase;
    letter-spacing:1.5px;
    margin-bottom:14px;
    padding-bottom:8px;
    border-bottom:2px solid #e2e8f0;
    font-weight:600;
}

/* INFO BOX */
.ibox{
    background:white;
    border-radius:14px;
    padding:14px;
    border:1px solid #e2e8f0;
    margin-bottom:10px;
    box-shadow:0 2px 8px rgba(0,0,0,0.03);
}

/* ALERTS */
.alert-r{
    background:#ffffff;
    border:1px solid #fecdd3;
    border-left:5px solid #ef4444;
    border-radius:12px;
    padding:16px 20px;
    margin-bottom:12px;
}

.alert-o{
    background:#fff7ed;
    border:1px solid #fed7aa;
    border-left:5px solid #f97316;
    border-radius:12px;
    padding:16px 20px;
    margin-bottom:12px;
}

/* TAGS */
.tag{
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    font-size:0.7rem;
    font-weight:600;
    margin-bottom:6px;
}

.tag-r{
    background:#fee2e2;
    color:#dc2626;
}

.tag-o{
    background:#ffedd5;
    color:#ea580c;
}

/* SIDEBAR */
[data-testid="stSidebar"]{
    background:#ffffff;
    border-right:1px solid #e2e8f0;
}

/* TABS */
.stTabs [data-baseweb="tab"]{
    font-family:'Inter',sans-serif;
    font-weight:600;
    font-size:0.85rem;
    color:#475569;
}

.stTabs [data-baseweb="tab-list"]{
    background:white;
    border-bottom:1px solid #e2e8f0;
    border-radius:12px;
    padding:4px;
}

/* METRICS */
[data-testid="stMetric"]{
    background:white;
    border-radius:14px;
    padding:12px;
    border:1px solid #e2e8f0;
    box-shadow:0 2px 8px rgba(0,0,0,0.03);
}

[data-testid="stMetricValue"]{
    font-weight:700;
    color:#0f172a;
}

/* DATAFRAMES */
[data-testid="stDataFrame"]{
    border-radius:14px;
    overflow:hidden;
    border:1px solid #e2e8f0;
}

/* BUTTONS */
.stButton button{
    border-radius:12px;
    border:none;
    background:#2563eb;
    color:white;
    font-weight:600;
    padding:0.5rem 1rem;
}

.stButton button:hover{
    background:#1d4ed8;
}

/* PLOTS */
.js-plotly-plot{
    border-radius:16px;
    overflow:hidden;
}

/* GENERAL */
h1,h2,h3,h4{
    color:#0f172a;
}

p,span,label{
    color:#475569;
}
</style>
""", unsafe_allow_html=True)
# ============================================================================
# ── Système d'Alertes ────────────────────────────────────────────────────────
# ============================================================================

NIVEAUX_ALERTE = {"Élevé", "Très élevé"}

class ConfigAlertes:
    """Charge la configuration email/webhook depuis config_alertes.json"""
    def __init__(self):
        self.email_actif         = False
        self.smtp_host           = "smtp.gmail.com"
        self.smtp_port           = 587
        self.smtp_user           = ""
        self.smtp_password       = ""
        self.destinataires       = []
        self.expediteur_nom      = "Système Alerte Incendie Agdez"
        self.webhook_actif       = False
        self.webhook_url         = ""
        self.webhook_type        = "slack"
        self.cooldown_minutes    = 60
        self.sauvegarder_json    = True
        self.repertoire_rapports = RPT
        self._charger()

    def _charger(self):
        path = BASE / "config_alertes.json"
        if not path.exists():
            return
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
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
            self.webhook_type   = wh.get("type", "slack")
            opt = cfg.get("options", {})
            self.cooldown_minutes = opt.get("cooldown_minutes", 60)
            self.sauvegarder_json = opt.get("sauvegarder_json", True)
        except Exception:
            pass

    def erreurs(self):
        e = []
        if self.email_actif:
            if not self.smtp_user:     e.append("smtp_user vide")
            if not self.smtp_password: e.append("smtp_password vide")
            if not self.destinataires: e.append("destinataires vide")
        if self.webhook_actif and not self.webhook_url:
            e.append("webhook_url vide")
        return e


def _envoyer_email(cfg: ConfigAlertes, payload: dict) -> dict:
    """Envoie un email HTML via SMTP."""
    risque   = payload["risque"]
    prio     = payload["priorite"]
    mois     = payload["mois"]
    annee    = payload["annee"]
    conf     = payload["confiance"]
    cond     = payload["conditions"]
    probas   = payload["probabilites"]
    reco     = payload["recommandation"]
    couleur  = RISQUE_COLOR.get(risque, "#888")
    emoji    = RISQUE_EMOJI.get(risque, "⚠️")
    ts       = payload["timestamp"]

    # Corps texte brut
    prob_txt = "\n".join([f"  {k}: {v:.0%}" for k, v in probas.items()])
    corps_txt = f"""
⚡ ALERTE {prio} — RISQUE INCENDIE {risque.upper()}
{'='*55}
📍 Zone      : Agdez, Drâa-Tafilalet, Maroc
📅 Période   : {mois} {annee}
📊 Confiance : {conf:.0%}
🕐 Généré le : {ts}

CONDITIONS MÉTÉO
  🌡️ Température    : {cond['temperature']}°C
  💧 Humidité       : {cond['humidite']}%
  🌧️ Précipitations : {cond['precipitation']} mm
  💨 Vent           : {cond['vent']} m/s

PROBABILITÉS
{prob_txt}

RECOMMANDATION
  {reco}
""".strip()

    # Corps HTML
    prob_html = "".join([
        f'<tr><td style="padding:6px 12px;color:#555">{k}</td>'
        f'<td style="padding:6px 12px"><div style="background:#eee;border-radius:4px;height:14px;width:150px;display:inline-block;vertical-align:middle">'
        f'<div style="background:{RISQUE_COLOR.get(k,"#888")};width:{v*100:.0f}%;height:14px;border-radius:4px"></div></div>'
        f'<span style="margin-left:8px;font-weight:600">{v:.0%}</span></td></tr>'
        for k, v in probas.items()
    ])
    corps_html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
<div style="background:#fff;border-radius:12px;max-width:600px;margin:auto;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.12)">
  <div style="background:{couleur};padding:24px 28px;color:#fff">
    <div style="font-size:32px">{emoji}</div>
    <h1 style="margin:8px 0 0;font-size:20px">ALERTE {prio} — Risque {risque}</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:13px">Agdez, Maroc · {mois} {annee} · {ts}</p>
  </div>
  <div style="padding:24px 28px">
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:8px 12px;color:#555;width:140px">🌡️ Température</td><td style="padding:8px 12px;font-weight:600">{cond['temperature']}°C</td></tr>
      <tr><td style="padding:8px 12px;color:#555">💧 Humidité</td><td style="padding:8px 12px;font-weight:600">{cond['humidite']}%</td></tr>
      <tr><td style="padding:8px 12px;color:#555">🌧️ Précipitations</td><td style="padding:8px 12px;font-weight:600">{cond['precipitation']} mm</td></tr>
      <tr><td style="padding:8px 12px;color:#555">💨 Vent</td><td style="padding:8px 12px;font-weight:600">{cond['vent']} m/s</td></tr>
    </table>
    <p style="margin:20px 0 8px;font-weight:700;color:#333">Probabilités — Random Forest</p>
    <table style="width:100%;border-collapse:collapse">{prob_html}</table>
    <div style="background:#fff8e6;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;padding:12px 16px;margin-top:20px;font-size:13px;color:#7c5310">
      <strong>📋 Recommandation :</strong><br>{reco}
    </div>
  </div>
  <div style="background:#f9f9f9;padding:14px 28px;font-size:11px;color:#aaa;text-align:center;border-top:1px solid #eee">
    Système Automatique · Agdez 🇲🇦 · Random Forest v1.0.0 · Ne pas répondre.
  </div>
</div></body></html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔥 ALERTE {prio} — Risque Incendie {risque} · {mois} {annee} · Agdez"
        msg["From"]    = f"{cfg.expediteur_nom} <{cfg.smtp_user}>"
        msg["To"]      = ", ".join(cfg.destinataires)
        msg.attach(MIMEText(corps_txt,  "plain", "utf-8"))
        msg.attach(MIMEText(corps_html, "html",  "utf-8"))
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as srv:
            srv.ehlo()                                    # 1. identification initiale
            srv.starttls()                                # 2. chiffrement TLS
            srv.ehlo()                                    # 3. ré-identification après TLS (obligatoire Gmail)
            srv.login(cfg.smtp_user, cfg.smtp_password)   # 4. authentification
            srv.sendmail(cfg.smtp_user, cfg.destinataires, msg.as_string())  # 5. envoi
        return {"succes": True, "destinataires": cfg.destinataires}
    except smtplib.SMTPAuthenticationError:
        return {"succes": False, "erreur": "❌ Authentification échouée — utilisez un mot de passe d'application Gmail (16 caractères)"}
    except smtplib.SMTPException as e:
        return {"succes": False, "erreur": f"❌ Erreur SMTP : {e}"}
    except OSError as e:
        return {"succes": False, "erreur": f"❌ Connexion réseau impossible : {e}"}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


def _envoyer_webhook(cfg: ConfigAlertes, payload: dict) -> dict:
    """Envoie une notification webhook (Slack / Discord / Teams / générique)."""
    risque  = payload["risque"]
    prio    = payload["priorite"]
    mois    = payload["mois"]
    annee   = payload["annee"]
    conf    = payload["confiance"]
    cond    = payload["conditions"]
    probas  = payload["probabilites"]
    reco    = payload["recommandation"]
    couleur = RISQUE_COLOR.get(risque, "#888")
    emoji   = RISQUE_EMOJI.get(risque, "⚠️")
    ts      = payload["timestamp"]

    prob_txt = " | ".join([f"{k}: {v:.0%}" for k, v in probas.items()])
    titre = f"{emoji} ALERTE {prio} — Risque {risque} · {mois} {annee}"
    texte = (f"📍 Agdez, Maroc · Confiance : {conf:.0%}\n"
             f"🌡️ T={cond['temperature']}°C | 💧 H={cond['humidite']}% | "
             f"🌧️ P={cond['precipitation']}mm | 💨 V={cond['vent']}m/s\n"
             f"Probabilités : {prob_txt}\n💬 {reco}")

    if cfg.webhook_type == "slack":
        data = {"text": titre, "attachments": [{"color": couleur, "text": texte,
                "footer": f"Agdez Fire Risk · {ts}"}]}
    elif cfg.webhook_type == "discord":
        data = {"username": "🔥 Agdez Fire Alert", "content": titre,
                "embeds": [{"description": texte, "color": int(couleur.lstrip("#"), 16),
                            "footer": {"text": f"Agdez · {ts}"}}]}
    elif cfg.webhook_type == "teams":
        data = {"@type": "MessageCard", "@context": "https://schema.org/extensions",
                "themeColor": couleur.lstrip("#"), "summary": titre,
                "sections": [{"activityTitle": titre, "text": texte.replace("\n","<br>")}]}
    else:
        data = payload

    try:
        r = requests.post(cfg.webhook_url, json=data, timeout=8,
                          headers={"Content-Type": "application/json"})
        if r.status_code in (200, 204):
            return {"succes": True, "status_code": r.status_code}
        return {"succes": False, "status_code": r.status_code, "erreur": r.text[:200]}
    except requests.exceptions.ConnectionError:
        return {"succes": False, "erreur": "❌ Impossible de joindre le webhook — vérifiez l'URL"}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


def _sauvegarder_alerte_json(payload: dict) -> dict:
    """Sauvegarde l'alerte dans un fichier JSON horodaté dans reports/."""
    try:
        RPT.mkdir(parents=True, exist_ok=True)
        risque_safe = payload["risque"].replace(" ", "_")
        nom    = f"alerte_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{risque_safe}.json"
        chemin = RPT / nom
        chemin.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"succes": True, "fichier": str(chemin)}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


def envoyer_alerte(cfg: ConfigAlertes, risque: str, confiance: float,
                   temperature: float, humidite: float, precipitation: float,
                   vent: float, mois: str, annee: int, probas: dict,
                   recommandation: str, scenario: str = "") -> dict:
    """
    Fonction principale : envoie l'alerte via tous les canaux configurés.
    Retourne un dict avec les résultats de chaque canal.
    """
    if risque not in NIVEAUX_ALERTE:
        return {"ignore": True, "raison": f"Risque {risque} ne nécessite pas d'alerte"}

    payload = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "priorite":      "CRITIQUE" if risque == "Très élevé" else "HAUTE",
        "risque":        risque,
        "confiance":     round(confiance, 4),
        "zone":          "Agdez, Drâa-Tafilalet, Maroc",
        "scenario":      scenario or f"{mois} {annee}",
        "mois":          mois,
        "annee":         annee,
        "conditions":    {"temperature": temperature, "humidite": humidite,
                          "precipitation": precipitation, "vent": vent},
        "probabilites":  probas,
        "recommandation": recommandation,
    }

    resultats = {"email": None, "webhook": None, "json": None}

    if cfg.email_actif and not cfg.erreurs():
        resultats["email"] = _envoyer_email(cfg, payload)

    if cfg.webhook_actif and cfg.webhook_url:
        resultats["webhook"] = _envoyer_webhook(cfg, payload)

    if cfg.sauvegarder_json:
        resultats["json"] = _sauvegarder_alerte_json(payload)

    return resultats


# ============================================================================
# ── Helpers ──────────────────────────────────────────────────────────────────
# ============================================================================

def hex2rgba(h: str, a: float = 0.15) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[:2],16)},{int(h[2:4],16)},{int(h[4:],16)},{a})"

def read_csv(path: Path) -> pd.DataFrame | None:
    for enc in ["utf-8","latin-1","cp1252"]:
        for sep in [";",","]:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc)
                if df.shape[1] > 1:
                    return df
            except Exception:
                pass
    return None

def read_xlsx(path: Path, sheet=0) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet)
    except Exception:
        return None

def load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ── Prédiction ML ────────────────────────────────────────────────────────────
FEAT_ORDER = [
    "temperature","humidite","precipitation","vent",
    "pente","altitude","exposition","ndvi_avant",
    "indice_secheresse","indice_propagation","stress_vegetal",
    "exposition_sud","mois_num",
]

def build_X(t, h, p, v, mois_num=1, ndvi=0.144):
    row = dict(temperature=t, humidite=h, precipitation=p, vent=v,
               pente=PENTE, altitude=ALTITUDE, exposition=EXPOSITION,
               ndvi_avant=ndvi, mois_num=mois_num)
    df = pd.DataFrame([row])
    df["indice_secheresse"]  = (df["temperature"] - df["humidite"]) / (df["precipitation"] + 0.1)
    df["indice_propagation"] = df["vent"] * np.sin(np.radians(PENTE))
    df["stress_vegetal"]     = (1 - df["ndvi_avant"]) * df["temperature"] / 10
    df["exposition_sud"]     = float(np.cos(np.radians(EXPOSITION - 180)))
    return df[FEAT_ORDER]

def ml_predict(model, le, t, h, p, v, mois_num=1, ndvi=0.144):
    X = build_X(t, h, p, v, mois_num, ndvi)
    y      = model.predict(X)[0]
    probas = model.predict_proba(X)[0]
    label  = le.inverse_transform([y])[0]
    return label, float(probas.max()), {c: float(pb) for c, pb in zip(le.classes_, probas)}

def recommendation(risque: str) -> str:
    return {
        "Faible":     "✅ Surveillance standard. Conditions favorables.",
        "Moyen":      "⚠️ Vigilance modérée. Vérifier les équipements.",
        "Élevé":      "🟠 Patrouilles terrain actives. Alerter les équipes.",
        "Très élevé": "🔴 DANGER — Activer plan ORSEC. Interdire accès zones boisées.",
    }.get(risque, "—")

def style_risque(val):
    mp = {
        "Très élevé": "background-color:#3d0000;color:#ff6b6b;font-weight:bold",
        "Élevé":      "background-color:#3d1e00;color:#ffaa55;font-weight:bold",
        "Moyen":      "background-color:#3d3000;color:#ffd700",
        "Faible":     "background-color:#0d3020;color:#7fff9a",
    }
    return mp.get(val, "")

# ── API météo temps réel ──────────────────────────────────────────────────────
def fetch_meteo_realtime() -> dict | None:
    """Appel Open-Meteo API pour Agdez. Retourne dict ou None si erreur."""
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            "&current=temperature_2m,relative_humidity_2m,"
            "precipitation,wind_speed_10m"
            "&wind_speed_unit=ms&timezone=Africa%2FCasablanca"
        )
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            c = r.json()["current"]
            return dict(
                temperature   = round(c["temperature_2m"], 1),
                humidite      = round(c["relative_humidity_2m"], 1),
                precipitation = round(c["precipitation"], 2),
                vent          = round(c["wind_speed_10m"], 1),
                source        = "Open-Meteo (temps réel)",
            )
    except Exception:
        pass
    return None

# ── Chargement données (cache) ────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_model():
    try:
        model = joblib.load(MDL / "model_risque_incendie.pkl")
        le    = joblib.load(MDL / "label_encoder.pkl")
        return model, le
    except FileNotFoundError as e:
        st.error(f"❌ Modèle introuvable : {e}")
        st.stop()

@st.cache_data(show_spinner=False)
def load_data():
    d = {}
    d["sc"]    = read_csv(META / "predictions_scenarios_2026.csv")
    d["proj"]  = read_csv(META / "projections_climatiques.csv")
    d["fi"]    = read_csv(META / "feature_importance.csv")
    d["mi"]    = load_json(META / "model_info.json")
    d["ann"]   = read_csv(CSV  / "climat_statistiques_annuelles.csv")
    d["ete"]   = read_csv(CSV  / "climat_conditions_ete_2025.csv")
    d["recap"] = read_csv(CSV  / "climat_recap_incendie.csv")
    d["idx"]   = read_xlsx(INCENDIE / "indices_stats.xlsx")
    d["sev"]   = read_xlsx(INCENDIE / "severity_classes.xlsx")
    d["sum"]   = read_xlsx(INCENDIE / "summary_complete.xlsx")
    d["alertes"] = [load_json(Path(f))
                    for f in sorted(glob.glob(str(RPT / "alerte_*.json")))]
    return d

# ============================================================================
# ── Graphiques Plotly (toutes données réelles) ───────────────────────────────
# ============================================================================
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#0d0d1a",
    plot_bgcolor="#0d0d1a",
    font_family="Syne",
    font_color="#e2e8f0",
    margin=dict(t=50, b=35, l=10, r=10),
)
C = dict(rouge="#d62828", orange="#f77f00", bleu="#3498db",
         vert="#27ae60", violet="#a855f7", cyan="#06b6d4")
RP = {"Faible":"#27ae60","Moyen":"#e67e22","Élevé":"#e74c3c","Très élevé":"#8e1a1a"}

def fig_temp_humidity_full(df_proj):
    """Température + humidité 2017–2035 (historique + projections)."""
    # Historique 2017-2025
    annees_h = list(HIST.keys())
    temps_h  = [HIST[a]["temperature"] for a in annees_h]
    hum_h    = [HIST[a]["humidite"]    for a in annees_h]
    # Projections 2026-2035
    annees_p = df_proj["annee"].tolist()
    temps_p  = df_proj["temperature"].tolist()
    hum_p    = df_proj["humidite"].tolist()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Historique température
    fig.add_trace(go.Scatter(
        x=annees_h, y=temps_h, name="T° historique",
        mode="lines+markers",
        line=dict(color=C["rouge"], width=3),
        marker=dict(size=9),
        text=[f"{v:.2f}°C" for v in temps_h],
        textposition="top center", textfont=dict(size=8.5),
    ), secondary_y=False)

    # Projections température
    fig.add_trace(go.Scatter(
        x=[annees_h[-1]] + annees_p,
        y=[temps_h[-1]]  + temps_p,
        name="T° projetée",
        mode="lines+markers",
        line=dict(color=C["rouge"], width=2.5, dash="dash"),
        marker=dict(size=8, symbol="diamond"),
        text=[""] + [f"{v:.1f}°C" for v in temps_p],
        textposition="top center", textfont=dict(size=8),
    ), secondary_y=False)

    # Humidité historique
    fig.add_trace(go.Scatter(
        x=annees_h, y=hum_h, name="H% historique",
        mode="lines+markers",
        line=dict(color=C["bleu"], width=2),
        marker=dict(size=7),
    ), secondary_y=True)

    # Humidité projetée
    fig.add_trace(go.Scatter(
        x=[annees_h[-1]] + annees_p,
        y=[hum_h[-1]]    + hum_p,
        name="H% projetée",
        mode="lines",
        line=dict(color=C["bleu"], width=1.8, dash="dot"),
    ), secondary_y=True)

    # Zone de séparation historique/projection
    fig.add_vrect(x0=2025.5, x1=2035.5,
                  fillcolor="rgba(255,100,0,0.05)",
                  layer="below", line_width=0,
                  annotation_text="Projections →",
                  annotation_position="top left",
                  annotation_font_color="#f77f00")

    fig.update_layout(
        title="Évolution climatique 2017–2035 (historique + projections CC)", **DARK,
        legend=dict(orientation="h", y=1.12),
    )
    fig.update_yaxes(title_text="Température (°C)", secondary_y=False, color=C["rouge"])
    fig.update_yaxes(title_text="Humidité (%)", secondary_y=True, color=C["bleu"])
    return fig


def fig_anomalies():
    """Anomalies de température estivale (référence 2017-2024)."""
    annees = list(HIST.keys())
    temps  = [HIST[a]["temperature"] for a in annees]
    ref    = np.mean(temps[:-1])  # référence sans 2025
    anom   = [t - ref for t in temps]
    colors = [C["rouge"] if a >= 0 else "#3498db" for a in anom]
    fig = go.Figure(go.Bar(
        x=annees, y=anom, marker_color=colors,
        text=[f"{a:+.2f}°C" for a in anom], textposition="outside",
    ))
    fig.add_hline(y=0, line_color="white", line_width=1.5)
    fig.update_layout(
        title=f"Anomalies T° estivale (référence 2017-2024 · moy={ref:.2f}°C)",
        yaxis_title="Écart (°C)", **DARK,
    )
    return fig


def fig_precipitations():
    """Précipitations annuelles 2017-2025 + tendance."""
    annees = list(HIST.keys())
    prec   = [HIST[a]["precipitation"] for a in annees]
    z      = np.polyfit(annees, prec, 1)
    trend  = np.poly1d(z)(annees)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=annees, y=prec, name="Précipitations",
                         marker_color="#3498db",
                         text=[f"{v:.0f}" for v in prec], textposition="outside"))
    fig.add_trace(go.Scatter(x=annees, y=trend, name="Tendance",
                             line=dict(color=C["orange"], width=2.5, dash="dash"),
                             mode="lines"))
    fig.update_layout(title="Précipitations annuelles + tendance (2017–2025)",
                      yaxis_title="mm", **DARK)
    return fig


def fig_vent_hum():
    """Vent & humidité annuels 2017-2025."""
    annees = list(HIST.keys())
    vent   = [HIST[a]["vent"]    for a in annees]
    hum    = [HIST[a]["humidite"]for a in annees]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=annees, y=vent, name="Vent (m/s)",
                             mode="lines+markers",
                             line=dict(color=C["vert"], width=2.5),
                             marker=dict(size=9)),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=annees, y=hum, name="Humidité (%)",
                             mode="lines+markers",
                             line=dict(color=C["bleu"], width=2, dash="dot"),
                             marker=dict(size=8)),
                  secondary_y=True)
    fig.update_layout(title="Vent & Humidité annuels (2017–2025)", **DARK)
    fig.update_yaxes(title_text="Vent (m/s)", secondary_y=False, color=C["vert"])
    fig.update_yaxes(title_text="Humidité (%)", secondary_y=True, color=C["bleu"])
    return fig


def fig_ombrothermique():
    """Diagramme ombrothermique Agdez 2025."""
    mois = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
    prec = [0.8, 5.1, 6.0, 18.7, 1.1, 2.85, 26.43, 0.18, 0.05, 0.0, 2.0, 31.0]
    temp = [9.3, 11.5, 14.0, 19.0, 22.1, 29.3, 32.7, 31.4, 26.0, 21.5, 15.1, 8.5]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=mois, y=prec, name="Précipitations (mm)",
                         marker_color="#3498db", opacity=0.75), secondary_y=False)
    fig.add_trace(go.Scatter(x=mois, y=temp, name="Température (°C)",
                             mode="lines+markers",
                             line=dict(color=C["rouge"], width=3),
                             marker=dict(size=9, color=C["rouge"])), secondary_y=True)
    fig.update_layout(title="Diagramme ombrothermique — Agdez 2025", **DARK)
    fig.update_yaxes(title_text="Précipitations (mm)", secondary_y=False, color="#3498db")
    fig.update_yaxes(title_text="Température (°C)", secondary_y=True, color=C["rouge"])
    return fig


def fig_ete_bars():
    """Températures été 2025 (Juin/Juillet/Août) — données réelles."""
    mois = list(ETE_2025.keys())
    vals = [ETE_2025[m]["temperature"] for m in mois]
    moy  = np.mean(vals)
    cols = [C["rouge"] if v == max(vals) else C["orange"] for v in vals]
    fig  = go.Figure(go.Bar(
        x=mois, y=vals, marker_color=cols,
        text=[f"{v:.2f}°C" for v in vals], textposition="outside",
    ))
    fig.add_hline(y=moy, line_dash="dash", line_color="#58a6ff",
                  annotation_text=f"Moy été: {moy:.1f}°C", annotation_position="right")
    fig.update_layout(title="Températures estivales 2025 — Agdez",
                      yaxis_title="°C", yaxis_range=[0, 38], **DARK)
    return fig


def fig_fi(df):
    """Importance des features — barres horizontales."""
    df2   = df.sort_values("importance")
    cols  = [C["rouge"] if v > 0.15 else C["orange"] if v > 0.09 else "#3498db"
             for v in df2["importance"]]
    fig   = go.Figure(go.Bar(
        x=df2["importance"], y=df2["feature"],
        orientation="h", marker_color=cols,
        text=[f"{v:.1%}" for v in df2["importance"]], textposition="outside",
    ))
    fig.update_layout(title="Importance des features — Random Forest",
                      xaxis_title="Importance", **DARK, height=430)
    return fig


def fig_fi_pie(df):
    """Camembert répartition features actives."""
    dfa = df[df["importance"] > 0].sort_values("importance", ascending=False)
    fig = go.Figure(go.Pie(
        labels=dfa["feature"], values=dfa["importance"],
        hole=0.4,
        marker=dict(colors=[C["rouge"],C["orange"],"#3498db",C["vert"],
                             C["violet"],C["cyan"],"#f59e0b","#10b981","#6366f1"]),
        textinfo="label+percent",
    ))
    fig.update_layout(title="Répartition features actives", **DARK,
                      showlegend=False, height=360)
    return fig


def fig_severity_pie(df):
    """Camembert classes de sévérité incendie 2025."""
    df2 = df[df["Classe"] > 0] if "Classe" in df.columns else df.iloc[1:]
    lbl = df2.iloc[:, 1].tolist() if df2.shape[1] > 1 else ["Faible","Moyen","Fort"]
    val = df2["Surface (ha)"].tolist() if "Surface (ha)" in df2.columns else [323.94, 60.42, 4.15]
    fig = go.Figure(go.Pie(
        labels=lbl, values=val,
        hole=0.35, marker=dict(colors=[C["vert"],C["orange"],C["rouge"],"#8e1a1a"]),
        textinfo="label+percent+value",
        texttemplate="%{label}<br>%{value:.1f} ha (%{percent})",
    ))
    fig.update_layout(title="Classes de sévérité — Incendie Agdez 2025", **DARK)
    return fig


def fig_ndvi_bars(df_idx):
    """NDVI avant/après incendie."""
    if df_idx is None:
        vals_m = [0.1443, 0.1167]
    else:
        try:
            vals_m = [
                df_idx[df_idx["Indice"].str.contains("avant", case=False)]["Moyenne"].values[0],
                df_idx[df_idx["Indice"].str.contains("après", case=False)]["Moyenne"].values[0],
            ]
        except Exception:
            vals_m = [0.1443, 0.1167]
    delta = ((vals_m[1] - vals_m[0]) / vals_m[0]) * 100
    fig   = go.Figure(go.Bar(
        x=["NDVI avant incendie", "NDVI après incendie"],
        y=vals_m, marker_color=[C["vert"], C["rouge"]],
        text=[f"{v:.4f}" for v in vals_m], textposition="outside",
    ))
    fig.update_layout(
        title=f"NDVI avant vs après — Agdez 2025 (Δ = {delta:.1f}%)",
        yaxis_title="NDVI moyen", yaxis_range=[0, 0.22], **DARK,
        annotations=[dict(x=0.5, y=0.95, xref="paper", yref="paper",
                          text=f"Perte végétation : {abs(delta):.1f}%",
                          showarrow=False, font=dict(color=C["orange"], size=13))],
    )
    return fig


def fig_dnbr_radar(df_idx):
    """Radar NDVI/dNBR."""
    try:
        nd_av = float(df_idx[df_idx["Indice"].str.contains("avant", case=False)]["Moyenne"].values[0])
        nd_ap = float(df_idx[df_idx["Indice"].str.contains("après", case=False)]["Moyenne"].values[0])
        dnbr  = float(df_idx[df_idx["Indice"].str.contains("dNBR",  case=False)]["Moyenne"].values[0])
    except Exception:
        nd_av, nd_ap, dnbr = 0.1443, 0.1167, 0.0248
    cats  = ["NDVI avant", "NDVI après", "dNBR"]
    vals  = [nd_av, nd_ap, dnbr]
    maxv  = max(vals)
    normd = [v / maxv if maxv > 0 else 0 for v in vals]
    fig   = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=normd + [normd[0]], theta=cats + [cats[0]],
        name="Valeurs normalisées",
        line=dict(color=C["rouge"], width=2),
        fill="toself",
        fillcolor=hex2rgba(C["rouge"], 0.15),
    ))
    fig.update_layout(
        title="Radar NDVI/dNBR",
        polar=dict(bgcolor="#111", radialaxis=dict(visible=True, range=[0,1])),
        **DARK,
    )
    return fig


def fig_scenarios_stack(df):
    """Barres empilées probabilités réelles par scénario."""
    short = [s[:30] + "…" if len(s) > 30 else s for s in df["scenario"]]
    fig   = go.Figure()
    for col, lbl, col_r in [
        ("prob_tres_eleve","Très élevé","#8e1a1a"),
        ("prob_eleve",     "Élevé",     "#e74c3c"),
        ("prob_moyen",     "Moyen",     "#e67e22"),
        ("prob_faible",    "Faible",    "#27ae60"),
    ]:
        fig.add_trace(go.Bar(
            name=lbl, x=short, y=df[col] * 100,
            marker_color=col_r,
            text=[f"{v:.0%}" if v > 0.04 else "" for v in df[col]],
            textposition="inside",
        ))
    fig.update_layout(
        barmode="stack",
        title="Probabilités réelles du modèle — 10 scénarios 2026",
        yaxis_title="%", xaxis_tickangle=-30,
        legend=dict(orientation="h", y=1.12), **DARK,
    )
    return fig


def fig_scenarios_conf(df):
    """Barres de confiance par scénario."""
    cols = [RP.get(r, "#888") for r in df["risque_predit"]]
    short= [s[:30]+"…" if len(s)>30 else s for s in df["scenario"]]
    fig  = go.Figure(go.Bar(
        x=short, y=df["confiance"] * 100,
        marker_color=cols,
        text=[f"{c:.0%}" for c in df["confiance"]],
        textposition="outside",
    ))
    fig.update_layout(title="Confiance du modèle par scénario (%)",
                      yaxis_title="%", yaxis_range=[0,115],
                      xaxis_tickangle=-30, **DARK)
    return fig


def fig_scenarios_heatmap(df):
    """Heatmap probabilités — 10 scénarios × 4 classes."""
    short = [s[:28]+"…" if len(s)>28 else s for s in df["scenario"]]
    prob_m = df[["prob_faible","prob_moyen","prob_eleve","prob_tres_eleve"]].values * 100
    fig = go.Figure(go.Heatmap(
        z=prob_m,
        x=["Faible","Moyen","Élevé","Très élevé"],
        y=short,
        colorscale=[[0,"#0d3020"],[0.33,"#3d3000"],[0.66,"#3d1e00"],[1.0,"#3d0000"]],
        text=[[f"{v:.0f}%" for v in row] for row in prob_m],
        texttemplate="%{text}",
        colorbar=dict(title="Prob (%)", thickness=12),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(title="Heatmap probabilités modèle — scénarios 2026",
                      **DARK, height=380)
    return fig


def fig_scenarios_radar(df):
    """Radar météo par catégorie de scénario."""
    cats  = df["categorie"].unique()
    cols_v= ["temperature","humidite","precipitation","vent"]
    lbls  = ["T°C","Humidité","Précip.","Vent"]
    COLS  = [C["rouge"],"#8e1a1a","#3498db",C["vert"]]
    fig   = go.Figure()
    for i, cat in enumerate(cats):
        sub   = df[df["categorie"] == cat]
        means = [sub[c].mean() for c in cols_v]
        maxs  = [df[c].max()   for c in cols_v]
        normd = [v/m if m > 0 else 0 for v,m in zip(means,maxs)]
        col   = COLS[i % len(COLS)]
        fig.add_trace(go.Scatterpolar(
            r=normd + [normd[0]], theta=lbls + [lbls[0]],
            name=cat, line=dict(color=col, width=2.2),
            fill="toself", fillcolor=hex2rgba(col, 0.12),
        ))
    fig.update_layout(
        title="Profil météo par catégorie",
        polar=dict(bgcolor="#111", radialaxis=dict(visible=True, range=[0,1])),
        **DARK,
    )
    return fig


def fig_proj_temp(df):
    """Température projetée juillet 2026-2035."""
    fig = go.Figure(go.Scatter(
        x=df["annee"], y=df["temperature"],
        mode="lines+markers+text",
        text=[f"{v:.1f}°C" for v in df["temperature"]],
        textposition="top center",
        line=dict(color=C["rouge"], width=3),
        marker=dict(size=11, color=C["rouge"]),
        fill="tozeroy", fillcolor=hex2rgba(C["rouge"], 0.08),
    ))
    fig.update_layout(title="Température projetée juillet 2026–2035",
                      yaxis_title="°C", **DARK)
    return fig


def fig_proj_prob_evol(df):
    """Évolution probabilités 2026-2035 (données réelles CSV)."""
    fig = go.Figure()
    for col, lbl, col_r, dash in [
        ("prob_tres_eleve","Très élevé","#8e1a1a","solid"),
        ("prob_eleve",     "Élevé",     "#e74c3c","dot"),
        ("prob_moyen",     "Moyen",     "#e67e22","dash"),
        ("prob_faible",    "Faible",    "#27ae60","longdash"),
    ]:
        fig.add_trace(go.Scatter(
            x=df["annee"], y=df[col]*100, name=lbl,
            mode="lines+markers",
            line=dict(color=col_r, width=2.5, dash=dash),
            marker=dict(size=9),
            text=[f"{v:.0%}" for v in df[col]],
            hovertemplate=f"<b>{lbl}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
    fig.update_layout(title="Évolution probabilités par classe — 2026→2035",
                      yaxis_title="%", legend=dict(orientation="h", y=1.12), **DARK)
    return fig


def fig_proj_heatmap(df):
    """Heatmap probabilités 2026-2035."""
    prob_m = df[["prob_faible","prob_moyen","prob_eleve","prob_tres_eleve"]].values * 100
    fig = go.Figure(go.Heatmap(
        z=prob_m,
        x=["Faible","Moyen","Élevé","Très élevé"],
        y=[str(int(a)) for a in df["annee"]],
        colorscale=[[0,"#0d3020"],[0.33,"#3d3000"],[0.66,"#3d1e00"],[1.0,"#3d0000"]],
        text=[[f"{v:.0f}%" for v in row] for row in prob_m],
        texttemplate="%{text}", showscale=True,
        colorbar=dict(title="Prob (%)", thickness=12),
    ))
    fig.update_layout(title="Heatmap probabilités — Projections juillet 2026–2035",
                      **DARK, height=360)
    return fig


def fig_fvt(model, le):
    """Fenêtre de Vulnérabilité Temporelle — simulation journalière été 2026."""
    dates = pd.date_range("2026-06-01", "2026-08-31", freq="D")
    np.random.seed(42)
    rows  = []
    for d in dates:
        doy = d.timetuple().tm_yday
        t   = round(29.5 + 3.5*np.sin(np.pi*(doy-152)/91) + np.random.normal(0,1.2), 2)
        h   = round(max(8.0, 20.0-4.0*np.sin(np.pi*(doy-152)/91) + np.random.normal(0,2)), 2)
        p   = round(max(0.0, np.random.exponential(3.5) if np.random.random()<0.12 else 0.0), 2)
        v   = round(max(1.5, 4.0 + np.random.normal(0,0.4)), 2)
        rows.append(dict(date=d, temperature=t, humidite=h, precipitation=p, vent=v,
                         mois_num={6:0,7:1,8:2}[d.month],
                         pente=PENTE, altitude=ALTITUDE, exposition=EXPOSITION,
                         ndvi_avant=0.144))
    df = pd.DataFrame(rows)
    df["indice_secheresse"]  = (df["temperature"] - df["humidite"]) / (df["precipitation"] + 0.1)
    df["indice_propagation"] = df["vent"] * np.sin(np.radians(PENTE))
    df["stress_vegetal"]     = (1-0.144) * df["temperature"] / 10
    df["exposition_sud"]     = float(np.cos(np.radians(EXPOSITION-180)))
    X  = df[FEAT_ORDER]
    lbs= le.inverse_transform(model.predict(X))
    df["risque"] = lbs
    df["r_num"]  = [{"Faible":0,"Moyen":1,"Élevé":2,"Très élevé":3}[l] for l in lbs]
    cs = [[0.0,"#27ae60"],[0.33,"#e67e22"],[0.67,"#e74c3c"],[1.0,"#8e1a1a"]]
    fig = go.Figure(go.Heatmap(
        z=df["r_num"].values,
        x=df["date"].dt.strftime("%d/%m").values,
        y=["Risque"]*len(df),
        colorscale=cs, zmin=0, zmax=3,
        text=df["risque"].values,
        hovertemplate="<b>%{x}</b><br>Risque: %{text}<br>T=%{customdata[0]}°C H=%{customdata[1]}%<extra></extra>",
        customdata=np.column_stack([df["temperature"], df["humidite"]]),
        colorbar=dict(tickvals=[0,1,2,3],
                      ticktext=["Faible","Moyen","Élevé","Très élevé"],
                      thickness=12, len=0.6),
    ))
    fig.update_layout(
        title="🗓️ Fenêtre de Vulnérabilité Temporelle — Été 2026 (92 jours simulés)",
        xaxis=dict(tickangle=-45, tickfont=dict(size=7)),
        yaxis=dict(showticklabels=False), height=220, **DARK,
    )
    return fig, df


def fig_proba_gauge(probas: dict, risque: str):
    val = probas.get(risque, 0) * 100
    col = RISQUE_COLOR.get(risque, "#888")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": f"P({risque})", "font": {"size": 12}},
        number={"suffix": "%", "font": {"size": 25}},
        gauge={
            "axis": {"range": [0,100], "tickcolor":"#555"},
            "bar":  {"color": col, "thickness": 0.75},
            "bgcolor": "#111",
            "steps": [{"range":[0,25],"color":"#1a1a1a"},{"range":[25,50],"color":"#1f1a10"},
                      {"range":[50,75],"color":"#2a1010"},{"range":[75,100],"color":"#3d0000"}],
            "threshold": {"line": {"color": col, "width": 4}, "value": val},
        },
    ))
    fig.update_layout(paper_bgcolor="#0d0d1a", font_family="Syne",
                      font_color="#e2e8f0",
                      margin=dict(t=50,b=10,l=20,r=20), height=200)
    return fig


# ── Carte Folium ──────────────────────────────────────────────────────────────
def make_map(risque, conf, probas, t, h, p, v, mois, annee):
    color = RISQUE_COLOR.get(risque, "#888")
    emoji = RISQUE_EMOJI.get(risque, "⚪")
    proba_html = "".join([
        f'<span style="background:{RISQUE_COLOR.get(c,"#888")};color:white;'
        f'border-radius:3px;padding:2px 7px;margin:2px;display:inline-block;font-size:0.75rem">'
        f'{c}: {pb:.0%}</span>'
        for c, pb in probas.items()
    ])
    popup_html = f"""
    <div style="font-family:Arial;min-width:290px">
      <div style="background:{color};color:white;padding:10px 14px;border-radius:8px 8px 0 0;margin:-4px -4px 10px">
        <div style="font-size:1.1rem;font-weight:bold">{emoji} {risque}</div>
        <div style="font-size:0.77rem;opacity:.9">Confiance : {conf:.0%} · {mois} {annee}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:0.78rem">
        {''.join([f'<tr style="background:{"#f8f8f8" if i%2==0 else "white"}"><td style="padding:5px 8px;font-weight:bold">{k}</td><td style="padding:5px 8px">{val}</td></tr>'
                  for i,(k,val) in enumerate([
                    ("📍 Zone","Agdez, Drâa-Tafilalet"),("🌐 Coordonnées",f"{LAT}°N {abs(LON)}°W"),
                    ("⛰️ Altitude",f"{ALTITUDE} m"),("📐 Pente",f"{PENTE}°"),
                    ("🧭 Exposition","165.51° (Sud-Est)"),("🌡️ Température",f"{t}°C"),
                    ("💧 Humidité",f"{h}%"),("🌧️ Précipitations",f"{p} mm"),
                    ("💨 Vent",f"{v} m/s"),("🔥 Ind. sécheresse",f"{(t-h)/(p+0.1):.2f}"),
                  ])])}
      </table>
      <div style="background:#fffbea;border-radius:5px;padding:8px;margin-top:8px;font-size:0.75rem">
        <b>Recommandation :</b> {recommendation(risque)}
      </div>
      <div style="margin-top:8px;font-size:0.73rem"><b>Probabilités :</b><br>{proba_html}</div>
    </div>"""
    m = folium.Map(location=[LAT, LON], zoom_start=12,
                   tiles="CartoDB dark_matter", prefer_canvas=True)
    folium.Circle(location=[LAT, LON], radius=5000, color=color,
                  fill=True, fill_opacity=0.10, weight=1.5).add_to(m)
    folium.CircleMarker(
        location=[LAT, LON], radius=16, color=color,
        fill=True, fill_color=color, fill_opacity=0.85, weight=3,
        popup=folium.Popup(popup_html, max_width=330),
        tooltip=f"🔥 Agdez — {risque} ({conf:.0%})",
    ).add_to(m)
    folium.CircleMarker(location=[LAT, LON], radius=4, color="white",
                        fill=True, fill_color="white", fill_opacity=1, weight=0).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI", name="🛰️ Satellite", overlay=False,
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ============================================================================
# ── SIDEBAR ──────────────────────────────────────────────────────────────────
# ============================================================================
def sidebar(meteo_rt):
    st.sidebar.markdown(f"""
    <div style="text-align:center;padding:10px 0">
      <div style="font-size:2rem">🔥</div>
      <div style="font-family:'Syne',sans-serif;font-weight:800;color:#d62828;font-size:0.95rem">
        Agdez Fire Risk
      </div>
      <div style="font-family:'Space Mono',monospace;font-size:0.62rem;color:#a0aec0">
        Drâa-Tafilalet · Maroc
      </div>
    </div>""", unsafe_allow_html=True)

    # Météo temps réel
    if meteo_rt:
        st.sidebar.success(f"📡 **Météo en temps réel** · {meteo_rt['source']}")
    else:
        st.sidebar.warning("⚠️ API indisponible · valeurs par défaut")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**📅 Sélection de la période**")

    annee = st.sidebar.slider("Année", 2017, 2035, 2026)
    mois  = st.sidebar.selectbox("Mois", ["Juin","Juillet","Août"], index=1)

    # Valeurs par défaut selon source
    if annee <= 2025:
        # Données réelles historiques
        h_data = HIST.get(annee, HIST[2025])
        if annee == 2025 and mois in ETE_2025:
            d = ETE_2025[mois]
            d_t, d_h, d_p, d_v = d["temperature"], d["humidite"], d["precipitation"], d["vent"]
        else:
            d_t = h_data["temperature"]
            d_h = h_data["humidite"]
            d_p = h_data["precipitation"] / 12  # mensuel approx
            d_v = h_data["vent"]
    else:
        # Données projetées
        st.sidebar.info(f"📊 Données modèle CC · Juillet {annee}")
        d_t, d_h, d_p, d_v = 33.3, 15.6, 20.9, 4.15  # défaut 2026

    # Pré-remplir avec temps réel si disponible
    if meteo_rt:
        d_t = meteo_rt["temperature"]
        d_h = meteo_rt["humidite"]
        d_p = meteo_rt["precipitation"]
        d_v = meteo_rt["vent"]

    st.sidebar.markdown("---")
    st.sidebar.markdown("**🌡️ Variables climatiques**")
    temperature   = st.sidebar.slider("Température (°C)", 10.0, 45.0, float(d_t), 0.1)
    humidite      = st.sidebar.slider("Humidité (%)",      5.0,  70.0, float(d_h), 0.5)
    precipitation = st.sidebar.slider("Précipitations (mm)", 0.0, 100.0, float(min(d_p, 100.0)), 0.5)
    vent          = st.sidebar.slider("Vent (m/s)",         0.5,  12.0, float(d_v), 0.1)
    ndvi          = st.sidebar.slider("NDVI avant",         0.05,  0.40, 0.144, 0.005)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**⚡ Préréglages**")
    presets = {
        "🔥 Canicule extrême": (38.0, 10.0, 0.0, 5.5),
        "⛈️ Après pluies":     (26.0, 45.0,55.0, 3.0),
        "💨 Tempête de vent":  (30.0, 18.0, 1.0, 8.0),
        "✅ Conditions sûres": (22.0, 55.0,40.0, 2.0),
        "📊 Juillet 2025 réel":(32.69,16.42,26.43,4.01),
        "— Personnalisé —":    None,
    }
    preset = st.sidebar.radio("", list(presets.keys()), index=5,
                               label_visibility="collapsed")
    if presets[preset]:
        temperature, humidite, precipitation, vent = presets[preset]

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div style="font-size:0.65rem;color:#a0aec0;font-family:'Space Mono',monospace;line-height:1.8">
    🤖 Random Forest · 13 features<br>
    📊 Accuracy CV : 76.7% ± 15.2%<br>
    📅 Entraîné : 2017–2025<br>
    🌍 Zone : Agdez 30.69°N 6.45°W<br>
    🔥 Incendie : 15 Sep. 2025 · 388.51 ha
    </div>""", unsafe_allow_html=True)

    return annee, mois, temperature, humidite, precipitation, vent, ndvi


# ============================================================================
# ── MAIN ─────────────────────────────────────────────────────────────────────
# ============================================================================
def main():
    # Load realtime monitoring data
    try:
        with open("data/meteo_daily/live_data.json", "r") as f:
            live_data = json.load(f)

    except:
        live_data = None

    model, le = load_model()
    D         = load_data()
    meteo_rt  = fetch_meteo_realtime()
    # ===============================
    # REALTIME MONITORING
# ===============================

    st.subheader("🔥 Realtime Fire Monitoring")
    if live_data:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🌡 Temperature",
               f"{live_data.get('temperature', 0)} °C"
            )
        with col2:
            st.metric(
                "💧 Humidity",
              f"{live_data.get('humidity', 0)} %"
            )
        with col3:
            st.metric(
                "💨 Wind",
                f"{live_data.get('wind', 0)} km/h"
            )
        with col4:
            st.metric(
                "🔥 AI Risk",
              live_data.get('risk', 'Unknown')
          )
    

    else:
        
        st.warning("No realtime monitoring data")

    # ── Gestionnaire d'alertes ────────────────────────────────────────────────
    cfg_alertes = ConfigAlertes()

    # Sidebar
    annee, mois, temperature, humidite, precipitation, vent, ndvi = sidebar(meteo_rt)

    # ── Prédiction dynamique ──────────────────────────────────────────────────
    mois_num = MOIS_MAP[mois]

    # Pour années futures : récupérer probabilités exactes du CSV si disponibles
    if annee >= 2026 and D["proj"] is not None:
        proj_row = D["proj"][D["proj"]["annee"] == annee]
        if not proj_row.empty:
            r = proj_row.iloc[0]
            # On utilise les probabilités exactes du CSV modèle
            risque = r["risque_predit"]
            conf   = r["confiance"]
            probas = {
                "Faible":     r["prob_faible"],
                "Moyen":      r["prob_moyen"],
                "Élevé":      r["prob_eleve"],
                "Très élevé": r["prob_tres_eleve"],
            }
            # Prédiction fraîche avec sliders (what-if)
            risque_live, conf_live, probas_live = ml_predict(
                model, le, temperature, humidite, precipitation, vent, mois_num, ndvi)
            # Afficher les deux
            using_proj = True
        else:
            risque, conf, probas = ml_predict(
                model, le, temperature, humidite, precipitation, vent, mois_num, ndvi)
            risque_live, conf_live, probas_live = risque, conf, probas
            using_proj = False
    else:
        # Années historiques : prédiction fraîche + risque réel si disponible
        risque, conf, probas = ml_predict(
            model, le, temperature, humidite, precipitation, vent, mois_num, ndvi)
        risque_live, conf_live, probas_live = risque, conf, probas
        using_proj = False
        if annee in RISQUES_REELS:
            risque_reel = RISQUES_REELS[annee]
        else:
            risque_reel = None

    color = RISQUE_COLOR.get(risque, "#888")

    # ── ALERTE DYNAMIQUE ──────────────────────────────────────────────────────
    if risque in ["Élevé", "Très élevé"]:
        css_alert = "alert-r" if risque == "Très élevé" else "alert-o"
        tag_css   = "tag-r"   if risque == "Très élevé" else "tag-o"
        st.markdown(f"""
        <div class="{css_alert}">
          <span class="tag {tag_css}">⚡ ALERTE {'CRITIQUE' if risque=='Très élevé' else 'HAUTE'}</span>
          <div style="font-weight:700;font-size:1rem;margin:4px 0">
            {RISQUE_EMOJI[risque]} Risque {risque} prédit — {mois} {annee}
          </div>
          <div style="font-size:0.85rem;color:#ddd;line-height:1.7">
            Confiance : <b>{conf:.0%}</b> · T={temperature}°C · H={humidite}% · P={precipitation}mm · V={vent}m/s<br>
            {recommendation(risque)}
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="app-hdr">
      <h1>🔥 Agdez · Prédiction Risque Incendie de Forêt</h1>
      <p>Drâa-Tafilalet, Maroc · 30.69°N 6.45°W · Alt. {ALTITUDE} m · Pente {PENTE}° ·
         Random Forest v1.0.0 · Données 2017–2025 · Incendie 15 Sep. 2025</p>
    </div>""", unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
    kpis = [
        (k1, f"{RISQUE_EMOJI[risque]} {risque}", f"{mois} {annee}", color),
        (k2, f"{conf:.0%}", "Confiance modèle",  "#3498db"),
        (k3, f"{temperature}°C", "Température",  "#e74c3c"),
        (k4, f"{humidite}%",     "Humidité",     "#3498db"),
        (k5, "388.51 ha",        "Surface brûlée 2025", "#d62828"),
        (k6, "0.1443",           "NDVI avant 2025",     "#27ae60"),
        (k7, "76.7%",            "Accuracy CV modèle",  "#a855f7"),
    ]
    for col, val, lbl, clr in kpis:
        col.markdown(f"""
        <div class="kpi">
          <div class="v" style="color:{clr}">{val}</div>
          <div class="l">{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Source météo
    if meteo_rt:
        st.info(f"📡 **Météo temps réel** — Agdez : T={meteo_rt['temperature']}°C | "
                f"H={meteo_rt['humidite']}% | P={meteo_rt['precipitation']}mm | "
                f"V={meteo_rt['vent']}m/s · Source : {meteo_rt['source']}")

    # ── ONGLETS ───────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "🗺️ Carte & Risque",
        "🌡️ Climatologie",
        "🔥 Incendie 2025",
        "🛰️ Indices Spectraux",
        "📋 Scénarios 2026",
        "🔔 Alertes",
        "🗓️ FVT",
        "🌍 Projections 2026–2035",
        "🧮 Comparateur",
        "📊 Modèle & Données",
    ])

    # =========================================================================
    # TAB 1 — Carte & Risque
    # =========================================================================
    with tabs[0]:
        col_map, col_info = st.columns([3, 1])
        with col_map:
            st.markdown('<div class="sec">Carte de risque — Agdez</div>', unsafe_allow_html=True)
            map_data = st_folium(
                make_map(risque, conf, probas, temperature, humidite, precipitation, vent, mois, annee),
                width="100%", height=490,
                returned_objects=["last_object_clicked"],
            )
        with col_info:
            clicked = (map_data and map_data.get("last_object_clicked") and
                       map_data["last_object_clicked"].get("lat") is not None)
            st.markdown(f'<div class="sec">{"📍 Cliqué" if clicked else "📍 Informations"}</div>',
                        unsafe_allow_html=True)
            st.markdown(f"""
            <div style="text-align:center;padding:15px;background:{'#fdf2f2' if risque in ['Élevé','Très élevé'] else '#eafaf1'};
                        border-radius:12px;border:2px solid {color};margin-bottom:12px">
              <div style="font-size:2.2rem">{RISQUE_EMOJI[risque]}</div>
              <div style="font-size:1.25rem;font-weight:800;color:{color}">{risque}</div>
              <div style="font-size:0.78rem;color:#666">{conf:.0%} confiance · {mois} {annee}</div>
            </div>""", unsafe_allow_html=True)
            st.plotly_chart(fig_proba_gauge(probas, risque), width="stretch",
                            config={"displayModeBar": False})
            # Info dynamique
            ind_sec = round((temperature - humidite) / (precipitation + 0.1), 2)
            st.markdown(f"""
            <div class="ibox" style="font-size:0.77rem;line-height:2.1;font-family:'Space Mono',monospace">
            📅 <b>{mois} {annee}</b><br>
            🌡️ <b>{temperature}°C</b><br>
            💧 <b>{humidite}%</b><br>
            🌧️ <b>{precipitation}mm</b><br>
            💨 <b>{vent}m/s</b><br>
            🌿 NDVI <b>{ndvi:.3f}</b><br>
            🔥 Ind. sécheresse <b>{ind_sec:.2f}</b><br>
            ⛰️ Alt. <b>{ALTITUDE}m</b><br>
            📐 Pente <b>{PENTE}°</b><br>
            🧭 Expo. <b>165.51° S-E</b>
            </div>""", unsafe_allow_html=True)
            # Probabilités barres
            st.markdown('<div class="sec" style="margin-top:10px">Probabilités</div>',
                        unsafe_allow_html=True)
            for cls, pb in probas.items():
                clr = RISQUE_COLOR.get(cls,"#888")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px">
                  <div style="width:78px;font-size:0.68rem;font-family:'Space Mono',monospace;color:#a0aec0">{cls}</div>
                  <div style="flex:1;background:#222;border-radius:3px;height:9px">
                    <div style="background:{clr};width:{pb*100:.0f}%;height:9px;border-radius:3px"></div>
                  </div>
                  <div style="width:34px;font-size:0.68rem;font-family:'Space Mono',monospace;color:#a0aec0;text-align:right">{pb:.0%}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="background:#111;border-radius:8px;padding:10px;margin-top:10px;
                        border-left:3px solid {color};font-size:0.8rem;line-height:1.6">
            {recommendation(risque)}
            </div>""", unsafe_allow_html=True)
            # Risque réel historique si disponible
            if annee <= 2025 and annee in RISQUES_REELS:
                rr = RISQUES_REELS[annee]
                cr = RISQUE_COLOR.get(rr,"#888")
                st.markdown(f"""
                <div style="background:#0d1a0d;border:1px solid #1a3a1a;border-radius:8px;
                            padding:8px 12px;margin-top:8px;font-size:0.78rem">
                ✅ <b>Risque réel observé {annee} :</b>
                <span style="color:{cr};font-weight:bold">{rr}</span>
                </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 2 — Climatologie
    # =========================================================================
    with tabs[1]:
        st.markdown('<div class="sec">Analyse climatique 2017–2035 (données réelles + projections)</div>',
                    unsafe_allow_html=True)

        df_proj = D["proj"]
        c1, c2  = st.columns(2)
        with c1:
            st.plotly_chart(fig_temp_humidity_full(df_proj), width="stretch")
        with c2:
            st.plotly_chart(fig_anomalies(), width="stretch")

        c3, c4  = st.columns(2)
        with c3:
            st.plotly_chart(fig_precipitations(), width="stretch")
        with c4:
            st.plotly_chart(fig_vent_hum(), width="stretch")

        c5, c6  = st.columns(2)
        with c5:
            st.plotly_chart(fig_ete_bars(), width="stretch")
        with c6:
            st.plotly_chart(fig_ombrothermique(), width="stretch")

        # Tableau données historiques
        st.markdown("---")
        st.markdown('<div class="sec">Données historiques annuelles (2017–2025)</div>',
                    unsafe_allow_html=True)
        df_hist = pd.DataFrame(HIST).T.reset_index().rename(columns={"index": "Année"})
        df_hist["Risque réel"] = df_hist["Année"].map(RISQUES_REELS)
        st.dataframe(df_hist.style.map(style_risque, subset=["Risque réel"])
                     .format({"temperature":"{:.2f}","humidite":"{:.2f}",
                              "precipitation":"{:.1f}","vent":"{:.2f}"}),
                     width="stretch")

    # =========================================================================
    # TAB 3 — Incendie 2025
    # =========================================================================
    with tabs[2]:
        st.markdown('<div class="sec">Incendie Agdez — 15 Septembre 2025</div>',
                    unsafe_allow_html=True)

        i1,i2,i3,i4,i5 = st.columns(5)
        i1.metric("Zone",             "Agdez (Drâa-Tafilalet)")
        i2.metric("Date",             "15 Sep. 2025")
        i3.metric("Surface brûlée",   "388.51 ha")
        i4.metric("% zone brûlée",    "5.96%")
        i5.metric("Surface totale",   "6 520.8 ha")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            # Classes sévérité — données exactes
            sev_data = pd.DataFrame({
                "Classe": ["Faible","Moyen","Fort","Très fort"],
                "Surface (ha)": [323.94, 60.42, 4.15, 0.0],
                "Pourcentage (%)": [4.97, 0.93, 0.06, 0.0],
                "Pixels": [32394, 6042, 415, 0],
            })
            st.plotly_chart(go.Figure(go.Pie(
                labels=sev_data["Classe"], values=sev_data["Surface (ha)"],
                hole=0.35,
                marker=dict(colors=[C["vert"],C["orange"],C["rouge"],"#8e1a1a"]),
                textinfo="label+percent+value",
                texttemplate="%{label}<br>%{value:.1f} ha (%{percent})",
            )).update_layout(title="Classes de sévérité — Incendie 2025", **DARK),
            width="stretch")
        with c2:
            fig_s = go.Figure(go.Bar(
                x=sev_data["Classe"], y=sev_data["Surface (ha)"],
                marker_color=[C["vert"],C["orange"],C["rouge"],"#8e1a1a"],
                text=[f"{v:.2f} ha\n({p:.2f}%)" for v,p in zip(sev_data["Surface (ha)"],sev_data["Pourcentage (%)"])],
                textposition="outside",
            ))
            fig_s.update_layout(title="Surface brûlée par classe (ha)", **DARK,
                                yaxis_title="ha", yaxis_range=[0,370])
            st.plotly_chart(fig_s, width="stretch")

        # Tableau récapitulatif
        st.markdown('<div class="sec" style="margin-top:14px">Tableau classes de sévérité</div>',
                    unsafe_allow_html=True)
        st.dataframe(sev_data, width="stretch")

        # Récapitulatif facteurs
        st.markdown("---")
        st.markdown('<div class="sec">Facteurs climatiques → Incendie</div>',
                    unsafe_allow_html=True)
        facteurs = [
            ("Température max (juillet)", "32.69°C", "Très haut", C["rouge"]),
            ("Humidité min (juillet)",    "16.42%",  "Favorise le feu", C["rouge"]),
            ("Vent max (juin)",           "4.50 m/s","Propagation", C["orange"]),
            ("Précipitations juillet",    "26.43 mm","Exceptionnel", C["orange"]),
            ("Surface brûlée",            "388.51 ha","Important", C["rouge"]),
            ("dNBR maximum",              "0.5928",  "Sévère", "#8e1a1a"),
        ]
        for fact, val, imp, clr in facteurs:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:8px 12px;
                        background:#16213e;border-radius:6px;margin-bottom:5px;
                        border-left:3px solid {clr}">
              <span style="font-size:0.83rem">{fact}</span>
              <span style="font-family:'Space Mono',monospace;font-size:0.83rem;font-weight:bold;color:#ddd">{val}</span>
              <span style="font-size:0.78rem;color:{clr}">{imp}</span>
            </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 4 — Indices Spectraux
    # =========================================================================
    with tabs[3]:
        st.markdown('<div class="sec">Indices spectraux NDVI · NBR · dNBR — Incendie 2025</div>',
                    unsafe_allow_html=True)

        # Données exactes
        indices_data = pd.DataFrame({
            "Indice": ["NDVI_avant","NDVI_après","dNBR"],
            "Moyenne":     [0.1443, 0.1167, 0.0248],
            "Minimum":    [-0.2090,-0.1119,-0.5661],
            "Maximum":    [ 0.8995, 0.8107, 0.5928],
            "Écart-type": [ 0.1447, 0.1275, 0.0522],
        })

        i1,i2,i3 = st.columns(3)
        i1.metric("NDVI avant",  "0.1443", "Max: 0.8995")
        i2.metric("NDVI après",  "0.1167", "-19.1% (perte)")
        i3.metric("dNBR max",    "0.5928", "Sévérité élevée")

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(fig_ndvi_bars(indices_data), width="stretch")
        with c2:
            st.plotly_chart(fig_dnbr_radar(indices_data), width="stretch")

        # Tableau complet
        st.markdown('<div class="sec" style="margin-top:12px">Statistiques indices spectraux</div>',
                    unsafe_allow_html=True)
        st.dataframe(indices_data.style.format({
            "Moyenne":"{:.4f}","Minimum":"{:.4f}",
            "Maximum":"{:.4f}","Écart-type":"{:.4f}",
        }), width="stretch")

        # Interprétation dNBR
        st.markdown("---")
        st.markdown('<div class="sec">Interprétation dNBR</div>', unsafe_allow_html=True)
        dnbr_classes = [
            ("<-0.10", "Régénération végétale",  C["vert"],   False),
            ("-0.10 – 0.10","Non brûlé",          "#a0aec0",  False),
            ("0.10 – 0.27","Sévérité faible",      C["orange"],False),
            ("0.27 – 0.44","Sévérité modérée",     "#e67e22",  False),
            ("0.44 – 0.66","Sévérité élevée ← Agdez 2025", C["rouge"], True),
            (">0.66",      "Sévérité très élevée", "#8e1a1a",  False),
        ]
        for rng, lbl, clr, active in dnbr_classes:
            brd = f"4px solid {clr}" if active else f"2px solid {clr}"
            st.markdown(f"""
            <div style="display:flex;gap:12px;padding:6px 10px;margin-bottom:4px;
                        background:#16213e;border-radius:5px;border-left:{brd}">
              <span style="font-family:'Space Mono',monospace;font-size:0.73rem;color:#a0aec0;width:115px">{rng}</span>
              <span style="font-size:0.8rem;color:{clr};{"font-weight:bold" if active else ""}">{lbl}</span>
            </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 5 — Scénarios 2026 (données exactes du modèle)
    # =========================================================================
    with tabs[4]:
        st.markdown('<div class="sec">Scénarios 2026 — Probabilités exactes du modèle Random Forest</div>',
                    unsafe_allow_html=True)
        df_sc = D["sc"]
        if df_sc is not None:
            # KPIs
            nb_te = (df_sc["risque_predit"]=="Très élevé").sum()
            nb_el = (df_sc["risque_predit"]=="Élevé").sum()
            nb_mo = (df_sc["risque_predit"]=="Moyen").sum()
            k1,k2,k3,k4 = st.columns(4)
            k1.metric("🔴 Très élevé", f"{nb_te}/10")
            k2.metric("🟠 Élevé",      f"{nb_el}/10")
            k3.metric("🟡 Moyen",      f"{nb_mo}/10")
            k4.metric("📊 Conf. moy.", f"{df_sc['confiance'].mean():.0%}")

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_scenarios_stack(df_sc), width="stretch")
            with c2:
                st.plotly_chart(fig_scenarios_conf(df_sc), width="stretch")

            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(fig_scenarios_heatmap(df_sc), width="stretch")
            with c4:
                st.plotly_chart(fig_scenarios_radar(df_sc), width="stretch")

            # Tableau complet
            st.markdown('<div class="sec" style="margin-top:10px">Tableau complet — données exactes</div>',
                        unsafe_allow_html=True)
            cats = ["Tous"] + sorted(df_sc["categorie"].unique().tolist())
            cat  = st.selectbox("Filtrer", cats)
            df_sh= df_sc if cat=="Tous" else df_sc[df_sc["categorie"]==cat]
            cols_d = ["categorie","scenario","mois","temperature","humidite",
                      "precipitation","vent","risque_predit","confiance",
                      "prob_faible","prob_moyen","prob_eleve","prob_tres_eleve"]
            st.dataframe(
                df_sh[cols_d].style
                .map(style_risque, subset=["risque_predit"])
                .format({"confiance":"{:.0%}","prob_faible":"{:.2%}",
                         "prob_moyen":"{:.2%}","prob_eleve":"{:.2%}",
                         "prob_tres_eleve":"{:.2%}"}),
                width="stretch", height=350,
            )
            st.download_button("⬇️ CSV scénarios complet",
                               data=df_sc.to_csv(index=False).encode("utf-8"),
                               file_name="scenarios_2026_complet.csv",
                               mime="text/csv")
        else:
            st.warning("⚠️ predictions_scenarios_2026.csv introuvable.")

    # =========================================================================
    # TAB 6 — Alertes dynamiques (avec envoi Email / Webhook)
    # =========================================================================
    with tabs[5]:
        st.markdown('<div class="sec">Alertes dynamiques — Email · Webhook · Sauvegarde JSON</div>',
                    unsafe_allow_html=True)

        # ── Statut configuration ──────────────────────────────────────────────
        erreurs_cfg = cfg_alertes.erreurs()
        if not cfg_alertes.email_actif and not cfg_alertes.webhook_actif:
            st.warning(
                "⚙️ **Aucun canal d'envoi activé.**\n\n"
                "Créez le fichier **`config_alertes.json`** dans votre dossier projet "
                "pour activer l'envoi par email et/ou webhook.",
                icon="⚠️",
            )
            exemple_cfg = {
                "email": {
                    "actif": True,
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "smtp_user": "votre.email@gmail.com",
                    "smtp_password": "mot_de_passe_application_google",
                    "destinataires": ["pompiers@agdez.ma", "commune@agdez.ma"],
                    "expediteur_nom": "Système Alerte Incendie Agdez"
                },
                "webhook": {
                    "actif": False,
                    "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
                    "type": "slack"
                },
                "options": {
                    "cooldown_minutes": 60,
                    "sauvegarder_json": True,
                    "repertoire_rapports": "reports"
                }
            }
            st.download_button(
                "⬇️ Télécharger config_alertes.json (modèle à remplir)",
                data=json.dumps(exemple_cfg, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="config_alertes.json",
                mime="application/json",
            )
        elif erreurs_cfg:
            st.error("❌ Configuration incomplète : " + " · ".join(erreurs_cfg))
        else:
            canaux = []
            if cfg_alertes.email_actif:
                canaux.append(f"📧 Email → {', '.join(cfg_alertes.destinataires)}")
            if cfg_alertes.webhook_actif:
                canaux.append(f"🔗 Webhook ({cfg_alertes.webhook_type})")
            st.success("✅ Canaux actifs : " + " · ".join(canaux))

        st.markdown("---")

        # ── Alerte courante ───────────────────────────────────────────────────
        st.markdown("**🔴 Alerte courante (basée sur les sliders)**")
        if risque in ["Élevé","Très élevé"]:
            prio    = "CRITIQUE" if risque=="Très élevé" else "HAUTE"
            css     = "alert-r"  if risque=="Très élevé" else "alert-o"
            tag_css = "tag-r"    if risque=="Très élevé" else "tag-o"
            st.markdown(f"""
            <div class="{css}">
              <span class="tag {tag_css}">⚡ {prio}</span>
              <div style="font-weight:700;font-size:0.95rem;margin:5px 0">
                {RISQUE_EMOJI[risque]} Risque {risque} — {mois} {annee}
              </div>
              <div style="font-size:0.82rem;color:#ddd;line-height:1.8">
                📍 Zone : Agdez, Maroc<br>
                📊 Confiance : <b>{conf:.0%}</b><br>
                🌡️ T={temperature}°C | 💧 H={humidite}% | 🌧️ P={precipitation}mm | 💨 V={vent}m/s<br>
                🕐 Généré : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br>
                💬 <b>{recommendation(risque)}</b>
              </div>
            </div>""", unsafe_allow_html=True)

            col_envoyer, col_simuler, col_info = st.columns([1, 1, 2])
            with col_envoyer:
                if st.button("📤 Envoyer l'alerte", type="primary", key="btn_envoyer_courant"):
                    with st.spinner("⏳ Envoi en cours…"):
                        res = envoyer_alerte(
                            cfg_alertes, risque, conf,
                            temperature, humidite, precipitation, vent,
                            mois, annee, probas, recommendation(risque),
                        )
                    if res.get("email"):
                        if res["email"]["succes"]:
                            st.success(f"✅ Email envoyé → {res['email']['destinataires']}")
                        else:
                            st.error(res["email"]["erreur"])
                    if res.get("webhook"):
                        if res["webhook"]["succes"]:
                            st.success("✅ Webhook envoyé")
                        else:
                            st.error(res["webhook"]["erreur"])
                    if res.get("json") and res["json"]["succes"]:
                        st.info(f"💾 Sauvegardée : {res['json']['fichier']}")

            with col_simuler:
                if st.button("🧪 Simuler (voir JSON)", key="btn_simuler_courant"):
                    st.json({
                        "priorite": prio, "risque": risque,
                        "confiance": f"{conf:.0%}", "periode": f"{mois} {annee}",
                        "conditions": {"temperature": temperature, "humidite": humidite,
                                       "precipitation": precipitation, "vent": vent},
                        "probabilites": {k: f"{v:.0%}" for k, v in probas.items()},
                        "recommandation": recommendation(risque),
                    })
            with col_info:
                st.caption(
                    f"📧 Email : {'✅' if cfg_alertes.email_actif else '❌'}  |  "
                    f"🔗 Webhook : {'✅' if cfg_alertes.webhook_actif else '❌'}  |  "
                    f"💾 JSON : {'✅' if cfg_alertes.sauvegarder_json else '❌'}"
                )
        else:
            st.success(f"✅ Risque **{risque}** — Aucune alerte requise pour les conditions actuelles.")

        # ── Scénarios 2026 ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Alertes générées par les 10 scénarios 2026**")
        df_sc = D["sc"]
        if df_sc is not None:
            alerts_2026 = df_sc[df_sc["risque_predit"].isin(["Élevé","Très élevé"])]
            st.markdown(f"**{len(alerts_2026)} scénarios** sur 10 déclenchent une alerte.")
            for idx, r in alerts_2026.iterrows():
                css_sc  = "alert-r" if r["risque_predit"]=="Très élevé" else "alert-o"
                tcss_sc = "tag-r"   if r["risque_predit"]=="Très élevé" else "tag-o"
                prio_sc = "CRITIQUE" if r["risque_predit"]=="Très élevé" else "HAUTE"
                st.markdown(f"""
                <div class="{css_sc}">
                  <span class="tag {tcss_sc}">⚡ {prio_sc}</span>
                  <div style="font-weight:700;font-size:0.87rem;margin:3px 0">{r['scenario']}</div>
                  <div style="font-size:0.8rem;color:#aaa;line-height:1.7">
                    {r['risque_predit']} · Confiance {r['confiance']:.0%}
                    | T={r['temperature']}°C H={r['humidite']}% P={r['precipitation']}mm V={r['vent']}m/s<br>
                    Prob. Très élevé: <b>{r['prob_tres_eleve']:.0%}</b>
                    | Élevé: {r['prob_eleve']:.0%}
                  </div>
                </div>""", unsafe_allow_html=True)
                if st.button(f"📤 Envoyer — {r['scenario']}", key=f"btn_sc_{idx}"):
                    with st.spinner("Envoi…"):
                        res_sc = envoyer_alerte(
                            cfg_alertes, r["risque_predit"], r["confiance"],
                            r["temperature"], r["humidite"],
                            r["precipitation"], r["vent"], mois, annee,
                            {"Faible": r.get("prob_faible",0), "Moyen": r.get("prob_moyen",0),
                             "Élevé": r.get("prob_eleve",0), "Très élevé": r.get("prob_tres_eleve",0)},
                            recommendation(r["risque_predit"]), scenario=r["scenario"],
                        )
                    if res_sc.get("email", {}).get("succes"):
                        st.success(f"✅ Email envoyé — {r['scenario']}")
                    elif res_sc.get("json", {}).get("succes"):
                        st.info(f"💾 Sauvegardée : {res_sc['json']['fichier']}")
                    elif res_sc.get("email"):
                        st.error(res_sc["email"]["erreur"])

        # ── Archive JSON ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Archive alertes historiques (JSON)**")
        alertes = D["alertes"]
        if alertes:
            for a in alertes:
                prio = a.get("priorite","")
                css  = "alert-r" if prio=="CRITIQUE" else "alert-o"
                tcss = "tag-r"   if prio=="CRITIQUE" else "tag-o"
                try:
                    ts = datetime.fromisoformat(a.get("timestamp","")).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    ts = a.get("timestamp","—")
                st.markdown(f"""
                <div class="{css}" style="opacity:0.8">
                  <span class="tag {tcss}">📁 {prio}</span>
                  <div style="font-size:0.85rem;font-weight:600;margin:3px 0">{a.get('scenario','—')}</div>
                  <div style="font-size:0.78rem;color:#aaa">
                    {a.get('risque','')} · {a.get('confiance',0):.0%} · {ts}
                  </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Aucun fichier alerte JSON trouvé dans reports/")

    # =========================================================================
    # TAB 7 — FVT
    # =========================================================================
    with tabs[6]:
        st.markdown('<div class="sec">Fenêtre de Vulnérabilité Temporelle — Été 2026</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        > **Concept original** : simulation journalière des 92 jours d'été
        > pour identifier les *fenêtres continues* de risque critique —
        > outil de planification des ressources de surveillance terrain.
        """)
        with st.spinner("Simulation 92 jours…"):
            fig_fvt_chart, df_fvt = fig_fvt(model, le)
        st.plotly_chart(fig_fvt_chart, width="stretch")

        n_te = (df_fvt["risque"]=="Très élevé").sum()
        n_el = (df_fvt["risque"]=="Élevé").sum()
        n_cr = n_te + n_el
        v1,v2,v3,v4 = st.columns(4)
        v1.metric("🔴 Très élevé",   n_te)
        v2.metric("🟠 Élevé",        n_el)
        v3.metric("⚠️ Critiques",    n_cr)
        v4.metric("✅ Sûrs",         92-n_cr)

        # Calcul fenêtres
        st.markdown("---")
        st.markdown('<div class="sec">Fenêtres continues identifiées</div>',
                    unsafe_allow_html=True)
        df_fvt["is_c"] = df_fvt["risque"].isin(["Élevé","Très élevé"])
        wins, in_w, start = [], False, None
        for _, r in df_fvt.iterrows():
            if r["is_c"] and not in_w:
                in_w, start = True, r["date"]
            elif not r["is_c"] and in_w:
                in_w = False
                wins.append({"Début":start.strftime("%d/%m/%Y"),
                             "Fin":(r["date"]-pd.Timedelta(days=1)).strftime("%d/%m/%Y"),
                             "Durée (jours)":(r["date"]-start).days})
        if in_w:
            wins.append({"Début":start.strftime("%d/%m/%Y"),
                         "Fin":df_fvt["date"].iloc[-1].strftime("%d/%m/%Y"),
                         "Durée (jours)":(df_fvt["date"].iloc[-1]-start).days+1})
        if wins:
            df_w = pd.DataFrame(wins).sort_values("Durée (jours)", ascending=False)
            st.dataframe(df_w, width="stretch")
            st.error(f"⚠️ Fenêtre principale : **{df_w.iloc[0]['Début']} → {df_w.iloc[0]['Fin']}** "
                     f"= **{df_w.iloc[0]['Durée (jours)']} jours consécutifs**")

        # Box plot T par risque
        fig_bx = px.box(df_fvt, x="risque", y="temperature", color="risque",
                        color_discrete_map=RP,
                        title="Distribution température par niveau de risque — Été 2026",
                        category_orders={"risque":["Faible","Moyen","Élevé","Très élevé"]})
        fig_bx.update_layout(**DARK, showlegend=False)
        st.plotly_chart(fig_bx, width="stretch")

    # =========================================================================
    # TAB 8 — Projections 2026-2035 (données exactes CSV modèle)
    # =========================================================================
    with tabs[7]:
        st.markdown('<div class="sec">Projections 2026–2035 — Probabilités exactes du modèle</div>',
                    unsafe_allow_html=True)
        df_proj = D["proj"]
        if df_proj is not None:
            # KPIs
            pk1,pk2,pk3,pk4,pk5 = st.columns(5)
            pk1.metric("T° 2026",       f"{df_proj.iloc[0]['temperature']:.1f}°C")
            pk2.metric("T° 2035",       f"{df_proj.iloc[-1]['temperature']:.1f}°C",
                       f"+{df_proj.iloc[-1]['temperature']-df_proj.iloc[0]['temperature']:.1f}°C")
            pk3.metric("H% 2026",       f"{df_proj.iloc[0]['humidite']:.1f}%")
            pk4.metric("H% 2035",       f"{df_proj.iloc[-1]['humidite']:.1f}%",
                       f"{df_proj.iloc[-1]['humidite']-df_proj.iloc[0]['humidite']:.1f}%")
            pk5.metric("P(>Élevé) min", f"{(df_proj['prob_eleve']+df_proj['prob_tres_eleve']).min():.0%}")

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_proj_temp(df_proj), width="stretch")
            with c2:
                st.plotly_chart(fig_proj_prob_evol(df_proj), width="stretch")

            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(fig_proj_heatmap(df_proj), width="stretch")
            with c4:
                # Précipitations projetées
                fig_pp = go.Figure(go.Bar(
                    x=df_proj["annee"], y=df_proj["precipitation"],
                    marker_color="#3498db",
                    text=[f"{v:.1f}" for v in df_proj["precipitation"]],
                    textposition="outside",
                ))
                fig_pp.update_layout(title="Précipitations projetées juillet (mm)",
                                     **DARK, yaxis_title="mm")
                st.plotly_chart(fig_pp, width="stretch")

            # Tableau complet données exactes
            st.markdown('<div class="sec" style="margin-top:10px">Tableau — toutes les probabilités exactes</div>',
                        unsafe_allow_html=True)
            st.dataframe(
                df_proj.style
                .map(style_risque, subset=["risque_predit"])
                .format({"temperature":"{:.3f}°C","humidite":"{:.3f}%",
                         "precipitation":"{:.3f}mm","vent":"{:.4f}m/s",
                         "confiance":"{:.3f}","prob_faible":"{:.4f}",
                         "prob_moyen":"{:.4f}","prob_eleve":"{:.4f}",
                         "prob_tres_eleve":"{:.4f}"}),
                width="stretch",
            )
            st.download_button("⬇️ Projections complètes (.csv)",
                               data=df_proj.to_csv(index=False).encode("utf-8"),
                               file_name="projections_2026_2035.csv", mime="text/csv")
        else:
            st.warning("⚠️ projections_climatiques.csv introuvable.")

    # =========================================================================
    # TAB 9 — Comparateur d'années
    # =========================================================================
    with tabs[8]:
        st.markdown('<div class="sec">Comparateur d\'années 2017–2035</div>',
                    unsafe_allow_html=True)
        df_proj = D["proj"]

        all_years = list(range(2017, 2036))
        ca1, ca2  = st.columns(2)
        with ca1:
            yr_a = st.selectbox("Année A", all_years, index=9, key="cmp_a")
        with ca2:
            yr_b = st.selectbox("Année B", all_years, index=18, key="cmp_b")

        def get_year_data(yr):
            """Retourne (t,h,p,v,risque,conf,probas) pour une année."""
            if yr <= 2025:
                h = HIST.get(yr, HIST[2025])
                # Données juillet
                t, hum, p, v = h["temperature"]+9.0, h["humidite"]-12.0, h["precipitation"]/3, h["vent"]
                risque_r, conf_r, probas_r = ml_predict(model, le, t, hum, p, v, 1)
                return t, hum, p, v, risque_r, conf_r, probas_r
            elif df_proj is not None:
                row = df_proj[df_proj["annee"]==yr]
                if not row.empty:
                    r = row.iloc[0]
                    return (r["temperature"], r["humidite"], r["precipitation"], r["vent"],
                            r["risque_predit"], r["confiance"],
                            {"Faible":r["prob_faible"],"Moyen":r["prob_moyen"],
                             "Élevé":r["prob_eleve"],"Très élevé":r["prob_tres_eleve"]})
            return 32.0, 16.0, 10.0, 4.0, "—", 0.0, {}

        ta,ha,pa,va,la,ca_v,pa_d = get_year_data(yr_a)
        tb,hb,pb,vb,lb,cb,pb_d   = get_year_data(yr_b)

        def year_card(col, yr, t, h, p, v, lbl, cnf, probas_d):
            c_clr = RISQUE_COLOR.get(lbl,"#888")
            col.markdown(f"""
            <div style="text-align:center;padding:14px;background:#16213e;
                        border-radius:12px;border:2px solid {c_clr};margin-bottom:12px">
              <div style="font-size:1.8rem">{RISQUE_EMOJI.get(lbl,'⚪')}</div>
              <div style="font-size:1.5rem;font-weight:800;color:{c_clr}">{yr}</div>
              <div style="font-size:0.95rem;color:{c_clr};font-weight:600">{lbl}</div>
              <div style="font-size:0.75rem;color:#666">{cnf:.0%} confiance</div>
            </div>""", unsafe_allow_html=True)
            for lbl_v, val in [("🌡️ T°C",f"{t:.1f}°C"),("💧 H%",f"{h:.1f}%"),
                                ("🌧️ P mm",f"{p:.1f}mm"),("💨 V m/s",f"{v:.2f}m/s")]:
                col.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:5px 8px;
                            background:#0d0d1a;border-radius:5px;margin-bottom:4px;
                            font-family:'Space Mono',monospace;font-size:0.73rem">
                  <span style="color:#a0aec0">{lbl_v}</span>
                  <span style="color:#ddd;font-weight:bold">{val}</span>
                </div>""", unsafe_allow_html=True)
            # Probabilités
            if probas_d:
                for cls, pb_v in probas_d.items():
                    clr = RISQUE_COLOR.get(cls,"#888")
                    col.markdown(f"""
                    <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px">
                      <div style="width:72px;font-size:0.65rem;font-family:'Space Mono',monospace;color:#a0aec0">{cls}</div>
                      <div style="flex:1;background:#222;border-radius:2px;height:7px">
                        <div style="background:{clr};width:{pb_v*100:.0f}%;height:7px;border-radius:2px"></div>
                      </div>
                      <div style="font-size:0.65rem;font-family:'Space Mono',monospace;color:#a0aec0;width:32px;text-align:right">{pb_v:.0%}</div>
                    </div>""", unsafe_allow_html=True)

        col_a, col_sep, col_b = st.columns([5,1,5])
        year_card(col_a, yr_a, ta, ha, pa, va, la, ca_v, pa_d)
        col_sep.markdown("<div style='text-align:center;padding-top:70px;font-size:1.3rem;color:#a0aec0'>VS</div>",
                         unsafe_allow_html=True)
        year_card(col_b, yr_b, tb, hb, pb, vb, lb, cb, pb_d)

        # Graphique comparatif
        fig_cmp = go.Figure()
        fig_cmp.add_trace(go.Bar(name=str(yr_a), x=["T(°C)","H(%)","P(mm)","V(m/s)"],
                                  y=[ta,ha,pa,va],
                                  marker_color=RISQUE_COLOR.get(la,"#888"),
                                  text=[f"{ta:.1f}",f"{ha:.1f}",f"{pa:.1f}",f"{va:.2f}"],
                                  textposition="outside"))
        fig_cmp.add_trace(go.Bar(name=str(yr_b), x=["T(°C)","H(%)","P(mm)","V(m/s)"],
                                  y=[tb,hb,pb,vb],
                                  marker_color=RISQUE_COLOR.get(lb,"#555"),
                                  text=[f"{tb:.1f}",f"{hb:.1f}",f"{pb:.1f}",f"{vb:.2f}"],
                                  textposition="outside"))
        fig_cmp.update_layout(title=f"Comparaison juillet — {yr_a} vs {yr_b}",
                              barmode="group", **DARK)
        st.plotly_chart(fig_cmp, width="stretch")

        # Deltas
        st.markdown('<div class="sec">Évolution entre les deux années</div>',
                    unsafe_allow_html=True)
        d1,d2,d3,d4 = st.columns(4)
        for col_d, nm, va_v, vb_v, u in [
            (d1,"🌡️ Température",ta,tb,"°C"),
            (d2,"💧 Humidité",   ha,hb,"%"),
            (d3,"🌧️ Pluie",      pa,pb,"mm"),
            (d4,"💨 Vent",       va,vb,"m/s"),
        ]:
            col_d.metric(nm, f"{vb_v:.1f}{u}", f"{vb_v-va_v:+.1f}{u}")

    # =========================================================================
    # TAB 10 — Modèle & Données
    # =========================================================================
    with tabs[9]:
        st.markdown('<div class="sec">Modèle Random Forest · Feature Importance · Données brutes</div>',
                    unsafe_allow_html=True)

     
        mi = D["mi"]
        df_fi_data = D["fi"]

        if mi:
            m1,m2,m3,m4,m5 = st.columns(5)
            m1.metric("Algorithme",   mi.get("modele","—"))
            m2.metric("Accuracy CV",  f"{mi.get('accuracy_cv',0):.1%}")
            m3.metric("Écart-type",   f"±{mi.get('accuracy_cv_std',0):.1%}")
            m4.metric("Train",        mi.get("annees_train","—"))
            m5.metric("Version",      mi.get("version","—"))

            feats   = mi.get("features", [])
            classes = mi.get("classes", [])
            feat_html  = " · ".join([f"<code style='background:#1a2a3a;padding:1px 5px;border-radius:3px;font-size:0.75rem'>{f}</code>" for f in feats])
            class_html = " · ".join([f"<span style='color:{RP.get(c,'#888')};font-weight:bold'>{c}</span>" for c in classes])
            st.markdown(f"""
            <div class="ibox" style="font-size:0.79rem;line-height:2">
            <b>Features ({len(feats)}) :</b> {feat_html}<br>
            <b>Classes ({len(classes)}) :</b> {class_html}
            </div>""", unsafe_allow_html=True)

        if df_fi_data is not None:
            st.markdown("---")
            c1, c2 = st.columns([3,1])
            with c1:
                st.plotly_chart(fig_fi(df_fi_data), use_container_width=True)
            with c2:
                st.plotly_chart(fig_fi_pie(df_fi_data), use_container_width=True)

            df_fi_d = df_fi_data.copy()
            df_fi_d["importance_%"] = df_fi_d["importance"] * 100
            st.dataframe(
                df_fi_d.style
                .format({"importance":"{:.6f}","importance_%":"{:.2f}%"})
                .background_gradient(subset=["importance"], cmap="Reds"),
                use_container_width=True
            )

        # Explorer données
        st.markdown("---")
        st.markdown('<div class="sec">Explorer & télécharger les données</div>',
                    unsafe_allow_html=True)
        sources = {
            "Scénarios 2026":           D["sc"],
            "Projections 2026–2035":    D["proj"],
            "Feature importance":       D["fi"],
            "Données annuelles":        D["ann"],
            "Conditions été 2025":      D["ete"],
            "Récap incendie":           D["recap"],
        }
        chosen = st.selectbox("Dataset", list(sources.keys()))
        df_ch  = sources[chosen]
        if df_ch is not None:
            st.dataframe(df_ch, use_container_width=True)
            st.download_button(
                f"⬇️ {chosen}",
                data=df_ch.to_csv(index=False).encode("utf-8"),
                file_name=f"{chosen[:30].replace(' ','_')}.csv",
                mime="text/csv"
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center;font-size:0.65rem;color:#a0aec0;padding:8px 0">
        🔥 Agdez Wildfire Prediction System · Random Forest v1.0.0 ·
        Données 2017–2025 · Drâa-Tafilalet, Maroc 🇲🇦 ·
        Mis à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()