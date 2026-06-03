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
INCENDIE = BASE / "dashboard" / "data_" / "satellite _image"
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
    border-radius:10px;
    overflow:hidden;
    border:1px solid #2a3a5c;
}
[data-testid="stDataFrame"] table td,
[data-testid="stDataFrame"] table th{
    color:#e2e8f0 !important;
    font-size:0.78rem;
}
[data-testid="stDataFrame"] table th{
    background:#0d1a2d !important;
    color:#f8fafc !important;
    font-weight:700;
}
[data-testid="stDataFrame"] table td{
    background:#0a1628 !important;
}
[data-testid="stDataFrame"] table tr:nth-child(even) td{
    background:#0f1f35 !important;
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

    resultats = {}

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
    label  = str(le.inverse_transform([y])[0])
    return label, float(probas.max()), {str(c): float(pb) for c, pb in zip(le.classes_, probas)}

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
        model = joblib.load("models/trained/model_risque_incendie.pkl")
        le    = joblib.load("models/trained/label_encoder.pkl")
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

def hex2rgba(h: str, a: float = 0.15) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[:2],16)},{int(h[2:4],16)},{int(h[4:],16)},{a})"

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


def fig_temp_humidity_full(df_proj):
    """Température + humidité 2017–2035 (historique + projections)."""
    annees_h = list(HIST.keys())
    temps_h  = [HIST[a]["temperature"] for a in annees_h]
    hum_h    = [HIST[a]["humidite"]    for a in annees_h]
    annees_p = df_proj["annee"].tolist()
    temps_p  = df_proj["temperature"].tolist()
    hum_p    = df_proj["humidite"].tolist()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=annees_h, y=temps_h, name="T° historique",
        mode="lines+markers", line=dict(color=C["rouge"], width=3),
        marker=dict(size=9), text=[f"{v:.2f}°C" for v in temps_h],
        textposition="top center", textfont=dict(size=8.5)), secondary_y=False)
    fig.add_trace(go.Scatter(x=[annees_h[-1]]+annees_p, y=[temps_h[-1]]+temps_p,
        name="T° projetée", mode="lines+markers",
        line=dict(color=C["rouge"], width=2.5, dash="dash"),
        marker=dict(size=8, symbol="diamond"),
        text=[""]+[f"{v:.1f}°C" for v in temps_p],
        textposition="top center", textfont=dict(size=8)), secondary_y=False)
    fig.add_trace(go.Scatter(x=annees_h, y=hum_h, name="H% historique",
        mode="lines+markers", line=dict(color=C["bleu"], width=2),
        marker=dict(size=7)), secondary_y=True)
    fig.add_trace(go.Scatter(x=[annees_h[-1]]+annees_p, y=[hum_h[-1]]+hum_p,
        name="H% projetée", mode="lines",
        line=dict(color=C["bleu"], width=1.8, dash="dot")), secondary_y=True)
    fig.add_vrect(x0=2025.5, x1=2035.5, fillcolor="rgba(255,100,0,0.05)",
                  layer="below", line_width=0,
                  annotation_text="Projections →", annotation_position="top left",
                  annotation_font_color="#f77f00")
    fig.update_layout(title="Évolution climatique 2017–2035", **DARK,
                      legend=dict(orientation="h", y=1.12))
    fig.update_yaxes(title_text="Température (°C)", secondary_y=False, color=C["rouge"])
    fig.update_yaxes(title_text="Humidité (%)", secondary_y=True, color=C["bleu"])
    return fig


def fig_anomalies():
    """Anomalies de température estivale (référence 2017-2024)."""
    annees = list(HIST.keys())
    temps  = [HIST[a]["temperature"] for a in annees]
    ref    = np.mean(temps[:-1])
    anom   = [t - ref for t in temps]
    colors = [C["rouge"] if a >= 0 else "#3498db" for a in anom]
    fig = go.Figure(go.Bar(x=annees, y=anom, marker_color=colors,
                           text=[f"{a:+.2f}°C" for a in anom], textposition="outside"))
    fig.add_hline(y=0, line_color="white", line_width=1.5)
    fig.update_layout(title=f"Anomalies T° estivale (réf. 2017-2024 · moy={ref:.2f}°C)",
                      yaxis_title="Écart (°C)", **DARK)
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


def fig_ombrothermique():
    """Diagramme ombrothermique Agdez 2025."""
    mois = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
    prec = [0.8, 5.1, 6.0, 18.7, 1.1, 2.85, 26.43, 0.18, 0.05, 0.0, 2.0, 31.0]
    temp = [9.3, 11.5, 14.0, 19.0, 22.1, 29.3, 32.7, 31.4, 26.0, 21.5, 15.1, 8.5]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=mois, y=prec, name="Précipitations (mm)",
                         marker_color="#3498db", opacity=0.75), secondary_y=False)
    fig.add_trace(go.Scatter(x=mois, y=temp, name="Température (°C)",
                             mode="lines+markers", line=dict(color=C["rouge"], width=3),
                             marker=dict(size=9, color=C["rouge"])), secondary_y=True)
    fig.update_layout(title="Diagramme ombrothermique — Agdez 2025", **DARK)
    fig.update_yaxes(title_text="Précipitations (mm)", secondary_y=False, color="#3498db")
    fig.update_yaxes(title_text="Température (°C)", secondary_y=True, color=C["rouge"])
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


def fig_severity_pie(df):
    """Camembert classes de sévérité incendie 2025."""
    if df is None or df.empty:
        return None
    df2 = df[df["Classe"] > 0] if "Classe" in df.columns else df.iloc[1:]
    lbl = df2.iloc[:, 1].tolist() if df2.shape[1] > 1 else ["Faible","Moyen","Fort"]
    val = df2["Surface (ha)"].tolist() if "Surface (ha)" in df2.columns else [323.94, 60.42, 4.15]
    fig = go.Figure(go.Pie(
        labels=lbl, values=val, hole=0.35,
        marker=dict(colors=[C["vert"],C["orange"],C["rouge"],"#8e1a1a"]),
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
        fill="toself", fillcolor=hex2rgba(C["rouge"], 0.15),
    ))
    fig.update_layout(
        title="Radar NDVI/dNBR",
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
    """Évolution probabilités 2026-2035."""
    fig = go.Figure()
    for col, lbl, col_r, dash in [
        ("prob_tres_eleve","Très élevé","#8e1a1a","solid"),
        ("prob_eleve",     "Élevé",     "#e74c3c","dot"),
        ("prob_moyen",     "Moyen",     "#e67e22","dash"),
        ("prob_faible",    "Faible",    "#27ae60","longdash"),
    ]:
        fig.add_trace(go.Scatter(
            x=df["annee"], y=df[col]*100, name=lbl,
            mode="lines+markers", line=dict(color=col_r, width=2.5, dash=dash),
            marker=dict(size=9), text=[f"{v:.0%}" for v in df[col]],
            hovertemplate=f"<b>{lbl}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
    fig.update_layout(title="Évolution probabilités par classe — 2026→2035",
                      yaxis_title="%", legend=dict(orientation="h", y=1.12), **DARK)
    return fig


def fig_proj_heatmap(df):
    """Heatmap probabilités 2026-2035."""
    prob_m = df[["prob_faible","prob_moyen","prob_eleve","prob_tres_eleve"]].values * 100
    fig = go.Figure(go.Heatmap(
        z=prob_m, x=["Faible","Moyen","Élevé","Très élevé"],
        y=[str(int(a)) for a in df["annee"]],
        colorscale=[[0,"#0d3020"],[0.33,"#3d3000"],[0.66,"#3d1e00"],[1.0,"#3d0000"]],
        text=[[f"{v:.0f}%" for v in row] for row in prob_m],
        texttemplate="%{text}", showscale=True,
        colorbar=dict(title="Prob (%)", thickness=12),
    ))
    fig.update_layout(title="Heatmap probabilités — Projections juillet 2026–2035",
                      **DARK, height=360)
    return fig


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
    folium.CircleMarker(location=[LAT, LON], radius=16, color=color,
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
    model, le = load_model()
    D         = load_data()
    meteo_rt  = fetch_meteo_realtime()
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

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="app-hdr">
      <h1>🔥 Agdez · Prédiction Risque Incendie de Forêt</h1>
      <p>Drâa-Tafilalet, Maroc · 30.69°N 6.45°W · Alt. {ALTITUDE} m · Pente {PENTE}° ·
         Random Forest v1.0.0 · Données 2017–2025 · Incendie 15 Sep. 2025</p>
    </div>""", unsafe_allow_html=True)

    # ── ONGLETS ───────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "🧠 Centre Opérationnel",
        "🌡️ Climatologie & Tendances",
        "🛰️ Télédétection & Analyse",
        "🤖 IA & Modèle",
        "🔔 Alertes",
    ])

    # =========================================================================
    # TAB 0 — Centre Opérationnel (pipeline complet)
    # =========================================================================
    with tabs[0]:
        st.markdown('<div class="sec">① Monitoring Temps Réel</div>', unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("🌡️ Température", f"{temperature}°C")
        c2.metric("💧 Humidité", f"{humidite}%")
        c3.metric("💨 Vent", f"{vent} m/s")
        c4.metric("🌧️ Précipitations", f"{precipitation} mm")
        if meteo_rt:
            st.caption(f"📡 Source : {meteo_rt['source']} · {datetime.now().strftime('%d/%m/%Y %H:%M')} · Ajustable dans la barre latérale")
        else:
            st.caption("💡 Mode simulation — ajustez les valeurs dans la barre latérale")

        st.markdown("---")
        st.markdown('<div class="sec">② Prédiction ML</div>', unsafe_allow_html=True)
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(f'<div class="kpi"><div class="v" style="color:{color}">{RISQUE_EMOJI[risque]} {risque}</div><div class="l">Risque prédit · {mois} {annee}</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="kpi"><div class="v" style="color:#3498db">{conf:.0%}</div><div class="l">Confiance modèle</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="kpi"><div class="v" style="color:#f39c12">{temperature}°C · {humidite}%</div><div class="l">T° & Humidité</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="kpi"><div class="v" style="color:#06b6d4">{precipitation}mm · {vent}m/s</div><div class="l">Pluie & Vent</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="sec" style="margin-top:-8px">Probabilités par classe</div>', unsafe_allow_html=True)
        cols_p = st.columns(4)
        for cls, pb in probas.items():
            clr = RISQUE_COLOR.get(cls,"#888")
            idx = ["Faible","Moyen","Élevé","Très élevé"].index(cls)
            cols_p[idx].markdown(f'<div style="background:#16213e;border-radius:8px;padding:8px;text-align:center;border-bottom:3px solid {clr}"><div style="font-size:0.7rem;color:#a0aec0">{cls}</div><div style="font-size:1.2rem;font-weight:700;color:{clr}">{pb:.0%}</div></div>', unsafe_allow_html=True)

        st.plotly_chart(fig_proba_gauge(probas, risque), use_container_width=True, config={"displayModeBar":False})

        st.markdown("---")
        st.markdown('<div class="sec">③ Carte de situation — Folium</div>', unsafe_allow_html=True)
        with st.spinner("🔄 Chargement de la carte interactive…"):
            folium_map = make_map(risque, conf, probas, temperature, humidite, precipitation, vent, mois, annee)
            st_folium(folium_map, width=None, height=450, key="folium_map_op")
        st.caption(f"Carte centrée sur Agdez (30.69°N, 6.45°W) · Cercle de 5 km · Niveau de risque : {risque}")

        st.markdown("---")
        st.markdown('<div class="sec">④ Analyse IA de la situation</div>', unsafe_allow_html=True)

        ai_result = st.session_state.get("ai_result")
        force_refresh = st.button("🔄 Actualiser l'analyse IA", type="secondary", key="refresh_ai")
        if force_refresh or ai_result is None:
            with st.spinner("🧠 Analyse IA en cours…"):
                try:
                    from src.ai.llm_service import analyse_ia
                    prompt_data = {
                        "temperature": temperature, "humidite": humidite,
                        "precipitation": precipitation, "vent": vent,
                        "ndvi": ndvi, "risque": risque, "confiance": conf,
                        "probas": probas, "mois": mois, "annee": annee,
                        "altitude": ALTITUDE, "pente": PENTE,
                    }
                    ai_result = analyse_ia(prompt_data)
                except Exception as e:
                    ai_result = {"erreur": str(e), "fallback": True}
                st.session_state["ai_result"] = ai_result

        if ai_result and ai_result.get("erreur") and ai_result.get("fallback"):
            if ai_result.get("quota_exceeded"):
                st.warning("⚠️ Gemini API connected but quota exceeded. Switching to local expert system.")
            else:
                st.warning(f"⚠️ API IA indisponible. Utilisation du système expert local. ({ai_result['erreur']})")
            from src.ai.explanator import analyser_risque, generer_explication
            from src.ai.awareness import generer_message_population
            from src.ai.bulletin import generer_bulletin
            analyse = analyser_risque(temperature, humidite, precipitation, vent, ndvi, risque)
            explication = generer_explication(analyse)
            awareness = generer_message_population(risque, temperature, vent)
            bulletin = generer_bulletin(risque, conf, temperature, humidite, precipitation, vent, ndvi, mois, annee, probas)
            st.markdown(f'<div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.9rem;font-weight:700;color:#f39c12;margin-bottom:8px">📋 Bulletin Opérationnel</div><div style="font-size:0.8rem;color:#cbd5e1;line-height:1.8"><b>Risque :</b> <span style="color:{color};font-weight:bold">{risque}</span> · <b>Confiance :</b> {conf:.0%}<br><b>Conditions :</b> T={temperature}°C · H={humidite}% · P={precipitation}mm · V={vent}m/s<br><b>NDVI :</b> {ndvi:.4f}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="background:#0a1a2a;border:1px solid #1a3a5c;border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.9rem;font-weight:700;color:#f39c12;margin-bottom:8px">🧠 Explication</div><div style="font-size:0.8rem;color:#cbd5e1;line-height:1.8">{explication}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="background:#0d1a0d;border:1px solid #1a3a1a;border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.8rem;color:#cbd5e1;line-height:1.8;white-space:pre-line">{awareness}</div></div>', unsafe_allow_html=True)
        elif ai_result and not ai_result.get("erreur"):
            ex = ai_result.get("explication", "")
            aw = ai_result.get("sensibilisation", "")
            bo = ai_result.get("bulletin", "")
            if bo:
                st.markdown(f'<div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.9rem;font-weight:700;color:#f39c12;margin-bottom:8px">📋 Bulletin Opérationnel</div><div style="font-size:0.8rem;color:#cbd5e1;line-height:1.8;white-space:pre-line">{bo}</div></div>', unsafe_allow_html=True)
            if ex:
                st.markdown(f'<div style="background:#0a1a2a;border:1px solid #1a3a5c;border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.9rem;font-weight:700;color:#f39c12;margin-bottom:8px">🧠 Explication de la prédiction</div><div style="font-size:0.8rem;color:#cbd5e1;line-height:1.8;white-space:pre-line">{ex}</div></div>', unsafe_allow_html=True)
            if aw:
                st.markdown(f'<div style="background:{ "#3d0000" if risque=="Très élevé" else "#3d1e00" if risque=="Élevé" else "#0d3020" };border:1px solid {color};border-radius:12px;padding:16px;margin-bottom:12px"><div style="font-size:0.9rem;font-weight:700;color:{color};margin-bottom:8px">{RISQUE_EMOJI[risque]} Message de sensibilisation</div><div style="font-size:0.8rem;color:#e2e8f0;line-height:1.8;white-space:pre-line">{aw}</div></div>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ Analyse IA en attente. Clique sur « Actualiser l'analyse IA ».")

        st.markdown("---")
        st.markdown('<div class="sec">⑤ Alerte Dynamique</div>', unsafe_allow_html=True)
        if risque in ["Élevé","Très élevé"]:
            css_a = "alert-r" if risque=="Très élevé" else "alert-o"
            tag_a = "tag-r" if risque=="Très élevé" else "tag-o"
            st.markdown(f"""<div class="{css_a}"><span class="tag {tag_a}">⚡ ALERTE {"CRITIQUE" if risque=="Très élevé" else "HAUTE"}</span><div style="font-weight:700;font-size:1rem;margin:4px 0">{RISQUE_EMOJI[risque]} Risque {risque} prédit — {mois} {annee}</div><div style="font-size:0.85rem;color:#ddd;line-height:1.7">Confiance : <b>{conf:.0%}</b> · T={temperature}°C · H={humidite}% · P={precipitation}mm · V={vent}m/s<br>{recommendation(risque)}</div></div>""", unsafe_allow_html=True)
            if st.button("📤 Envoyer l'alerte par email", type="primary", key="op_alert_send"):
                with st.spinner("⏳ Envoi via Railway…"):
                    res = envoyer_alerte(cfg_alertes, risque, conf, temperature, humidite, precipitation, vent, mois, annee, probas, recommendation(risque))
                email_res = res.get("email") or {}
                webhook_res = res.get("webhook") or {}
                json_res = res.get("json") or {}
                if email_res.get("succes"): st.success(f"✅ Email envoyé → {email_res.get('destinataires','?')}")
                if webhook_res.get("succes"): st.success("✅ Webhook envoyé")
                if json_res.get("succes"): st.info(f"💾 Événement sauvegardé : {json_res.get('fichier','?')}")
                if email_res.get("erreur"): st.error(email_res["erreur"])
        else:
            st.success(f"✅ Risque **{risque}** — Aucune alerte requise. Surveillance standard.")

    # =========================================================================
    # TAB 1 — Climatologie & Tendances
    # =========================================================================
    with tabs[1]:
        st.markdown('<div class="sec">Évolution climatique 2017–2035</div>', unsafe_allow_html=True)
        if D["proj"] is not None:
            st.plotly_chart(fig_temp_humidity_full(D["proj"]), use_container_width=True)
        else:
            st.warning("Données de projections climatiques non disponibles.")

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(fig_anomalies(), use_container_width=True)
        with c2:
            st.plotly_chart(fig_precipitations(), use_container_width=True)

        st.markdown('<div class="sec">Diagramme ombrothermique</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_ombrothermique(), use_container_width=True)

        st.markdown('<div class="sec">Projections climatiques 2026–2035</div>', unsafe_allow_html=True)
        if D["proj"] is not None:
            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(fig_proj_temp(D["proj"]), use_container_width=True)
            with c4:
                st.plotly_chart(fig_proj_heatmap(D["proj"]), use_container_width=True)
            st.plotly_chart(fig_proj_prob_evol(D["proj"]), use_container_width=True)

    # =========================================================================
    # TAB 2 — Télédétection & Analyse
    # =========================================================================
    BASE_IMG = BASE / "data" / "processed" / "images" / "satellite"

    with tabs[2]:
        st.markdown("""
        <div style="background:#0a1628;border:1px solid #1a3a5c;border-radius:8px;padding:10px 14px;margin-bottom:10px">
        <b style="font-size:1rem;color:#f39c12">🛰️ Télédétection & Analyse Spatiale — Incendie Agdez 2025</b>
        <span style="font-size:0.75rem;color:#94a3b8;float:right">Sentinel-2 · NDVI · NBR · dNBR · MNT</span></div>""", unsafe_allow_html=True)

        IMG_W = 340

        # ── Section 1 : NDVI ──
        st.markdown('<div class="sec" style="font-size:0.85rem;padding:4px 8px">① NDVI — Indice de Végétation</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        p_ndvi_av = BASE_IMG / "carte_ndvi_avant.png"
        p_ndvi_ap = BASE_IMG / "carte_ndvi_apres.png"
        with c1:
            if p_ndvi_av.exists():
                st.image(str(p_ndvi_av), caption="NDVI avant (14/09)", width=IMG_W)
            else: st.warning("Indisponible")
        with c2:
            if p_ndvi_ap.exists():
                st.image(str(p_ndvi_ap), caption="NDVI après (16/09)", width=IMG_W)
            else: st.warning("Indisponible")
        st.markdown('<div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:6px;padding:6px 10px;font-size:0.72rem;color:#cbd5e1;margin-bottom:6px"><b>📖</b> NDVI moyen : 0.144 → 0.117 (Δ −19.1 %). Destruction de la biomasse et exposition du sol nu.</div>', unsafe_allow_html=True)

        # ── Section 2 : NBR ──
        st.markdown('<div class="sec" style="font-size:0.85rem;padding:4px 8px">② NBR — Détection des Zones Brûlées</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        p_nbr_av = BASE_IMG / "carte_nbr_avant.png"
        p_nbr_ap = BASE_IMG / "carte_nbr_apres.png"
        with c1:
            if p_nbr_av.exists():
                st.image(str(p_nbr_av), caption="NBR avant", width=IMG_W)
            else: st.warning("Indisponible")
        with c2:
            if p_nbr_ap.exists():
                st.image(str(p_nbr_ap), caption="NBR après", width=IMG_W)
            else: st.warning("Indisponible")
        st.markdown('<div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:6px;padding:6px 10px;font-size:0.72rem;color:#cbd5e1;margin-bottom:6px"><b>📖</b> La différence NBR met en évidence les zones de combustion intense (pixels à faible NBR post-incendie).</div>', unsafe_allow_html=True)

        # ── Section 3 : dNBR + Sévérité côte à côte ──
        st.markdown('<div class="sec" style="font-size:0.85rem;padding:4px 8px">③ dNBR & Sévérité Classifiée</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        p_dnbr = BASE_IMG / "carte_dnbr.png"
        p_sev  = BASE_IMG / "carte_severite.png"
        with c1:
            if p_dnbr.exists():
                st.image(str(p_dnbr), caption="dNBR — Intensité du brûlage", width=IMG_W)
            else: st.warning("Indisponible")
            st.markdown('<div style="background:#0a1a0a;border:1px solid #1a3a1a;border-radius:6px;padding:5px 8px;font-size:0.72rem;color:#cbd5e1"><b>📖</b> dNBR moy. 0.0248. Zones les plus touchées (dNBR &gt; 0.27) sur pentes Sud-Est.</div>', unsafe_allow_html=True)
        with c2:
            if p_sev.exists():
                st.image(str(p_sev), caption="Sévérité classifiée (USGS)", width=IMG_W)
            else: st.warning("Indisponible")

        # Table dNBR compacte
        st.markdown("<b style='font-size:0.78rem;color:#f39c12'>Table d'interprétation dNBR</b>", unsafe_allow_html=True)
        dnbr_rows = [
            ["<b>dNBR</b>","<b>Sévérité</b>","<b>Description</b>"],
            ["< 0.1", "Faible", "Végétation partiellement brûlée"],
            ["0.1 – 0.27", "Modéré", "Destruction du couvert herbacé"],
            ["0.27 – 0.44", "Fort", "Consommation de la litière"],
            ["> 0.44", "Très fort", "Sol stérilisé"],
        ]
        dnbr_html = "<table style='width:100%;font-size:0.7rem;border-collapse:collapse'>"
        for i, row in enumerate(dnbr_rows):
            bg = "#0d1a2d" if i % 2 == 0 else "#0a1628"
            text_color = "#f8fafc" if i == 0 else "#cbd5e1"
            cells = "".join(f'<td style="padding:3px 8px;border:1px solid #2a4a6c;color:{text_color}">{c}</td>' for c in row)
            dnbr_html += f'<tr style="background:{bg}">{cells}</tr>'
        dnbr_html += "</table>"
        st.markdown(dnbr_html, unsafe_allow_html=True)

        # ── Section 4 : Analyse des indices (graphiques + tableau en 2 colonnes) ──
        st.markdown('<div class="sec" style="font-size:0.85rem;padding:4px 8px">④ Analyse des Indices Spectraux</div>', unsafe_allow_html=True)
        col_g, col_t = st.columns([1.3, 1])
        with col_g:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_ndvi_bars(D["idx"]), use_container_width=True, config={"displayModeBar":False})
            with c2:
                st.plotly_chart(fig_dnbr_radar(D["idx"]), use_container_width=True, config={"displayModeBar":False})
            sev_fig = fig_severity_pie(D["sev"])
            if sev_fig is not None:
                st.plotly_chart(sev_fig, use_container_width=True, config={"displayModeBar":False})
            else:
                st.warning("Données de sévérité non disponibles.")
        with col_t:
            st.markdown("<b style='font-size:0.78rem;color:#f39c12'>Statistiques des indices</b>", unsafe_allow_html=True)
            if D["idx"] is not None and not D["idx"].empty:
                df_idx = D["idx"]
                df_idx_display = df_idx.copy()
                for col in df_idx_display.select_dtypes(include=["float64","int32","int64"]).columns:
                    df_idx_display[col] = df_idx_display[col].apply(lambda x: f"{x:.4f}")
                st.dataframe(df_idx_display, use_container_width=True, hide_index=True, height=180)
            else:
                st.warning("Indisponible.")

        # ── Section 5 : Carte Topographique ──
        st.markdown('<div class="sec" style="font-size:0.85rem;padding:4px 8px">⑤ Topographie — Contexte du Modèle ML</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px">
        Alt. {ALTITUDE} m · Pente {PENTE}° · Exp. {EXPOSITION}° (Sud-Est) · MNT 30 m (SRTM/ALOS PALSAR)
        </div>""", unsafe_allow_html=True)
        topo_map = folium.Map(location=[LAT, LON], zoom_start=13,
                              tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                              attr="© OpenTopoMap", prefer_canvas=True)
        folium.Marker(
            location=[LAT, LON],
            popup=folium.Popup(f"""
            <div style="font-family:Arial;min-width:200px">
              <b>📍 Agdez — Paramètres topographiques</b><br>
              Altitude : {ALTITUDE} m<br>
              Pente : {PENTE}°<br>
              Exposition : {EXPOSITION}° (Sud-Est)<br>
              Zone : Drâa-Tafilalet, Maroc
            </div>""", max_width=250),
            tooltip="📍 Agdez",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(topo_map)
        folium.Circle(
            location=[LAT, LON], radius=3000, color="#f39c12",
            fill=True, fill_opacity=0.08, weight=1.5, dash_array="5,5",
        ).add_to(topo_map)
        st_folium(topo_map, width=None, height=280, key="folium_topo")
        st.caption("OpenTopoMap — Courbes de niveau et relief de la zone d'étude")

    # =========================================================================
    # TAB 3 — IA & Modèle
    # =========================================================================
    with tabs[3]:
        st.markdown('<div class="sec">🧠 Diagnostic IA</div>', unsafe_allow_html=True)
        try:
            from src.ai.llm_service import diagnostics as diag_ia
            d = diag_ia()
            api_status = "✅ Oui" if d["api_key_detected"] else "❌ Non"
            auth_status = "✅ Connecté" if d["api_key_detected"] and not d["last_api_error"] else (
                "⚠️ Quota dépassé" if d["last_api_error"] and "quota" in d["last_api_error"].lower()
                else "❌ Échec" if d["last_api_error"]
                else "⏳ Non testé"
            )
            last_err = d["last_api_error"] or "—"
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fournisseur", d["provider"].title())
            c2.metric("Modèle", d["model"])
            c3.metric("Clé API détectée", api_status)
            c4.metric("Statut authentification", auth_status)
            st.caption(f"Dernière erreur API : {last_err}")
        except Exception:
            st.caption("Diagnostic IA non disponible")

        st.markdown('<div class="sec">Carte d\'identité du modèle</div>', unsafe_allow_html=True)
        mi = D["mi"]
        if mi:
            n_features = len(mi.get("features", []))
            n_classes  = len(mi.get("classes", []))
            n_train    = mi.get("n_echantillons", len(HIST))
            acc_cv     = mi.get("accuracy_cv", None)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Algorithme", mi.get("modele", "Random Forest"))
            if acc_cv is not None:
                c2.metric("Accuracy (CV)", f"{acc_cv:.1%}")
            else:
                c2.metric("Accuracy (CV)", "N/A")
            c3.metric("Features", str(n_features))
            c4.metric("Classes", str(n_classes))
            c1b, c2b, c3b = st.columns(3)
            c1b.metric("Échantillons train", str(n_train))
            c2b.metric("Zone", mi.get("zone", "Agdez"))
            c3b.metric("Période", mi.get("annees_train", "2017–2025"))
            if mi.get("accuracy_cv_std"):
                st.caption(f"Écart-type accuracy CV : ±{mi['accuracy_cv_std']:.1%} "
                           f"· Validation croisée 5-fold "
                           f"· Version {mi.get('version', '1.0.0')}")
        else:
            st.warning("Informations du modèle non disponibles.")

        st.markdown('<div class="sec">Importance des features</div>', unsafe_allow_html=True)
        if D["fi"] is not None:
            st.plotly_chart(fig_fi(D["fi"]), use_container_width=True)
            st.markdown("""
            <div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:12px;padding:14px;font-size:0.8rem;color:#cbd5e1;line-height:1.8">
            <b>🔍 Interprétation :</b> La température et l'humidité sont les facteurs dominants (37.4% cumulé).
            Le stress végétal (17.5%) et l'indice de sécheresse (13.5%) traduisent l'état du combustible.
            La pente et l'exposition (7.1% cumulé) jouent un rôle modérateur.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Données d'importance des features non disponibles.")

        st.markdown('<div class="sec">Processus de prédiction</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#0d1a2d;border:1px solid #1a3a5c;border-radius:12px;padding:14px;font-size:0.8rem;color:#cbd5e1;line-height:1.8">
        <b>⚙️ Pipeline ML :</b><br>
        1. <b>Entrées :</b> 13 features (météo + topographie + végétation)<br>
        2. <b>Modèle :</b> Random Forest Classifier (100 arbres, profondeur max 10)<br>
        3. <b>Target :</b> 4 classes (Faible, Moyen, Élevé, Très élevé)<br>
        4. <b>Probabilités :</b> Moyenne des prédictions des arbres → softmax<br>
        5. <b>Décision :</b> Classe avec probabilité maximale → <span style="color:{color};font-weight:bold">{risque}</span> ({conf:.0%})<br>
        6. <b>Explication IA :</b> LLM externe (Gemini/GPT) avec fallback expert rule-based
        </div>
        """, unsafe_allow_html=True)

    # =========================================================================
    # TAB 4 — Alertes (envoi + historique)
    # =========================================================================
    with tabs[4]:
        st.markdown('<div class="sec">Configuration des alertes</div>', unsafe_allow_html=True)
        erreurs_cfg = cfg_alertes.erreurs()
        if not cfg_alertes.email_actif and not cfg_alertes.webhook_actif:
            st.warning("⚙️ **Aucun canal d'envoi activé.**\n\nCréez `config_alertes.json` pour activer l'envoi par email (Railway) et/ou webhook.", icon="⚠️")
            exemple_cfg = {"email":{"actif":True,"smtp_host":"smtp.gmail.com","smtp_port":587,"smtp_user":"votre.email@gmail.com","smtp_password":"mot_de_passe_application","destinataires":["pompiers@agdez.ma","commune@agdez.ma"],"expediteur_nom":"Système Alerte Incendie Agdez"},"webhook":{"actif":False,"url":"https://hooks.slack.com/...","type":"slack"},"options":{"cooldown_minutes":60,"sauvegarder_json":True,"repertoire_rapports":"reports"}}
            st.download_button("⬇️ Modèle config_alertes.json", data=json.dumps(exemple_cfg, ensure_ascii=False, indent=2).encode("utf-8"), file_name="config_alertes.json", mime="application/json")
        elif erreurs_cfg:
            st.error("❌ Configuration incomplète : " + " · ".join(erreurs_cfg))
        else:
            canaux = []
            if cfg_alertes.email_actif: canaux.append(f"📧 Email → {', '.join(cfg_alertes.destinataires)}")
            if cfg_alertes.webhook_actif: canaux.append(f"🔗 Webhook ({cfg_alertes.webhook_type})")
            st.success("✅ Canaux actifs : " + " · ".join(canaux))

        st.markdown("---")
        st.markdown("**🔴 Alerte courante**")
        if risque in ["Élevé","Très élevé"]:
            prio = "CRITIQUE" if risque=="Très élevé" else "HAUTE"
            css_a = "alert-r" if risque=="Très élevé" else "alert-o"
            tag_a = "tag-r" if risque=="Très élevé" else "tag-o"
            st.markdown(f"""<div class="{css_a}"><span class="tag {tag_a}">⚡ {prio}</span><div style="font-weight:700;font-size:0.95rem;margin:5px 0">{RISQUE_EMOJI[risque]} Risque {risque} — {mois} {annee}</div><div style="font-size:0.82rem;color:#ddd;line-height:1.8">📍 Zone : Agdez, Maroc · 📊 Confiance : <b>{conf:.0%}</b><br>🌡️ T={temperature}°C | 💧 H={humidite}% | 🌧️ P={precipitation}mm | 💨 V={vent}m/s<br>🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br>💬 <b>{recommendation(risque)}</b></div></div>""", unsafe_allow_html=True)
            col_envoyer, col_simuler, col_info = st.columns([1,1,2])
            with col_envoyer:
                if st.button("📤 Envoyer l'alerte", type="primary", key="btn_envoyer_courant"):
                    with st.spinner("⏳ Envoi Railway…"):
                        res = envoyer_alerte(cfg_alertes, risque, conf, temperature, humidite, precipitation, vent, mois, annee, probas, recommendation(risque))
                    email_res = res.get("email") or {}
                    webhook_res = res.get("webhook") or {}
                    json_res = res.get("json") or {}
                    if email_res.get("succes"): st.success(f"✅ Email envoyé → {email_res.get('destinataires','?')}")
                    if webhook_res.get("succes"): st.success("✅ Webhook envoyé")
                    if json_res.get("succes"): st.info(f"💾 Sauvegardée : {json_res.get('fichier','?')}")
                    if email_res.get("erreur"): st.error(email_res["erreur"])
            with col_simuler:
                if st.button("🧪 Voir JSON", key="btn_simuler_courant"):
                    st.json({"priorite":prio,"risque":risque,"confiance":f"{conf:.0%}","periode":f"{mois} {annee}","conditions":{"temperature":temperature,"humidite":humidite,"precipitation":precipitation,"vent":vent},"probabilites":{k:f"{v:.0%}" for k,v in probas.items()},"recommandation":recommendation(risque)})
            with col_info:
                st.caption(f"📧 Email : {'✅' if cfg_alertes.email_actif else '❌'}  |  🔗 Webhook : {'✅' if cfg_alertes.webhook_actif else '❌'}  |  💾 JSON : {'✅' if cfg_alertes.sauvegarder_json else '❌'}")
        else:
            st.success(f"✅ Risque **{risque}** — Aucune alerte.")

        st.markdown("---")
        st.markdown("**Archive alertes historiques (JSON)**")
        alertes = D["alertes"]
        if alertes:
            for a in alertes:
                prio = a.get("priorite","")
                css_a = "alert-r" if prio=="CRITIQUE" else "alert-o"
                tag_a = "tag-r" if prio=="CRITIQUE" else "tag-o"
                try: ts = datetime.fromisoformat(a.get("timestamp","")).strftime("%d/%m/%Y %H:%M")
                except: ts = a.get("timestamp","—")
                st.markdown(f"""<div class="{css_a}" style="opacity:0.8"><span class="tag {tag_a}">📁 {prio}</span><div style="font-size:0.85rem;font-weight:600;margin:3px 0">{a.get('scenario','—')}</div><div style="font-size:0.78rem;color:#aaa">{a.get('risque','')} · {a.get('confiance',0):.0%} · {ts}</div></div>""", unsafe_allow_html=True)
        else:
            st.info("Aucun fichier alerte JSON trouvé dans reports/")

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