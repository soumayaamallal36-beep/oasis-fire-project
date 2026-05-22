"""
Page 5 — Système de Prédiction
Interactive scenario simulator with real-time risk prediction.
"""

import sys
from pathlib import Path
from datetime import datetime

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from components.ui         import GLOBAL_CSS, section_header, risk_badge, kpi_card, glass_card
from components.prediction import predict_risk, risk_recommendation, RISK_COLORS, RISK_BG
from components.weather    import get_weather
from components.charts     import probability_bars, risk_gauge, scenario_chart

st.set_page_config(page_title="Prédiction · OASIS Fire", page_icon="🔮",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

SCENARIOS_CSV = PROJECT_ROOT / "models" / "metadata" / "predictions_scenarios_2026.csv"
MOIS_OPTIONS  = ["Juin", "Juillet", "Août"]

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔮 Simulateur de Prédiction")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    st.markdown("**⚙️ Paramètres d'entrée**")

    temperature = st.slider("🌡️ Température (°C)", 15.0, 45.0, 32.0, 0.1)
    humidite    = st.slider("💧 Humidité relative (%)", 5.0, 80.0, 16.0, 1.0)
    precipitation = st.slider("🌧️ Précipitations (mm)", 0.0, 60.0, 2.0, 0.5)
    vent        = st.slider("💨 Vitesse du vent (m/s)", 0.5, 15.0, 4.0, 0.1)
    mois        = st.selectbox("📅 Mois", MOIS_OPTIONS, index=1)
    ndvi        = st.slider("🌿 NDVI végétation", 0.05, 0.50, 0.144, 0.001)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**📋 Préréglages**")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🌡️ Canicule", use_container_width=True):
            st.session_state["preset"] = "canicule"
    with col_b:
        if st.button("🌧️ Après pluie", use_container_width=True):
            st.session_state["preset"] = "pluie"

    preset = st.session_state.get("preset")
    if preset == "canicule":
        temperature, humidite, precipitation, vent = 36.0, 12.0, 0.5, 5.5
        st.session_state.pop("preset", None)
    elif preset == "pluie":
        temperature, humidite, precipitation, vent = 27.0, 40.0, 35.0, 2.5
        st.session_state.pop("preset", None)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Risk Prediction Intelligence",
    "Interactive scenario simulator · Multi-variable risk assessment · Real-time IA inference",
    "🔮",
), unsafe_allow_html=True)

# ── Run prediction ────────────────────────────────────────────────
label, conf, probas = predict_risk(temperature, humidite, precipitation, vent, mois, ndvi)
reco = risk_recommendation(label)
risk_color = RISK_COLORS.get(label, "#8b949e")
risk_bg    = RISK_BG.get(label, "rgba(139,148,158,0.1)")

# ── Result banner ─────────────────────────────────────────────────
st.markdown(f"""
<div style='background:rgba({",".join(str(int(risk_color.lstrip("#")[i:i+2],16)) for i in (0,2,4))}, 0.05);
    border:1px solid {risk_color}30; border-left:5px solid {risk_color};
    border-radius:15px; padding:1.5rem 2rem; margin-bottom:2rem;
    display:flex; align-items:center; justify-content:space-between; backdrop-filter:blur(10px);'>
    <div>
        <div style='font-size:0.8rem; color:#8b949e; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:8px;'>Predictive Classification</div>
        <div style='font-size:2.8rem; font-weight:900; color:{risk_color}; font-family:Outfit,sans-serif; line-height:1;'>{label.upper()}</div>
        <div style='color:#f0f6fc; font-size:0.95rem; font-weight:500; margin-top:12px;'>{reco}</div>
    </div>
    <div style='text-align:right;'>
        <div style='font-size:0.8rem; color:#8b949e; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:8px;'>Model Confidence</div>
        <div style='font-size:3rem; font-weight:900; color:#f0f6fc; font-family:JetBrains Mono,monospace; line-height:1;'>{conf:.0%}<span style='font-size:1.2rem; color:#484f58;'>/100</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Charts & Params ──────────────────────────────────────────────────
col_viz, col_input = st.columns([3, 2])

with col_viz:
    inner_c1, inner_c2 = st.columns([1, 1.5])
    with inner_c1:
        st.plotly_chart(risk_gauge(label, conf), use_container_width=True, config={"displayModeBar": False})
    with inner_c2:
        st.plotly_chart(probability_bars(probas), use_container_width=True, config={"displayModeBar": False})
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
            <span style='font-size:1.2rem;'>🌐</span>
            <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                Comparative Analysis (Simulation vs Real-Time)
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    weather = get_weather()
    rt_label, rt_conf, rt_probas = predict_risk(weather["temperature"], weather["humidite"], weather["precipitation"], weather["vent"])
    
    c_sim, c_rt = st.columns(2)
    for col, lbl, cnf, src in [(c_sim, label, conf, "Simulation Scenario"), (c_rt, rt_label, rt_conf, "Live Station Telemetry")]:
        rc = RISK_COLORS.get(lbl, "#8b949e")
        with col:
            compare_html = f"""
            <div style='padding:5px 0;'>
                <div style='font-size:0.75rem; color:#8b949e; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:10px;'>{src}</div>
                <div style='font-size:1.5rem; font-weight:800; color:{rc};'>{lbl.upper()}</div>
                <div style='color:#484f58; font-size:0.85rem; font-weight:600; margin-top:5px;'>CONFIDENCE: {cnf:.0%}</div>
            </div>
            """
            st.markdown(glass_card(compare_html), unsafe_allow_html=True)

with col_input:
    param_html = ""
    params = [
        ("🌡️ Temperature", f"{temperature}°C"),
        ("💧 Humidity", f"{humidite:.0f}%"),
        ("🌧️ Precipitation", f"{precipitation:.1f} mm"),
        ("💨 Wind Speed", f"{vent:.1f} m/s"),
        ("📅 Month Index", mois),
        ("🌿 Vegetation NDVI", f"{ndvi:.3f}"),
    ]
    for name, val in params:
        param_html += f"""
        <div style='display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
            <span style='color:#8b949e; font-size:0.85rem;'>{name}</span>
            <span style='color:#f0f6fc; font-size:0.85rem; font-weight:700;'>{val}</span>
        </div>
        """
    st.markdown(glass_card(param_html, title="Parameter Snapshot", icon="📝"), unsafe_allow_html=True)

    # Derived Features
    ind_sec = (temperature - humidite) / (precipitation + 0.1)
    ind_prop = vent * np.sin(np.radians(5.73))
    stress   = (1 - ndvi) * temperature / 10
    
    derived_html = ""
    derived = [
        ("Aridity Index", f"{ind_sec:.3f}"),
        ("Propagation Potential", f"{ind_prop:.3f}"),
        ("Vegetal Water Stress", f"{stress:.3f}"),
    ]
    for name, val in derived:
        derived_html += f"""
        <div style='display:flex; justify-content:space-between; padding:8px 0;'>
            <span style='color:#484f58; font-size:0.8rem;'>{name}</span>
            <span style='font-family:JetBrains Mono; color:#8b949e; font-size:0.8rem;'>{val}</span>
        </div>
        """
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(glass_card(derived_html, title="Derived IA Features", icon="📐"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Scenario comparison ───────────────────────────────────────────
if SCENARIOS_CSV.exists():
    st.markdown("""
        <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
            <span style='font-size:1.2rem;'>📊</span>
            <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                2026 Reference Scenario Comparison
            </span>
        </div>
    """, unsafe_allow_html=True)
    df_sc = pd.read_csv(SCENARIOS_CSV)
    fig = scenario_chart(df_sc)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander("📋 Full Scenario Matrix Explorer"):
        df_show = df_sc[["categorie","scenario","temperature","humidite","precipitation","vent","risque_predit","confiance"]].copy()
        df_show["confiance"] = df_show["confiance"].apply(lambda x: f"{x:.0%}")
        df_show.columns = ["Category","Scenario","Temp.","Humidity","Rain","Wind","Risk","Confidence"]
        st.dataframe(df_show, use_container_width=True, hide_index=True)

