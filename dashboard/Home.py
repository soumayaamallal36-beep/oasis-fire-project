"""
OASIS Fire Project — Professional Dashboard
Main entry point: streamlit run dashboard/Home.py
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# ── Path setup ───────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.ui       import GLOBAL_CSS, kpi_card, risk_badge, alert_card, section_header, status_dot, glass_card, metric_group
from components.weather  import get_weather, wind_direction_label
from components.prediction import get_current_prediction, risk_recommendation, RISK_COLORS
from components.charts   import risk_gauge, probability_bars

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="OASIS Fire · Intelligence Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Global State ──────────────────────────────────────────────────
online = True  # Simulation: system is online

# ── Data paths ────────────────────────────────────────────────────
META_PATH     = PROJECT_ROOT / "models" / "metadata" / "model_info.json"
SCENARIOS_CSV = PROJECT_ROOT / "models" / "metadata" / "predictions_scenarios_2026.csv"
PROJ_CSV      = PROJECT_ROOT / "models" / "metadata" / "projections_climatiques.csv"
ALERTS_DIR    = PROJECT_ROOT / "reports"
LAST_ALERT    = PROJECT_ROOT / "data" / "meteo_daily" / "last_alert.json"

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:1rem 0 0.5rem;'>
        <div style='font-size:2rem;'>🔥</div>
        <div style='font-size:1.1rem;font-weight:700;color:#f0f6fc;'>OASIS Fire</div>
        <div style='font-size:0.75rem;color:#8b949e;margin-top:2px;'>
            Plateforme de surveillance incendie
        </div>
    </div>
    <hr style='border-color:#21262d;margin:0.8rem 0;'>
    """, unsafe_allow_html=True)

    st.markdown("**📍 Zone d'étude**")
    st.markdown("""
    <div style='background:#0d1117;border:1px solid #21262d;border-radius:8px;
                padding:0.7rem 0.9rem;font-size:0.82rem;color:#c9d1d9;'>
        <div>🇲🇦 <b>Agdez</b>, Maroc</div>
        <div style='color:#8b949e;margin-top:4px;'>30.697°N · 6.448°O</div>
        <div style='color:#8b949e;'>Altitude : 1 169 m</div>
        <div style='color:#8b949e;'>Pente moy. : 5.73°</div>
        <div style='color:#8b949e;'>Exposition : 165° SE</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if META_PATH.exists():
        with open(META_PATH) as f:
            meta = json.load(f)
        st.markdown("**🤖 Modèle IA**")
        st.markdown(f"""
        <div style='background:#0d1117;border:1px solid #21262d;border-radius:8px;
                    padding:0.7rem 0.9rem;font-size:0.82rem;color:#c9d1d9;'>
            <div>📦 {meta.get('modele','Random Forest')}</div>
            <div style='color:#8b949e;margin-top:4px;'>
                Précision CV : <b style='color:#3fb950;'>{meta.get('accuracy_cv',0):.1%}</b>
                ± {meta.get('accuracy_cv_std',0):.1%}
            </div>
            <div style='color:#8b949e;'>Période : {meta.get('annees_train','2017-2025')}</div>
            <div style='color:#8b949e;'>Features : {len(meta.get('features',[]))}</div>
            <div style='color:#8b949e;'>v{meta.get('version','1.0.0')}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.72rem;color:#484f58;text-align:center;'>"
                f"Mis à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>",
                unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────
with st.spinner("Chargement des données en temps réel…"):
    weather = get_weather()
    label, conf, probas = get_current_prediction(weather)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Wildfire Intelligence Dashboard",
    "Agdez, Province de Zagora, Maroc · Surveillance temps réel · IA Predictive",
    "🛰️"
), unsafe_allow_html=True)

# ── Row 1: KPI cards ──────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

risk_color = RISK_COLORS.get(label, "#8b949e")
with c1:
    st.markdown(kpi_card(
        "Risk Level", label.upper(),
        subtitle=f"Confiance {conf:.0%}",
        icon="🔥", color=risk_color,
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        "Temperature", f"{weather['temperature']:.1f}°C",
        icon="🌡️", color="#f0883e",
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card(
        "Humidity", f"{weather['humidite']:.0f}%",
        icon="💧", color="#58a6ff",
    ), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card(
        "Wind Speed", f"{weather['vent']:.1f} m/s",
        subtitle=wind_direction_label(weather.get("wind_direction", 0)),
        icon="💨", color="#8b5cf6",
    ), unsafe_allow_html=True)
with c5:
    st.markdown(kpi_card(
        "Precipitation", f"{weather['precipitation']:.1f} mm",
        icon="🌧️", color="#3fb950",
    ), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 2: System Telemetry (Using new metric_group) ──────────────
telemetry = [
    {"title": "Sensor Node", "value": "ONLINE", "icon": "📡", "color": "#3fb950"},
    {"title": "Sentinel L2A", "value": "SYNCED", "icon": "🛰️", "color": "#58a6ff"},
    {"title": "Model Latency", "value": "12ms", "icon": "⚡", "color": "#d29922"},
    {"title": "Burn Area", "value": "388.5 ha", "icon": "🔥", "color": "#f85149"},
]
st.markdown(metric_group(telemetry), unsafe_allow_html=True)

# ── Row 3: Gauge + Probabilities + Alerts ─────────────────────────
col_main, col_side = st.columns([3, 2])

with col_main:
    st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                Live Analysis & Prediction
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    inner_c1, inner_c2 = st.columns([1, 1.5])
    with inner_c1:
        st.plotly_chart(risk_gauge(label, conf), use_container_width=True, config={"displayModeBar": False})
        st.markdown(f"<div style='text-align:center; margin-top:-20px;'>{risk_badge(label, size='normal')}</div>", unsafe_allow_html=True)
    with inner_c2:
        st.plotly_chart(probability_bars(probas), use_container_width=True, config={"displayModeBar": False})

    # Scenarios summary
    st.markdown("<br>", unsafe_allow_html=True)
    if SCENARIOS_CSV.exists():
        df_sc = pd.read_csv(SCENARIOS_CSV)
        sc_content = ""
        for cat in df_sc["categorie"].unique():
            sub = df_sc[df_sc["categorie"] == cat]
            high = sub[sub["risque_predit"].isin(["Élevé", "Très élevé"])]
            color = "#f85149" if len(high) == len(sub) else ("#f0883e" if len(high) > 0 else "#3fb950")
            sc_content += f"""
<div style='display:flex;justify-content:space-between;align-items:center;
            padding:10px 0;border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
    <span style='color:#c9d1d9;font-size:0.85rem;font-weight:500;'>{cat}</span>
    <div style='display:flex; align-items:center; gap:10px;'>
        <div style='width:60px; height:6px; background:rgba(240, 246, 252, 0.05); border-radius:10px; overflow:hidden;'>
            <div style='width:{len(high)/len(sub)*100}%; height:100%; background:{color};'></div>
        </div>
        <span style='color:{color};font-size:0.8rem;font-weight:700;'>
            {len(high)}/{len(sub)} CRITICAL
        </span>
    </div>
</div>
""".strip()
        st.markdown(glass_card(sc_content, title="2026 Prediction Scenarios", icon="🔮"), unsafe_allow_html=True)

with col_side:
    st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                Alert Monitor & Recommendations
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    # Active Alert
    st.markdown(alert_card(
        f"CRITICAL RISK: {label}",
        risk_recommendation(label),
        level=label,
        timestamp=datetime.now().strftime("%H:%M · %d %b %Y"),
        scenario=f"T={weather['temperature']:.1f}°C · H={weather['humidite']:.0f}%",
    ), unsafe_allow_html=True)

    # Historical Projections Quick View
    if PROJ_CSV.exists():
        df_pr = pd.read_csv(PROJ_CSV).head(6)
        proj_content = ""
        for _, row in df_pr.iterrows():
            rc = RISK_COLORS.get(row["risque_predit"], "#8b949e")
            proj_content += f"""
<div style='display:flex;justify-content:space-between;align-items:center;
            padding:8px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
    <span style='color:#f0f6fc;font-size:0.85rem;font-weight:600;'>{int(row["annee"])}</span>
    <span style='color:#8b949e;font-size:0.8rem;'>{row["temperature"]:.1f}°C</span>
    <div style='display:flex; align-items:center; gap:6px;'>
        <span style='color:{rc};font-size:0.75rem;font-weight:700;'>{row["risque_predit"].upper()}</span>
        <span style='color:#484f58;font-size:0.7rem;'>{row["confiance"]:.0%}</span>
    </div>
</div>
""".strip()
        st.markdown(glass_card(proj_content, title="Climate Projections (2026+)", icon="📈"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Footer
st.markdown(f"""
<div style='text-align:center; margin-top:2rem; padding: 2rem; border-top: 1px solid rgba(240, 246, 252, 0.05);'>
    <div style='margin-bottom: 1rem;'>{status_dot(online)}</div>
    <div style='color:#484f58; font-size:0.75rem; font-weight:500;'>
        OASIS FIRE INTELLIGENCE PLATFORM · AGDEZ, MAROC<br>
        DATA SOURCES: NASA POWER · COPERNICUS SENTINEL-2 · OPEN-METEO API
    </div>
</div>
""", unsafe_allow_html=True)

