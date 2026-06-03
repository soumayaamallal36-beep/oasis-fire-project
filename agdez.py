# =============================================================================
# app_agdez.py — Dashboard Prédiction Risque Incendie · Agdez, Maroc
# Version 2.0 — Toutes erreurs corrigées + données réelles intégrées
# =============================================================================
# Usage : streamlit run app_agdez.py
#
# Structure attendue à côté de ce fichier :
#   data/csv/        ← CSVs climatiques
#   data/xlsx/       ← XLSXs incendie/indices
#   data/images/     ← graphiques & tableaux
#   models/trained/  ← model_risque_incendie.pkl, label_encoder.pkl
#   models/metadata/ ← model_info.json, feature_importance.csv,
#                      predictions_scenarios_2026.csv,
#                      projections_climatiques.csv
#   reports/         ← alerte_*.json, rapport_prediction.txt,
#                      synthese_risque.json
# =============================================================================

import glob
import json
import os
import warnings
from datetime import datetime
from pathlib import Path

import folium
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_folium import st_folium

warnings.filterwarnings("ignore")

# ─── Chemins ─────────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent
CSV_DIR   = BASE / "data" / "csv"
XLSX_DIR  = BASE / "data" / "xlsx"
IMG_DIR   = BASE / "data" / "images"
MDL_DIR   = BASE / "models" / "trained"
META_DIR  = BASE / "models" / "metadata"
RPT_DIR   = BASE / "reports"

# ─── Constantes zone Agdez ───────────────────────────────────────────────────
LAT, LON   = 30.69, -6.45
ALTITUDE   = 1169.3
PENTE      = 5.73
EXPOSITION = 165.51
MOIS_MAP   = {"Juin": 0, "Juillet": 1, "Août": 2}

RISQUE_COLOR = {
    "Faible":      "#27ae60",
    "Moyen":       "#e67e22",
    "Élevé":       "#e74c3c",
    "Très élevé":  "#8e1a1a",
}
RISQUE_EMOJI = {"Faible": "🟢", "Moyen": "🟡", "Élevé": "🟠", "Très élevé": "🔴"}
RISQUE_BG    = {
    "Faible": "#eafaf1", "Moyen": "#fef9e7",
    "Élevé":  "#fdf2f2", "Très élevé": "#fce4e4",
}

# ─── Palette couleurs principale ─────────────────────────────────────────────
C_PRIMARY  = "#d62828"   # rouge Agdez
C_ACCENT   = "#f77f00"   # orange
C_DARK     = "#1a1a2e"   # fond sombre
C_CARD     = "#16213e"   # carte
C_BORDER   = "#0f3460"   # bordure
C_MUTED    = "#a0aec0"
C_TEXT     = "#e2e8f0"
C_GREEN    = "#2ecc71"
C_BLUE     = "#3498db"

# =============================================================================
# ── Configuration Streamlit ──────────────────────────────────────────────────
# =============================================================================
st.set_page_config(
    page_title="Agdez · Risque Incendie de Forêt",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Syne', sans-serif;
    background-color: {C_DARK};
    color: {C_TEXT};
}}
/* Header */
.app-header {{
    background: linear-gradient(135deg,#1a0505 0%,#3d0c02 40%,#1a0a00 100%);
    border-radius: 14px; padding: 22px 30px; margin-bottom: 20px;
    border: 1px solid #7f1d1d;
}}
.app-header h1 {{ color: {C_PRIMARY}; font-size: 1.9rem; font-weight: 800;
                  margin: 0; letter-spacing: -1px; }}
.app-header p  {{ color: #d4a88a; font-size: 0.82rem; margin: 4px 0 0 0;
                  font-family: 'Space Mono', monospace; }}
/* Metric cards */
.kpi-card {{
    background: {C_CARD}; border-radius: 12px; padding: 16px 18px;
    border: 1px solid {C_BORDER}; text-align: center; height: 100%;
}}
.kpi-value {{ font-size: 1.9rem; font-weight: 800; line-height: 1.1; }}
.kpi-label {{ font-size: 0.72rem; color: {C_MUTED};
              font-family: 'Space Mono',monospace; margin-top: 5px; }}
/* Section title */
.sec-title {{
    font-family: 'Space Mono',monospace; font-size: 0.68rem;
    color: {C_MUTED}; text-transform: uppercase; letter-spacing: 2px;
    margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid {C_BORDER};
}}
/* Info box */
.info-box {{
    background: {C_CARD}; border-radius: 10px; padding: 14px;
    border: 1px solid {C_BORDER}; margin-bottom: 10px;
}}
/* Alert boxes */
.alert-critique {{
    background:#1a0505; border:1px solid #7f1d1d; border-left:4px solid {C_PRIMARY};
    border-radius:8px; padding:12px 16px; margin-bottom:8px;
}}
.alert-haute {{
    background:#1a1000; border:1px solid #78350f; border-left:4px solid {C_ACCENT};
    border-radius:8px; padding:12px 16px; margin-bottom:8px;
}}
/* Tags */
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px;
        font-family:'Space Mono',monospace; font-size:0.68rem; font-weight:700;
        margin-bottom:4px; }}
.tag-crit {{ background:#3d0000; color:#ff6b6b; }}
.tag-haute {{ background:#3d1e00; color:#ffaa55; }}
/* Sidebar */
[data-testid="stSidebar"] {{ background:#0d0d1a; border-right:1px solid #222; }}
/* Tabs */
.stTabs [data-baseweb="tab"] {{ font-family:'Syne',sans-serif; font-weight:600; font-size:0.85rem; }}
.stTabs [data-baseweb="tab-list"] {{ background:transparent; border-bottom:1px solid {C_BORDER}; }}
/* Metric */
[data-testid="stMetric"] {{
    background:{C_CARD}; border-radius:10px; padding:12px;
    border:1px solid {C_BORDER};
}}
[data-testid="stMetricLabel"] {{ font-family:'Space Mono',monospace; font-size:0.7rem; }}
[data-testid="stMetricValue"] {{ font-family:'Syne',sans-serif; font-weight:800; }}
/* Progress bar override */
.stProgress .st-bo {{ background-color:{C_PRIMARY}; }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# ── Helpers de chargement ────────────────────────────────────────────────────
# =============================================================================

def read_csv(path: Path) -> pd.DataFrame | None:
    """Lit un CSV avec détection automatique d'encodage et séparateur."""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        for sep in [";", ","]:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc)
                if df.shape[1] > 1:
                    return df
            except Exception:
                pass
    return None


def read_xlsx(path: Path, sheet: str = None) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet or 0)
    except Exception:
        return None


def load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@st.cache_resource(show_spinner=False)
def load_model():
    try:
        model = joblib.load(MDL_DIR / "model_risque_incendie.pkl")
        le    = joblib.load(MDL_DIR / "label_encoder.pkl")
        return model, le
    except FileNotFoundError as e:
        st.error(f"❌ Modèle introuvable : {e}")
        st.stop()


@st.cache_data(show_spinner=False)
def load_all_data():
    """Charge toutes les sources de données en une passe (mise en cache)."""
    d = {}
    d["ete"]          = read_csv(CSV_DIR / "climat_conditions_ete_2025.csv")
    d["annuelles"]    = read_csv(CSV_DIR / "climat_statistiques_annuelles.csv")
    d["prediction"]   = read_csv(CSV_DIR / "climat_donnees_prediction.csv")
    d["recap"]        = read_csv(CSV_DIR / "climat_recap_incendie.csv")
    d["stats_recap"]  = read_csv(CSV_DIR / "climat_stats_recap.csv")
    d["indices"]      = read_xlsx(XLSX_DIR / "indices_stats.xlsx")
    d["severity"]     = read_xlsx(XLSX_DIR / "severity_classes.xlsx")
    d["summary"]      = read_xlsx(XLSX_DIR / "summary_complete.xlsx")
    d["scenarios"]    = read_csv(META_DIR / "predictions_scenarios_2026.csv")
    d["projections"]  = read_csv(META_DIR / "projections_climatiques.csv")
    d["fi"]           = read_csv(META_DIR / "feature_importance.csv")
    d["model_info"]   = load_json(META_DIR / "model_info.json")
    d["synthese"]     = load_json(RPT_DIR / "synthese_risque.json")
    d["alertes"]      = [load_json(Path(f))
                         for f in sorted(glob.glob(str(RPT_DIR / "alerte_*.json")))]
    return d


# =============================================================================
# ── Prédiction ML ────────────────────────────────────────────────────────────
# =============================================================================

FEAT_ORDER = [
    "temperature", "humidite", "precipitation", "vent",
    "pente", "altitude", "exposition", "ndvi_avant",
    "indice_secheresse", "indice_propagation",
    "stress_vegetal", "exposition_sud", "mois_num",
]


def build_features(t, h, p, v, mois_num=1, ndvi=0.144,
                   pente=PENTE, alt=ALTITUDE, expo=EXPOSITION):
    row = dict(temperature=t, humidite=h, precipitation=p, vent=v,
               pente=pente, altitude=alt, exposition=expo,
               ndvi_avant=ndvi, mois_num=mois_num)
    df = pd.DataFrame([row])
    df["indice_secheresse"]  = (df["temperature"] - df["humidite"]) / (df["precipitation"] + 0.1)
    df["indice_propagation"] = df["vent"] * np.sin(np.radians(df["pente"]))
    df["stress_vegetal"]     = (1 - df["ndvi_avant"]) * df["temperature"] / 10
    df["exposition_sud"]     = np.cos(np.radians(df["exposition"] - 180)).clip(0, 1)
    return df[FEAT_ORDER]


def predict(model, le, t, h, p, v, mois_num=1, ndvi=0.144):
    X      = build_features(t, h, p, v, mois_num, ndvi)
    y_num  = model.predict(X)[0]
    probas = model.predict_proba(X)[0]
    label  = le.inverse_transform([y_num])[0]
    return label, float(probas.max()), {c: float(pb) for c, pb in zip(le.classes_, probas)}


def recommendation(risque):
    return {
        "Faible":     "✅ Surveillance standard. Conditions favorables.",
        "Moyen":      "⚠️ Vigilance modérée. Vérifier les équipements.",
        "Élevé":      "🟠 Surveillance renforcée. Patrouilles terrain.",
        "Très élevé": "🔴 DANGER — Activer plan ORSEC. Interdire accès zones boisées.",
    }.get(risque, "—")


# =============================================================================
# ── Carte Folium ─────────────────────────────────────────────────────────────
# =============================================================================

def make_map(risque, conf, probas, t, h, p, v, mois, annee):
    color   = RISQUE_COLOR.get(risque, "#888")
    emoji   = RISQUE_EMOJI.get(risque, "⚪")
    rec     = recommendation(risque)
    proba_html = "".join([
        f'<span style="background:{RISQUE_COLOR.get(c,"#888")};color:white;'
        f'border-radius:4px;padding:2px 7px;margin:2px;display:inline-block;'
        f'font-size:0.78rem">{c}: {pb:.0%}</span>'
        for c, pb in probas.items()
    ])
    popup_html = f"""
    <div style="font-family:Arial,sans-serif;min-width:290px">
      <div style="background:{color};color:white;padding:10px 14px;
                  border-radius:8px 8px 0 0;margin:-4px -4px 10px -4px">
        <div style="font-size:1.15rem;font-weight:bold">{emoji} {risque}</div>
        <div style="font-size:0.78rem;opacity:.9">Confiance : {conf:.0%} — {mois} {annee}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:0.8rem">
        {''.join([
            f'<tr style="background:{"#f8f8f8" if i%2==0 else "white"}">'
            f'<td style="padding:5px 8px;font-weight:bold">{k}</td>'
            f'<td style="padding:5px 8px">{val}</td></tr>'
            for i,(k,val) in enumerate([
                ("📍 Zone","Agdez, Drâa-Tafilalet, Maroc"),
                ("🌐 Coordonnées",f"{LAT}°N, {abs(LON)}°W"),
                ("⛰️ Altitude",f"{ALTITUDE} m"),
                ("📐 Pente",f"{PENTE}°"),
                ("🧭 Exposition","165.51° (Sud-Est)"),
                ("🌡️ Température",f"{t}°C"),
                ("💧 Humidité",f"{h}%"),
                ("🌧️ Précipitations",f"{p} mm"),
                ("💨 Vent",f"{v} m/s"),
                ("🔥 Ind. sécheresse",f"{(t-h)/(p+0.1):.2f}"),
            ])
        ])}
      </table>
      <div style="background:#fffbea;border-radius:6px;padding:8px 10px;
                  margin-top:8px;font-size:0.78rem">
        <b>Recommandation :</b> {rec}
      </div>
      <div style="margin-top:8px;font-size:0.75rem"><b>Probabilités :</b><br>{proba_html}</div>
    </div>"""

    m = folium.Map(location=[LAT, LON], zoom_start=12,
                   tiles="CartoDB dark_matter", prefer_canvas=True)
    # Zone d'influence
    folium.Circle(location=[LAT, LON], radius=5000, color=color,
                  fill=True, fill_opacity=0.10, weight=1.5, opacity=0.5).add_to(m)
    # Marqueur principal
    folium.CircleMarker(
        location=[LAT, LON], radius=16, color=color,
        fill=True, fill_color=color, fill_opacity=0.85, weight=3,
        popup=folium.Popup(popup_html, max_width=330),
        tooltip=f"🔥 Agdez — {risque} ({conf:.0%})",
    ).add_to(m)
    # Point central blanc
    folium.CircleMarker(location=[LAT, LON], radius=4, color="white",
                        fill=True, fill_color="white", fill_opacity=1, weight=0).add_to(m)
    # Couche satellite ESRI
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI", name="🛰️ Satellite", overlay=False,
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


# =============================================================================
# ── Graphiques Plotly ─────────────────────────────────────────────────────────
# =============================================================================

DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#0d0d1a",
    plot_bgcolor="#0d0d1a",
    font_family="Syne",
    font_color="#e2e8f0",
    margin=dict(t=45, b=35, l=15, r=15),
)
RP = {  # Risque Palette
    "Faible": "#27ae60", "Moyen": "#e67e22",
    "Élevé": "#e74c3c", "Très élevé": "#8e1a1a",
}


def hex2rgba(h, a=0.15):
    """Convertit une couleur hex en chaîne rgba valide."""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def fig_annuelles(df):
    """Évolution température & humidité 2017-2025 depuis les données réelles."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Température (°C)"],
        name="Température (°C)", mode="lines+markers+text",
        text=[f"{v:.2f}°" for v in df["Température (°C)"]],
        textposition="top center", textfont=dict(size=9),
        line=dict(color=C_PRIMARY, width=3),
        marker=dict(size=9, color=C_PRIMARY),
        fill="tozeroy", fillcolor=hex2rgba(C_PRIMARY, 0.1),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Humidité (%)"],
        name="Humidité (%)", mode="lines+markers",
        line=dict(color=C_BLUE, width=2, dash="dot"),
        marker=dict(size=7),
    ), secondary_y=True)
    fig.update_layout(title="Évolution climatique annuelle — Agdez (2017–2025)", **DARK,
                      legend=dict(x=0.01, y=0.99))
    fig.update_yaxes(title_text="Température (°C)", secondary_y=False, color=C_PRIMARY)
    fig.update_yaxes(title_text="Humidité (%)", secondary_y=True, color=C_BLUE)
    return fig


def fig_anomalies(df):
    """Anomalies de température estivale (réf. 2017-2025)."""
    ref  = df["Température (°C)"].mean()
    anom = df["Température (°C)"] - ref
    cols = [C_PRIMARY if v >= 0 else C_BLUE for v in anom]
    fig  = go.Figure(go.Bar(
        x=df["Année"], y=anom, marker_color=cols,
        text=[f"{v:+.2f}°C" for v in anom], textposition="outside",
    ))
    fig.add_hline(y=0, line_color="white", line_width=1)
    fig.update_layout(
        title=f"Anomalies de température (réf. moy. {ref:.2f}°C)", **DARK,
        yaxis_title="Écart à la moyenne (°C)",
    )
    return fig


def fig_precipitations(df):
    """Précipitations annuelles avec tendance."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Année"], y=df["Précipitations (mm)"],
        marker_color=C_BLUE, name="Précipitations",
        text=[f"{v:.0f}" for v in df["Précipitations (mm)"]],
        textposition="outside",
    ))
    # Tendance linéaire
    z = np.polyfit(df["Année"], df["Précipitations (mm)"], 1)
    trend = np.poly1d(z)(df["Année"])
    fig.add_trace(go.Scatter(
        x=df["Année"], y=trend, name="Tendance",
        line=dict(color=C_ACCENT, width=2, dash="dash"), mode="lines",
    ))
    fig.update_layout(title="Précipitations annuelles + tendance (2017–2025)", **DARK,
                      yaxis_title="mm")
    return fig


def fig_ete_bars(df):
    """Températures été 2025 par mois (données réelles)."""
    moy = df["Température (°C)"].mean()
    cols = [C_PRIMARY if v == df["Température (°C)"].max() else C_ACCENT
            for v in df["Température (°C)"]]
    fig = go.Figure(go.Bar(
        x=df["Mois"], y=df["Température (°C)"], marker_color=cols,
        text=[f"{v:.2f}°C" for v in df["Température (°C)"]],
        textposition="outside", name="T°C été 2025",
    ))
    fig.add_hline(y=moy, line_color="#58a6ff", line_dash="dash",
                  annotation_text=f"Moy: {moy:.1f}°C", annotation_position="right")
    fig.update_layout(title="Températures estivales 2025 — Agdez", **DARK,
                      yaxis_title="Température (°C)", yaxis_range=[0, 38])
    return fig


def fig_ombrothermique(df_ann):
    """Diagramme ombrothermique reconstruit depuis les données annuelles."""
    mois_l = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
    prec   = [0.8,5.1,6.0,18.7,1.1,3.0,26.4,15.0,0.05,0.0,2.0,31.0]
    temp   = [9.3,11.5,14.0,19.0,22.1,29.3,32.7,31.4,26.0,21.5,15.1,8.5]
    fig    = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=mois_l, y=prec, name="Précipitations (mm)",
        marker_color=C_BLUE, opacity=0.75,
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=mois_l, y=temp, name="Température (°C)",
        line=dict(color=C_PRIMARY, width=3),
        mode="lines+markers", marker=dict(size=8, color=C_PRIMARY),
    ), secondary_y=True)
    fig.update_layout(title="Diagramme ombrothermique — Agdez 2025", **DARK)
    fig.update_yaxes(title_text="Précipitations (mm)", secondary_y=False, color=C_BLUE)
    fig.update_yaxes(title_text="Température (°C)", secondary_y=True, color=C_PRIMARY)
    return fig


def fig_vent_humidite(df):
    """Vent & humidité annuels."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Vent (m/s)"], name="Vent (m/s)",
        line=dict(color=C_GREEN, width=2), mode="lines+markers",
        marker=dict(size=8),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Humidité (%)"], name="Humidité (%)",
        line=dict(color=C_BLUE, width=2, dash="dot"), mode="lines+markers",
        marker=dict(size=8),
    ), secondary_y=True)
    fig.add_hline(y=df["Vent (m/s)"].mean(), line_dash="dash", line_color=C_GREEN,
                  secondary_y=False, annotation_text=f"Moy vent {df['Vent (m/s)'].mean():.2f}")
    fig.update_layout(title="Vent & Humidité annuels (2017–2025)", **DARK)
    fig.update_yaxes(title_text="Vent (m/s)", secondary_y=False, color=C_GREEN)
    fig.update_yaxes(title_text="Humidité (%)", secondary_y=True, color=C_BLUE)
    return fig


def fig_severity_pie(df):
    """Camembert des classes de sévérité de l'incendie 2025."""
    df2 = df[df["Nom"] != "Non brûlé"]  # exclure non brûlé pour lisibilité
    colors = [C_GREEN, C_ACCENT, C_PRIMARY, "#8e1a1a"]
    fig = go.Figure(go.Pie(
        labels=df2["Nom"], values=df2["Surface (ha)"],
        marker=dict(colors=colors[:len(df2)]),
        textinfo="label+percent+value",
        texttemplate="%{label}<br>%{value:.1f} ha (%{percent})",
        hole=0.35,
    ))
    fig.update_layout(title="Classes de sévérité incendie — Agdez 2025", **DARK,
                      showlegend=True)
    return fig


def fig_severity_bars(df):
    """Barres des surfaces brûlées par classe."""
    df2  = df[df["Classe"] > 0].copy()
    cols = [C_GREEN, C_ACCENT, C_PRIMARY, "#8e1a1a"]
    fig  = go.Figure(go.Bar(
        x=df2["Nom"], y=df2["Surface (ha)"],
        marker_color=cols[:len(df2)],
        text=[f"{v:.2f} ha\n({p:.2f}%)" for v, p in zip(df2["Surface (ha)"], df2["Pourcentage (%)"])],
        textposition="outside",
    ))
    fig.update_layout(title="Surface brûlée par classe de sévérité (ha)", **DARK,
                      yaxis_title="Surface (ha)", yaxis_range=[0, 380])
    return fig


def fig_indices_radar(df):
    """Radar NDVI avant/après et dNBR."""
    # Normaliser pour le radar
    cats   = ["NDVI avant", "NDVI après", "dNBR"]
    vals_m = [df[df["Indice"] == "NDVI_avant"]["Moyenne"].values[0],
              df[df["Indice"] == "NDVI_après"]["Moyenne"].values[0],
              df[df["Indice"] == "dNBR"]["Moyenne"].values[0]]
    vals_x = [df[df["Indice"] == "NDVI_avant"]["Maximum"].values[0],
              df[df["Indice"] == "NDVI_après"]["Maximum"].values[0],
              df[df["Indice"] == "dNBR"]["Maximum"].values[0]]
    fig = go.Figure()
    for vals, name, col in [
        (vals_m, "Valeurs moyennes", C_BLUE),
        (vals_x, "Valeurs maximales", C_PRIMARY),
    ]:
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=cats + [cats[0]],
            name=name,
            line=dict(color=col, width=2),
            fill="toself",
            fillcolor=hex2rgba(col, 0.12),
        ))
    fig.update_layout(
        title="Indices spectraux NDVI/dNBR — Radar",
        polar=dict(bgcolor="#111", radialaxis=dict(visible=True)),
        **DARK,
    )
    return fig


def fig_ndvi_change(df):
    """Variation NDVI avant/après incendie."""
    cats   = ["NDVI avant", "NDVI après"]
    vals_m = [df[df["Indice"] == "NDVI_avant"]["Moyenne"].values[0],
              df[df["Indice"] == "NDVI_après"]["Moyenne"].values[0]]
    cols   = [C_GREEN, C_PRIMARY]
    fig    = go.Figure(go.Bar(
        x=cats, y=vals_m, marker_color=cols,
        text=[f"{v:.4f}" for v in vals_m], textposition="outside",
    ))
    delta = ((vals_m[1] - vals_m[0]) / vals_m[0]) * 100
    fig.update_layout(
        title=f"NDVI avant vs après incendie (Δ = {delta:.1f}%)", **DARK,
        yaxis_title="NDVI moyen", yaxis_range=[0, 0.20],
        annotations=[dict(x=0.5, y=0.95, xref="paper", yref="paper",
                          text=f"Perte végétation : {abs(delta):.1f}%",
                          showarrow=False, font=dict(color=C_ACCENT, size=13))],
    )
    return fig


def fig_scenarios_confidence(df):
    """Barres de confiance par scénario, colorées par risque."""
    cols = [RP.get(r, "#888") for r in df["risque_predit"]]
    fig  = go.Figure(go.Bar(
        x=df["scenario"], y=df["confiance"] * 100,
        marker_color=cols,
        text=[f"{c:.0%}" for c in df["confiance"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Confiance du modèle par scénario 2026 (%)", **DARK,
        xaxis_tickangle=-35, yaxis_title="Confiance (%)",
        yaxis_range=[0, 110],
    )
    return fig


def fig_scenarios_radar_chart(df):
    """Radar météo moyen par catégorie de scénario."""
    cats   = df["categorie"].unique()
    cols_v = ["temperature", "humidite", "precipitation", "vent"]
    labels = ["Température", "Humidité", "Précipitations", "Vent"]
    colors = [C_PRIMARY, "#8e1a1a", C_BLUE, C_GREEN]
    fig    = go.Figure()
    for i, cat in enumerate(cats):
        sub   = df[df["categorie"] == cat]
        means = [sub[c].mean() for c in cols_v]
        maxs  = [df[c].max() for c in cols_v]
        normd = [v / m if m > 0 else 0 for v, m in zip(means, maxs)]
        col   = colors[i % len(colors)]
        fig.add_trace(go.Scatterpolar(
            r=normd + [normd[0]],
            theta=labels + [labels[0]],
            name=cat,
            line=dict(color=col, width=2),
            fill="toself",
            fillcolor=hex2rgba(col, 0.10),
        ))
    fig.update_layout(
        title="Profil météo par catégorie de scénario",
        polar=dict(bgcolor="#111", radialaxis=dict(visible=True, range=[0, 1])),
        **DARK,
    )
    return fig


def fig_projections_temp(df):
    """Température projetée juillet 2026-2035."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["annee"], y=df["temperature"],
        mode="lines+markers+text",
        text=[f"{v:.1f}°C" for v in df["temperature"]],
        textposition="top center",
        line=dict(color=C_PRIMARY, width=3),
        marker=dict(size=10, color=C_PRIMARY),
        fill="tozeroy", fillcolor=hex2rgba(C_PRIMARY, 0.10),
        name="T°C projetée",
    ))
    fig.update_layout(title="Température juillet projetée 2026–2035", **DARK,
                      yaxis_title="°C", xaxis_title="Année")
    return fig


def fig_projections_confiance(df):
    """Barres de confiance par année projetée."""
    cols = [RP.get(r, "#888") for r in df["risque_predit"]]
    fig  = go.Figure(go.Bar(
        x=df["annee"], y=df["confiance"] * 100,
        marker_color=cols,
        text=[f"{c:.0%}" for c in df["confiance"]],
        textposition="outside",
    ))
    fig.update_layout(title="Confiance prédiction par année (2026–2035)", **DARK,
                      yaxis_title="%", yaxis_range=[0, 100])
    return fig


def fig_fi_bars(df):
    """Importance des features — barres horizontales."""
    df2   = df.sort_values("importance")
    colors = [C_PRIMARY if v > 0.15 else C_ACCENT if v > 0.09 else C_BLUE
              for v in df2["importance"]]
    fig   = go.Figure(go.Bar(
        x=df2["importance"], y=df2["feature"],
        orientation="h", marker_color=colors,
        text=[f"{v:.1%}" for v in df2["importance"]],
        textposition="outside",
    ))
    fig.update_layout(title="Importance des features — Random Forest", **DARK,
                      xaxis_title="Importance", height=430)
    return fig


def fig_proba_gauge(probas, risque):
    """Jauge de probabilité du risque prédit."""
    val = probas.get(risque, 0) * 100
    col = RISQUE_COLOR.get(risque, "#888")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": f"P({risque})", "font": {"size": 13}},
        number={"suffix": "%", "font": {"size": 26}},
        gauge={
            "axis":  {"range": [0, 100], "tickcolor": "#555"},
            "bar":   {"color": col, "thickness": 0.75},
            "bgcolor": "#111",
            "steps": [{"range": [0, 25],  "color": "#1a1a1a"},
                       {"range": [25, 50], "color": "#1f1a10"},
                       {"range": [50, 75], "color": "#2a1010"},
                       {"range": [75, 100],"color": "#3d0000"}],
            "threshold": {"line": {"color": col, "width": 4}, "value": val},
        },
    ))
    fig.update_layout(paper_bgcolor="#0d0d1a", font_family="Syne",
                      font_color="#e2e8f0",
                      margin=dict(t=50, b=10, l=20, r=20), height=200)
    return fig


def fig_fvt_heatmap(model, le):
    """Simulation journalière été 2026 — Fenêtre de Vulnérabilité Temporelle."""
    dates = pd.date_range("2026-06-01", "2026-08-31", freq="D")
    np.random.seed(42)
    rows  = []
    for d in dates:
        doy  = d.timetuple().tm_yday
        t    = round(29.5 + 3.5 * np.sin(np.pi * (doy - 152) / 91) + np.random.normal(0, 1.2), 2)
        h    = round(max(8.0, 20.0 - 4.0 * np.sin(np.pi * (doy - 152) / 91) + np.random.normal(0, 2)), 2)
        p    = round(max(0.0, np.random.exponential(3.5) if np.random.random() < 0.12 else 0.0), 2)
        v    = round(max(1.5, 4.0 + np.random.normal(0, 0.4)), 2)
        rows.append(dict(date=d, temperature=t, humidite=h, precipitation=p,
                         vent=v, mois_num={6:0,7:1,8:2}[d.month],
                         pente=PENTE, altitude=ALTITUDE, exposition=EXPOSITION, ndvi_avant=0.144))
    df = pd.DataFrame(rows)
    df["indice_secheresse"]  = (df["temperature"] - df["humidite"]) / (df["precipitation"] + 0.1)
    df["indice_propagation"] = df["vent"] * np.sin(np.radians(PENTE))
    df["stress_vegetal"]     = (1 - 0.144) * df["temperature"] / 10
    df["exposition_sud"]     = float(np.cos(np.radians(EXPOSITION - 180)))
    X      = df[FEAT_ORDER]
    labels = le.inverse_transform(model.predict(X))
    df["risque"] = labels
    df["r_num"]  = [{"Faible":0,"Moyen":1,"Élevé":2,"Très élevé":3}[l] for l in labels]

    cs = [[0.0,"#27ae60"],[0.33,"#e67e22"],[0.67,"#e74c3c"],[1.0,"#8e1a1a"]]
    fig = go.Figure(go.Heatmap(
        z=df["r_num"].values,
        x=df["date"].dt.strftime("%d/%m").values,
        y=["Risque"] * len(df),
        colorscale=cs, zmin=0, zmax=3,
        text=df["risque"].values,
        hovertemplate="<b>%{x}</b><br>Risque: %{text}<br>T=%{customdata[0]}°C H=%{customdata[1]}%<extra></extra>",
        customdata=np.column_stack([df["temperature"], df["humidite"]]),
        colorbar=dict(tickvals=[0,1,2,3],
                      ticktext=["Faible","Moyen","Élevé","Très élevé"],
                      thickness=12, len=0.6),
        showscale=True,
    ))
    fig.update_layout(
        title="🗓️ Fenêtre de Vulnérabilité Temporelle — Été 2026 (92 jours)",
        xaxis=dict(tickangle=-45, tickfont=dict(size=7)),
        yaxis=dict(showticklabels=False), height=220, **DARK,
    )
    return fig, df


def style_risque(val):
    """Coloration Pandas Styler par niveau de risque — utilise map() au lieu de applymap()."""
    mp = {
        "Très élevé": "background-color:#3d0000;color:#ff6b6b;font-weight:bold",
        "Élevé":      "background-color:#3d1e00;color:#ffaa55;font-weight:bold",
        "Moyen":      "background-color:#3d3000;color:#ffd700",
        "Faible":     "background-color:#0d3020;color:#7fff9a",
    }
    return mp.get(val, "")


# =============================================================================
# ── SIDEBAR ──────────────────────────────────────────────────────────────────
# =============================================================================
def render_sidebar():
    st.sidebar.markdown(f"""
    <div style="text-align:center;padding:12px 0">
        <div style="font-size:2rem">🔥</div>
        <div style="font-family:'Syne',sans-serif;font-weight:800;color:{C_PRIMARY};font-size:1rem">
            Agdez Fire Risk
        </div>
        <div style="font-family:'Space Mono',monospace;font-size:0.65rem;color:{C_MUTED}">
            Drâa-Tafilalet, Maroc
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📅 Période de simulation**")
    annee = st.sidebar.selectbox("Année", list(range(2026, 2036)), index=0)
    mois  = st.sidebar.selectbox("Mois",  ["Juin", "Juillet", "Août"], index=1)

    defaults = {"Juin": (29.5,19.5,2.5,4.5), "Juillet": (32.8,16.5,10.0,4.0), "Août": (31.5,20.0,0.5,3.8)}
    d_t, d_h, d_p, d_v = defaults[mois]

    st.sidebar.markdown("---")
    st.sidebar.markdown("**🌡️ Variables climatiques**")
    temperature   = st.sidebar.slider("Température (°C)",   15.0, 45.0, d_t, 0.5)
    humidite      = st.sidebar.slider("Humidité (%)",        5.0,  60.0, d_h, 1.0)
    precipitation = st.sidebar.slider("Précipitations (mm)", 0.0, 100.0, d_p, 0.5)
    vent          = st.sidebar.slider("Vent (m/s)",           0.5,  10.0, d_v, 0.1)
    ndvi          = st.sidebar.slider("NDVI avant",          0.05,  0.40, 0.144, 0.005)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**⚡ Préréglages**")
    presets = {
        "🔥 Canicule":       (38.0, 10.0,  0.0, 5.5),
        "⛈️ Après pluies":   (26.0, 45.0, 55.0, 3.0),
        "💨 Tempête vent":   (30.0, 18.0,  1.0, 8.0),
        "✅ Conditions sûres":(22.0, 55.0, 40.0, 2.0),
        "— Personnalisé —":  None,
    }
    preset = st.sidebar.radio("", list(presets.keys()), index=4,
                               label_visibility="collapsed")
    if presets[preset]:
        temperature, humidite, precipitation, vent = presets[preset]

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div style="font-size:0.68rem;color:{C_MUTED};font-family:'Space Mono',monospace;line-height:1.7">
    🤖 Random Forest · 13 features<br>
    📊 Accuracy CV : 76.7%<br>
    📅 Entraîné 2017–2025<br>
    📍 Agdez, 30.69°N 6.45°W
    </div>
    """, unsafe_allow_html=True)
    return annee, mois, temperature, humidite, precipitation, vent, ndvi


# =============================================================================
# ── MAIN ─────────────────────────────────────────────────────────────────────
# =============================================================================
def main():
    # Chargement données
    model, le = load_model()
    D         = load_all_data()

    # Sidebar
    annee, mois, temperature, humidite, precipitation, vent, ndvi = render_sidebar()

    # Prédiction courante
    mois_num              = MOIS_MAP[mois]
    risque, conf, probas  = predict(model, le, temperature, humidite,
                                    precipitation, vent, mois_num, ndvi)
    color                 = RISQUE_COLOR[risque]
    ind_sec               = round((temperature - humidite) / (precipitation + 0.1), 2)

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="app-header">
        <h1>🔥 Agdez · Prédiction Risque Incendie de Forêt</h1>
        <p>Incendie 2025 · Random Forest ML · Drâa-Tafilalet, Maroc · 30.69°N 6.45°W · Alt. {ALTITUDE} m</p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpis = [
        (k1, RISQUE_EMOJI[risque] + " " + risque, f"{mois} {annee}", color),
        (k2, f"{conf:.0%}", "Confiance modèle",   C_BLUE),
        (k3, "388.51 ha",   "Surface brûlée 2025", C_PRIMARY),
        (k4, "5.96%",       "% zone brûlée 2025",  C_ACCENT),
        (k5, "0.1443",      "NDVI avant incendie",  C_GREEN),
        (k6, "0.5928",      "dNBR max (sévérité)",  "#a855f7"),
    ]
    for col, val, lbl, clr in kpis:
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:{clr}">{val}</div>
            <div class="kpi-label">{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── ONGLETS ──────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "🗺️ Carte & Risque",
        "🌡️ Climatologie",
        "🔥 Incendie 2025",
        "🛰️ Indices Spectraux",
        "📋 Scénarios 2026",
        "🔔 Alertes",
        "🗓️ FVT",
        "🌍 Projections CC",
        "🧮 Comparateur",
        "📄 Rapport & Données",
    ])

    # =========================================================================
    # TAB 1 — Carte & Risque
    # =========================================================================
    with tabs[0]:
        col_map, col_info = st.columns([3, 1])
        with col_map:
            st.markdown('<div class="sec-title">Carte de risque — Agdez</div>',
                        unsafe_allow_html=True)
            carte    = make_map(risque, conf, probas, temperature,
                                humidite, precipitation, vent, mois, annee)
            map_data = st_folium(carte, width="100%", height=490,
                                 returned_objects=["last_object_clicked"])

        with col_info:
            clicked = (map_data and map_data.get("last_object_clicked") and
                       map_data["last_object_clicked"].get("lat") is not None)
            st.markdown(f'<div class="sec-title">{"📍 Point cliqué" if clicked else "📍 Informations"}</div>',
                        unsafe_allow_html=True)
            # Badge risque
            st.markdown(f"""
            <div style="text-align:center;padding:16px;background:{RISQUE_BG[risque]};
                        border-radius:12px;border:2px solid {color};margin-bottom:14px">
                <div style="font-size:2.2rem">{RISQUE_EMOJI[risque]}</div>
                <div style="font-size:1.3rem;font-weight:800;color:{color}">{risque}</div>
                <div style="font-size:0.8rem;color:#666">{conf:.0%} · {mois} {annee}</div>
            </div>""", unsafe_allow_html=True)
            # Jauge
            st.plotly_chart(fig_proba_gauge(probas, risque), width="stretch",
                            config={"displayModeBar": False})
            # Météo
            st.markdown(f"""
            <div class="info-box" style="font-size:0.78rem;line-height:2;
                        font-family:'Space Mono',monospace">
            📅 <b>{mois} {annee}</b><br>
            🌡️ Température : <b>{temperature}°C</b><br>
            💧 Humidité : <b>{humidite}%</b><br>
            🌧️ Précipitations : <b>{precipitation} mm</b><br>
            💨 Vent : <b>{vent} m/s</b><br>
            🌿 NDVI : <b>{ndvi:.3f}</b><br>
            🔥 Ind. sécheresse : <b>{ind_sec:.2f}</b><br>
            ⛰️ Altitude : <b>{ALTITUDE} m</b><br>
            📐 Pente : <b>{PENTE}°</b><br>
            🧭 Exposition : <b>165.51° (S-E)</b>
            </div>""", unsafe_allow_html=True)
            # Barres probabilités
            st.markdown('<div class="sec-title" style="margin-top:10px">Probabilités</div>',
                        unsafe_allow_html=True)
            for cls, p in probas.items():
                clr = RISQUE_COLOR.get(cls, "#888")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px">
                  <div style="width:75px;font-size:0.7rem;font-family:'Space Mono',monospace;
                              color:{C_MUTED}">{cls}</div>
                  <div style="flex:1;background:#222;border-radius:4px;height:9px">
                    <div style="background:{clr};width:{p*100:.0f}%;height:9px;border-radius:4px"></div>
                  </div>
                  <div style="width:32px;font-size:0.7rem;font-family:'Space Mono',monospace;
                              color:{C_MUTED};text-align:right">{p:.0%}</div>
                </div>""", unsafe_allow_html=True)
            # Recommandation
            st.markdown(f"""
            <div style="background:#111;border-radius:8px;padding:10px;margin-top:10px;
                        border-left:3px solid {color};font-size:0.8rem;line-height:1.6">
            {recommendation(risque)}
            </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 2 — Climatologie
    # =========================================================================
    with tabs[1]:
        st.markdown('<div class="sec-title">Analyse climatique — Agdez 2017–2025</div>',
                    unsafe_allow_html=True)
        df_ann = D["annuelles"]
        df_ete = D["ete"]

        if df_ann is not None:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_annuelles(df_ann), width="stretch")
            with c2:
                st.plotly_chart(fig_anomalies(df_ann), width="stretch")

            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(fig_precipitations(df_ann), width="stretch")
            with c4:
                st.plotly_chart(fig_vent_humidite(df_ann), width="stretch")

        if df_ete is not None:
            c5, c6 = st.columns(2)
            with c5:
                st.plotly_chart(fig_ete_bars(df_ete), width="stretch")
            with c6:
                st.plotly_chart(fig_ombrothermique(df_ann), width="stretch")

        # Statistiques récap
        st.markdown("---")
        st.markdown('<div class="sec-title">Statistiques globales (2017–2025)</div>',
                    unsafe_allow_html=True)
        if D["stats_recap"] is not None:
            cols = st.columns(len(D["stats_recap"]))
            for i, (_, row) in enumerate(D["stats_recap"].iterrows()):
                cols[i].metric(row["Statistique"], row["Valeur"])

        # Tableau données annuelles
        st.markdown('<div class="sec-title" style="margin-top:14px">Données climatiques annuelles</div>',
                    unsafe_allow_html=True)
        if df_ann is not None:
            st.dataframe(df_ann.style.format({
                "Température (°C)": "{:.2f}",
                "Humidité (%)":     "{:.2f}",
                "Précipitations (mm)": "{:.2f}",
                "Vent (m/s)":       "{:.2f}",
            }), width="stretch")

        # Galerie graphiques climatiques
        st.markdown("---")
        st.markdown('<div class="sec-title">Graphiques ETL — Climatologie</div>',
                    unsafe_allow_html=True)
        images_clim = [
            ("anomalies_de_temperature.jpg",  "Anomalies température estivale"),
            ("diagramme_ombrothermique.jpg",   "Diagramme ombrothermique 2025"),
            ("graphique_evolution_temperature.png", "Évolution température (2017-2025)"),
            ("graphique_temperatures_ete.png", "Températures été 2025"),
            ("graphique_comparaison_ete_moyenne.png","Comparaison été vs moyenne"),
            ("LES_DONNES_CLIMATIQUE_.jpg",     "Données climatiques complètes"),
        ]
        cols_img = st.columns(3)
        for i, (fname, title) in enumerate(images_clim):
            p = IMG_DIR / fname
            if p.exists():
                with cols_img[i % 3]:
                    st.image(str(p), caption=title, use_container_width=True)

        # Tableaux images
        st.markdown('<div class="sec-title" style="margin-top:14px">Tableaux statistiques (ETL)</div>',
                    unsafe_allow_html=True)
        tabs_imgs = [
            ("table_clim_statistiques_tableaux.png", "Statistiques climatiques 2017-2025"),
            ("tableau_statistiques_climat_1_.png",   "Tableau statistiques climat"),
        ]
        c_t1, c_t2 = st.columns(2)
        for i, (fname, title) in enumerate(tabs_imgs):
            p = IMG_DIR / fname
            if p.exists():
                [c_t1, c_t2][i].image(str(p), caption=title, use_container_width=True)

    # =========================================================================
    # TAB 3 — Incendie 2025
    # =========================================================================
    with tabs[2]:
        st.markdown('<div class="sec-title">Incendie Agdez — 15 Septembre 2025</div>',
                    unsafe_allow_html=True)

        df_sev = D["severity"]
        df_sum = D["summary"]
        df_rec = D["recap"]

        if df_sum is not None:
            row = df_sum.iloc[0]
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Zone",               row.get("Zone","—"))
            m2.metric("Surface totale",     f"{row.get('Surface totale (ha)',0):.1f} ha")
            m3.metric("Surface brûlée",     f"{row.get('Surface brûlée (ha)',0):.2f} ha")
            m4.metric("% brûlé",            f"{row.get('Pourcentage brûlé (%)',0):.2f}%")
            m5.metric("Date incendie",      str(row.get("Date incendie","—")))

        st.markdown("---")
        if df_sev is not None:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_severity_pie(df_sev), width="stretch")
            with c2:
                st.plotly_chart(fig_severity_bars(df_sev), width="stretch")

            st.markdown('<div class="sec-title">Classes de sévérité détaillées</div>',
                        unsafe_allow_html=True)
            st.dataframe(df_sev, width="stretch")

        # Récapitulatif climat-incendie
        if df_rec is not None:
            st.markdown("---")
            st.markdown('<div class="sec-title">Récapitulatif facteurs climat → incendie</div>',
                        unsafe_allow_html=True)
            for _, row in df_rec.iterrows():
                imp = str(row.get("Impact",""))
                col_imp = C_PRIMARY if "haut" in imp.lower() or "feu" in imp.lower() else C_ACCENT
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:8px 12px;
                            background:{C_CARD};border-radius:6px;margin-bottom:6px;
                            border-left:3px solid {col_imp}">
                  <span style="color:{C_TEXT};font-size:0.85rem">{row['Facteur']}</span>
                  <span style="font-family:'Space Mono',monospace;font-size:0.85rem;
                               color:#ddd;font-weight:bold">{row['Valeur']}</span>
                  <span style="font-size:0.78rem;color:{col_imp}">{imp}</span>
                </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 4 — Indices Spectraux
    # =========================================================================
    with tabs[3]:
        st.markdown('<div class="sec-title">Indices spectraux — NDVI · NBR · dNBR</div>',
                    unsafe_allow_html=True)

        df_idx = D["indices"]
        if df_idx is not None:
            # Stats
            i1, i2, i3 = st.columns(3)
            for col_st, row in zip([i1, i2, i3], df_idx.itertuples()):
                col_st.metric(row.Indice,
                              f"Moy: {row.Moyenne:.4f}",
                              f"Max: {row.Maximum:.4f}")

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_ndvi_change(df_idx), width="stretch")
            with c2:
                st.plotly_chart(fig_indices_radar(df_idx), width="stretch")

            # Tableau complet
            st.markdown('<div class="sec-title" style="margin-top:10px">Statistiques indices spectraux</div>',
                        unsafe_allow_html=True)
            st.dataframe(df_idx.style.format({
                "Moyenne": "{:.6f}", "Minimum": "{:.6f}",
                "Maximum": "{:.6f}", "Écart-type": "{:.6f}",
            }), width="stretch")

        # Métriques dNBR depuis summary
        if D["summary"] is not None:
            row = D["summary"].iloc[0]
            st.markdown("---")
            st.markdown('<div class="sec-title">Métriques dNBR — Incendie 2025</div>',
                        unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("NDVI avant",  f"{row.get('NDVI avant',0):.4f}")
            d2.metric("NDVI après",  f"{row.get('NDVI après',0):.4f}")
            d3.metric("dNBR moyen",  f"{row.get('dNBR moyen',0):.4f}")
            d4.metric("dNBR max",    f"{row.get('dNBR max',0):.4f}")

            # Interprétation dNBR
            st.markdown('<div class="sec-title" style="margin-top:14px">Interprétation dNBR</div>',
                        unsafe_allow_html=True)
            dnbr_classes = [
                ("<-0.10", "Régénération végétale",    C_GREEN),
                ("-0.10 – 0.10","Non brûlé",           C_MUTED),
                ("0.10 – 0.27","Sévérité faible",       C_ACCENT),
                ("0.27 – 0.44","Sévérité modérée",      "#e67e22"),
                ("0.44 – 0.66","Sévérité élevée ←",    C_PRIMARY),
                (">0.66",      "Sévérité très élevée",  "#8e1a1a"),
            ]
            for rng, lbl, clr in dnbr_classes:
                active = "border-left:4px solid" if "←" in lbl else "border-left:2px solid"
                st.markdown(f"""
                <div style="display:flex;gap:12px;padding:6px 10px;margin-bottom:4px;
                            background:{C_CARD};border-radius:5px;{active} {clr}">
                  <span style="font-family:'Space Mono',monospace;font-size:0.75rem;
                               color:{C_MUTED};width:110px">{rng}</span>
                  <span style="font-size:0.82rem;color:{clr}">{lbl}</span>
                </div>""", unsafe_allow_html=True)

        # Distribution pente
        st.markdown("---")
        st.markdown('<div class="sec-title">Topographie — Distribution de la pente</div>',
                    unsafe_allow_html=True)
        p_img = IMG_DIR / "distribution_pente.png"
        if p_img.exists():
            c_p1, c_p2 = st.columns([2, 1])
            with c_p1:
                st.image(str(p_img), caption="Distribution de la pente — Agdez",
                         use_container_width=True)
            with c_p2:
                st.markdown(f"""
                <div class="info-box" style="font-size:0.82rem;line-height:2.1">
                <b>Statistiques topographiques</b><br>
                📐 Pente moyenne : <b>5.73°</b><br>
                ⛰️ Altitude : <b>1 169.3 m</b><br>
                🧭 Exposition : <b>165.51° (Sud-Est)</b><br>
                📏 Surface analysée : <b>6 520.8 ha</b><br>
                🔥 Surface brûlée : <b>388.51 ha</b><br>
                <span style="color:{C_MUTED};font-size:0.75rem">
                Zone à pente faible → propagation latérale<br>
                Exposition Sud-Est → ensoleillement max
                </span>
                </div>""", unsafe_allow_html=True)

    # =========================================================================
    # TAB 5 — Scénarios 2026
    # =========================================================================
    with tabs[4]:
        st.markdown('<div class="sec-title">Scénarios de prédiction 2026</div>',
                    unsafe_allow_html=True)
        df_sc = D["scenarios"]
        if df_sc is not None:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_scenarios_confidence(df_sc), width="stretch")
            with c2:
                st.plotly_chart(fig_scenarios_radar_chart(df_sc), width="stretch")

            # Distribution risques
            cnt = df_sc["risque_predit"].value_counts().reset_index()
            cnt.columns = ["risque", "count"]
            fig_cnt = px.bar(cnt, x="risque", y="count", color="risque",
                             color_discrete_map=RP, title="Distribution des risques prédits")
            fig_cnt.update_layout(**DARK, showlegend=False)
            st.plotly_chart(fig_cnt, width="stretch")

            # Filtre + tableau
            cats = ["Tous"] + sorted(df_sc["categorie"].unique().tolist())
            cat  = st.selectbox("Filtrer par catégorie", cats)
            df_show = df_sc if cat == "Tous" else df_sc[df_sc["categorie"] == cat]
            cols_d  = ["categorie","scenario","mois","temperature","humidite",
                       "precipitation","vent","risque_predit","confiance"]
            # FIX applymap → map
            styled = df_show[cols_d].style.map(style_risque, subset=["risque_predit"])
            st.dataframe(styled, width="stretch", height=320)

            csv_b = df_sc.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exporter CSV scénarios", data=csv_b,
                               file_name="scenarios_2026.csv", mime="text/csv")
        else:
            st.warning("⚠️ predictions_scenarios_2026.csv introuvable.")

    # =========================================================================
    # TAB 6 — Alertes
    # =========================================================================
    with tabs[5]:
        st.markdown('<div class="sec-title">Système d\'alertes précoces</div>',
                    unsafe_allow_html=True)
        alertes = D["alertes"]
        if alertes:
            nb_c = sum(1 for a in alertes if a.get("priorite") == "CRITIQUE")
            nb_h = sum(1 for a in alertes if a.get("priorite") == "HAUTE")
            a1, a2, a3 = st.columns(3)
            a1.metric("🔴 Critiques", nb_c)
            a2.metric("🟠 Hautes",    nb_h)
            a3.metric("📋 Total",     len(alertes))
            st.markdown("---")
            for a in alertes:
                prio = a.get("priorite","")
                css  = "critique" if prio == "CRITIQUE" else "haute"
                tag  = "tag-crit"  if prio == "CRITIQUE" else "tag-haute"
                try:
                    ts = datetime.fromisoformat(a.get("timestamp","")).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    ts = a.get("timestamp","—")
                st.markdown(f"""
                <div class="alert-{css}">
                  <span class="tag {tag}">⚡ {prio}</span>
                  <div style="font-weight:700;font-size:0.92rem;margin:4px 0">
                    {a.get('scenario','—')}
                  </div>
                  <div style="font-size:0.8rem;color:#aaa;line-height:1.7">
                    📍 {a.get('zone','')}, {a.get('pays','')} &nbsp;|&nbsp;
                    📊 <b>{a.get('risque','')}</b> — Confiance : {a.get('confiance',0):.0%}<br>
                    🕐 {ts}<br>💬 {a.get('message','')}
                  </div>
                </div>""", unsafe_allow_html=True)

            # Graphique confiance des alertes
            df_al = pd.DataFrame([{
                "scenario":  a.get("scenario",""),
                "priorite":  a.get("priorite",""),
                "confiance": a.get("confiance",0) * 100,
            } for a in alertes])
            fig_al = px.bar(df_al, x="scenario", y="confiance", color="priorite",
                            color_discrete_map={"CRITIQUE":C_PRIMARY,"HAUTE":C_ACCENT},
                            title="Confiance par alerte (%)", text="confiance")
            fig_al.update_layout(**DARK, xaxis_tickangle=-20)
            fig_al.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            st.plotly_chart(fig_al, width="stretch")
        else:
            st.info("ℹ️ Aucun fichier alerte trouvé dans reports/")

    # =========================================================================
    # TAB 7 — FVT
    # =========================================================================
    with tabs[6]:
        st.markdown('<div class="sec-title">Fenêtre de Vulnérabilité Temporelle — Été 2026</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        > **Concept original** : simulation journalière (92 jours) pour identifier les fenêtres
        > *continues* de risque critique — utile pour planifier les ressources de surveillance.
        """)
        with st.spinner("Simulation 92 jours en cours…"):
            fig_fvt, df_fvt = fig_fvt_heatmap(model, le)
        st.plotly_chart(fig_fvt, width="stretch")

        n_te = (df_fvt["risque"] == "Très élevé").sum()
        n_el = (df_fvt["risque"] == "Élevé").sum()
        n_cr = n_te + n_el
        n_ok = 92 - n_cr

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("🔴 Très élevé",   n_te)
        v2.metric("🟠 Élevé",        n_el)
        v3.metric("⚠️ Critiques total", n_cr)
        v4.metric("✅ Jours sûrs",    n_ok)

        # Fenêtres continues
        st.markdown("---")
        st.markdown('<div class="sec-title">Fenêtres continues identifiées</div>',
                    unsafe_allow_html=True)
        df_fvt["is_c"] = df_fvt["risque"].isin(["Élevé","Très élevé"])
        wins, in_w, start = [], False, None
        for _, r in df_fvt.iterrows():
            if r["is_c"] and not in_w:
                in_w, start = True, r["date"]
            elif not r["is_c"] and in_w:
                in_w = False
                wins.append({"Début": start.strftime("%d/%m/%Y"),
                             "Fin": (r["date"] - pd.Timedelta(days=1)).strftime("%d/%m/%Y"),
                             "Durée (jours)": (r["date"] - start).days})
        if in_w:
            wins.append({"Début": start.strftime("%d/%m/%Y"),
                         "Fin":   df_fvt["date"].iloc[-1].strftime("%d/%m/%Y"),
                         "Durée (jours)": (df_fvt["date"].iloc[-1] - start).days + 1})
        if wins:
            df_w = pd.DataFrame(wins).sort_values("Durée (jours)", ascending=False)
            st.dataframe(df_w, width="stretch")
            st.error(f"⚠️ Fenêtre principale : **{df_w.iloc[0]['Début']} → {df_w.iloc[0]['Fin']}** "
                     f"= **{df_w.iloc[0]['Durée (jours)']} jours consécutifs**")

        # Distribution T par risque
        fig_d = px.box(df_fvt, x="risque", y="temperature", color="risque",
                       color_discrete_map=RP,
                       title="Distribution température par niveau de risque",
                       category_orders={"risque":["Faible","Moyen","Élevé","Très élevé"]})
        fig_d.update_layout(**DARK, showlegend=False)
        st.plotly_chart(fig_d, width="stretch")

    # =========================================================================
    # TAB 8 — Projections CC
    # =========================================================================
    with tabs[7]:
        st.markdown('<div class="sec-title">Projections climatiques 2026–2035 (juillet)</div>',
                    unsafe_allow_html=True)
        df_proj = D["projections"]
        if df_proj is not None:
            st.markdown("""
            > Tendances par **régression linéaire** sur 2017–2025.
            > Toutes les années projetées sont classées **"Très élevé"**.
            """)
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_projections_temp(df_proj), width="stretch")
            with c2:
                st.plotly_chart(fig_projections_confiance(df_proj), width="stretch")

            # Température + humidité simultanément
            fig_th = go.Figure()
            fig_th.add_trace(go.Scatter(x=df_proj["annee"], y=df_proj["temperature"],
                name="Température (°C)", line=dict(color=C_PRIMARY, width=3),
                mode="lines+markers"))
            fig_th.add_trace(go.Scatter(x=df_proj["annee"], y=df_proj["humidite"],
                name="Humidité (%)", line=dict(color=C_BLUE, width=2, dash="dot"),
                mode="lines+markers", yaxis="y2"))
            fig_th.update_layout(
                title="Température & Humidité projetées 2026–2035",
                yaxis=dict(title="Température (°C)", color=C_PRIMARY),
                yaxis2=dict(title="Humidité (%)", color=C_BLUE,
                            overlaying="y", side="right"),
                **DARK,
            )
            st.plotly_chart(fig_th, width="stretch")

            st.markdown('<div class="sec-title">Tableau des projections</div>',
                        unsafe_allow_html=True)
            cols_p = ["annee","temperature","humidite","precipitation","vent",
                      "risque_predit","confiance"]
            st.dataframe(
                df_proj[cols_p].style
                .format({"temperature":"{:.2f}°C","humidite":"{:.2f}%",
                         "precipitation":"{:.2f} mm","vent":"{:.3f} m/s",
                         "confiance":"{:.0%}"})
                .map(style_risque, subset=["risque_predit"]),   # FIX: map pas applymap
                width="stretch",
            )
        else:
            st.warning("⚠️ projections_climatiques.csv introuvable.")

    # =========================================================================
    # TAB 9 — Comparateur d'années
    # =========================================================================
    with tabs[8]:
        st.markdown('<div class="sec-title">Comparateur d\'années — Projections</div>',
                    unsafe_allow_html=True)
        df_proj = D["projections"]
        if df_proj is not None:
            all_y = sorted(df_proj["annee"].unique().tolist())
            ca1, ca2 = st.columns(2)
            with ca1:
                yr_a = st.selectbox("Année A", all_y, index=0, key="cmp_a")
            with ca2:
                yr_b = st.selectbox("Année B", all_y, index=min(4, len(all_y)-1), key="cmp_b")

            ra = df_proj[df_proj["annee"] == yr_a].iloc[0]
            rb = df_proj[df_proj["annee"] == yr_b].iloc[0]
            la, ca2v, pa = predict(model, le, ra["temperature"], ra["humidite"],
                                   ra["precipitation"], ra["vent"], 1)
            lb, cb, pb   = predict(model, le, rb["temperature"], rb["humidite"],
                                   rb["precipitation"], rb["vent"], 1)

            def year_card(col, yr, row, lbl, cnf):
                c = RISQUE_COLOR.get(lbl, "#888")
                col.markdown(f"""
                <div style="text-align:center;padding:14px;background:{RISQUE_BG.get(lbl,'#111')};
                            border-radius:12px;border:2px solid {c};margin-bottom:12px">
                  <div style="font-size:1.8rem">{RISQUE_EMOJI.get(lbl,'⚪')}</div>
                  <div style="font-size:1.4rem;font-weight:800;color:{c}">{yr}</div>
                  <div style="font-size:0.9rem;color:{c};font-weight:600">{lbl}</div>
                  <div style="font-size:0.75rem;color:#666">{cnf:.0%} confiance</div>
                </div>""", unsafe_allow_html=True)
                for lbl_v, val in [("🌡️ T°C", f"{row['temperature']:.1f}°C"),
                                   ("💧 H%",  f"{row['humidite']:.1f}%"),
                                   ("🌧️ P mm",f"{row['precipitation']:.1f}mm"),
                                   ("💨 V m/s",f"{row['vent']:.2f}m/s")]:
                    col.markdown(f"""
                    <div style="display:flex;justify-content:space-between;padding:5px 8px;
                                background:#111;border-radius:5px;margin-bottom:4px;
                                font-family:'Space Mono',monospace;font-size:0.75rem">
                      <span style="color:{C_MUTED}">{lbl_v}</span>
                      <span style="color:#ddd;font-weight:bold">{val}</span>
                    </div>""", unsafe_allow_html=True)

            col_a, col_sep, col_b = st.columns([5, 1, 5])
            year_card(col_a, yr_a, ra, la, ca2v)
            col_sep.markdown("<div style='text-align:center;padding-top:70px;font-size:1.4rem'>VS</div>",
                             unsafe_allow_html=True)
            year_card(col_b, yr_b, rb, lb, cb)

            # Graphique comparatif
            vars_c  = ["temperature","humidite","precipitation","vent"]
            lbls_c  = ["T (°C)","H (%)","P (mm)","V (m/s)"]
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(name=str(yr_a), x=lbls_c,
                y=[ra[v] for v in vars_c], marker_color=RISQUE_COLOR.get(la,"#888"),
                text=[f"{ra[v]:.1f}" for v in vars_c], textposition="outside"))
            fig_cmp.add_trace(go.Bar(name=str(yr_b), x=lbls_c,
                y=[rb[v] for v in vars_c], marker_color=RISQUE_COLOR.get(lb,"#555"),
                text=[f"{rb[v]:.1f}" for v in vars_c], textposition="outside"))
            fig_cmp.update_layout(title=f"Comparaison juillet — {yr_a} vs {yr_b}",
                                  barmode="group", **DARK)
            st.plotly_chart(fig_cmp, width="stretch")

            # Deltas
            st.markdown('<div class="sec-title">Évolution entre les deux années</div>',
                        unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            for col_d, nm, va, vb, unit in [
                (d1,"🌡️ Température",ra["temperature"],rb["temperature"],"°C"),
                (d2,"💧 Humidité",   ra["humidite"],   rb["humidite"],  "%"),
                (d3,"🌧️ Pluie",      ra["precipitation"],rb["precipitation"],"mm"),
                (d4,"💨 Vent",       ra["vent"],        rb["vent"],      "m/s"),
            ]:
                col_d.metric(nm, f"{vb:.1f}{unit}", f"{vb-va:+.1f}{unit}")
        else:
            st.warning("⚠️ projections_climatiques.csv introuvable.")

    # =========================================================================
    # TAB 10 — Rapport & Données
    # =========================================================================
    with tabs[9]:
        st.markdown('<div class="sec-title">Rapport de prédiction & données complètes</div>',
                    unsafe_allow_html=True)

        # Feature importance
        df_fi = D["fi"]
        if df_fi is not None:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.plotly_chart(fig_fi_bars(df_fi), width="stretch")
            with c2:
                st.markdown('<div class="sec-title">Top 3 features</div>',
                            unsafe_allow_html=True)
                for _, row in df_fi.nlargest(3, "importance").iterrows():
                    pct = row["importance"] * 100
                    st.markdown(f"""
                    <div style="background:#111;border-radius:8px;padding:10px;
                                margin-bottom:8px;border-left:3px solid {C_ACCENT}">
                      <div style="font-family:'Space Mono',monospace;font-size:0.78rem">{row['feature']}</div>
                      <div style="background:#222;border-radius:4px;height:8px;margin-top:6px">
                        <div style="background:linear-gradient(90deg,{C_ACCENT},{C_PRIMARY});
                                    width:{pct/0.20*100:.0f}%;height:8px;border-radius:4px;
                                    max-width:100%"></div>
                      </div>
                      <div style="font-size:0.72rem;color:{C_MUTED};margin-top:4px">{pct:.1f}%</div>
                    </div>""", unsafe_allow_html=True)

        # Modèle info
        mi = D["model_info"]
        if mi:
            st.markdown("---")
            st.markdown('<div class="sec-title">Informations du modèle</div>',
                        unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Algorithme",     mi.get("modele","—"))
            m2.metric("Accuracy CV",    f"{mi.get('accuracy_cv',0):.1%}")
            m3.metric("Écart-type",     f"±{mi.get('accuracy_cv_std',0):.1%}")
            m4.metric("Années train",   mi.get("annees_train","—"))

        # Rapport texte
        rpt = RPT_DIR / "rapport_prediction.txt"
        if rpt.exists():
            st.markdown("---")
            st.markdown('<div class="sec-title">Rapport texte complet</div>',
                        unsafe_allow_html=True)
            rpt_txt = rpt.read_text(encoding="utf-8")
            st.code(rpt_txt, language=None)
            c_dl1, c_dl2 = st.columns(2)
            c_dl1.download_button("⬇️ Rapport (.txt)", data=rpt_txt.encode("utf-8"),
                                  file_name="rapport_agdez.txt", mime="text/plain")
            syn = D["synthese"]
            if syn:
                c_dl2.download_button("⬇️ Synthèse (.json)",
                                      data=json.dumps(syn, ensure_ascii=False, indent=2).encode("utf-8"),
                                      file_name="synthese_risque.json",
                                      mime="application/json")

        # Données brutes CSVs
        st.markdown("---")
        st.markdown('<div class="sec-title">Données brutes</div>',
                    unsafe_allow_html=True)
        src_map = {
            "Conditions été 2025":      D["ete"],
            "Statistiques annuelles":   D["annuelles"],
            "Données prédiction":       D["prediction"],
            "Récap incendie":           D["recap"],
        }
        chosen = st.selectbox("Choisir un dataset", list(src_map.keys()))
        df_ch  = src_map[chosen]
        if df_ch is not None:
            st.dataframe(df_ch, width="stretch")
            st.download_button(f"⬇️ Télécharger {chosen}",
                               data=df_ch.to_csv(index=False).encode("utf-8"),
                               file_name=f"{chosen.replace(' ','_')}.csv",
                               mime="text/csv")

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center;font-family:'Space Mono',monospace;
                font-size:0.68rem;color:{C_MUTED};padding:8px 0">
        🔥 Agdez Wildfire Prediction · Random Forest v1.0.0 ·
        Données 2017–2025 · Drâa-Tafilalet, Maroc 🇲🇦
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()