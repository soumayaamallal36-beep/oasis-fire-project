"""
Page 1 — Météo Temps Réel
Real-time weather from Open-Meteo API with trend charts and history.
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

from components.ui      import GLOBAL_CSS, kpi_card, section_header, status_dot, glass_card
from components.weather import get_weather, wind_direction_label, wmo_description, HISTORY_CSV
from components.charts  import hourly_trend

st.set_page_config(page_title="Météo · OASIS Fire", page_icon="🌡️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌡️ Météo Temps Réel")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    st.markdown("**Source de données**")
    st.markdown("""
    <div style='font-size:0.8rem;color:#8b949e;background:#0d1117;
                border:1px solid #21262d;border-radius:8px;padding:0.7rem;'>
        🌐 Open-Meteo API<br>
        📍 Agdez (30.69°N, 6.45°O)<br>
        🔄 Rafraîchi toutes les 5 min<br>
        📦 Cache JSON en fallback
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 Rafraîchir maintenant", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Real-Time Weather Monitor",
    "Current atmospheric conditions · Agdez Station · Open-Meteo Integration",
    "🌡️",
), unsafe_allow_html=True)

# ── Fetch data ────────────────────────────────────────────────────
with st.spinner("Fetching weather telemetry…"):
    weather = get_weather()

src    = weather.get("source", "fallback")
online = src == "api"
ts     = weather.get("timestamp", "")[:16].replace("T", " ")
emoji  = weather.get("weather_emoji", "🌡️")
desc   = weather.get("weather_desc", "")

# ── Status banner ─────────────────────────────────────────────────
src_colors = {"api": ("#3fb950", "SYSTEM OPERATIONAL"),
              "cache": ("#d29922", "CACHE MODE"),
              "fallback": ("#f85149", "FALLBACK MODE")}
src_color, src_label = src_colors.get(src, ("#8b949e", "UNKNOWN"))

st.markdown(f"""
<div style='background:rgba({",".join(str(int(src_color.lstrip("#")[i:i+2],16))
    for i in (0,2,4))},0.05);
    border:1px solid {src_color}30; border-left:4px solid {src_color};
    border-radius:12px; padding:0.8rem 1.2rem; margin-bottom:1.5rem;
    display:flex; align-items:center; justify-content:space-between;
    backdrop-filter: blur(5px);'>
    <div style='display:flex; align-items:center; gap:12px;'>
        <span style='width:10px; height:10px; background:{src_color}; border-radius:50%; box-shadow:0 0 10px {src_color};'></span>
        <span style='color:{src_color}; font-size:0.85rem; font-weight:700; letter-spacing:0.05em;'>{src_label}</span>
    </div>
    <span style='color:#f0f6fc; font-size:0.85rem; font-weight:500;'>
        {emoji} {desc.upper()} <span style='color:#484f58; margin: 0 10px;'>|</span> <span style='color:#8b949e; font-size:0.8rem;'>LAST SYNC: {ts}</span>
    </span>
</div>
""", unsafe_allow_html=True)

# ── KPI cards ─────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card(
        "Temperature", f"{weather['temperature']:.1f}°C",
        icon="🌡️", color="#f0883e",
        subtitle="Current air temp (2m)",
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        "Humidity", f"{weather['humidite']:.0f}%",
        icon="💧", color="#58a6ff",
        subtitle="Relative humidity",
    ), unsafe_allow_html=True)
with c3:
    wd = wind_direction_label(weather.get("wind_direction", 0))
    st.markdown(kpi_card(
        "Wind Speed", f"{weather['vent']:.1f} m/s",
        icon="💨", color="#8b5cf6",
        subtitle=f"Direction: {wd} ({weather.get('wind_direction', 0):.0f}°)",
    ), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card(
        "Precipitation", f"{weather['precipitation']:.1f} mm",
        icon="🌧️", color="#3fb950",
        subtitle="Hourly accumulation",
    ), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Hourly trend ──────────────────────────────────────────
col_chart, col_info = st.columns([2.5, 1])

with col_chart:
    hourly = weather.get("hourly", {})
    if hourly and "time" in hourly:
        fig = hourly_trend(hourly)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(glass_card("""
            <div style='text-align:center; padding:3rem; color:#484f58;'>
                <div style='font-size:3rem; margin-bottom:15px;'>📡</div>
                <div style='font-weight:600;'>Hourly Data Unavailable</div>
                <div style='font-size:0.8rem; margin-top:5px;'>Please check API connection for real-time trends</div>
            </div>
        """), unsafe_allow_html=True)

with col_info:
    t, h, v, p = weather["temperature"], weather["humidite"], weather["vent"], weather["precipitation"]
    
    analysis_html = ""
    conditions = []
    if t >= 35:   conditions.append(("🔴", "Extreme Temp (>35°C)", "#f85149"))
    elif t >= 30: conditions.append(("🟠", "High Temp (>30°C)", "#f0883e"))
    else:         conditions.append(("🟢", "Normal Temp", "#3fb950"))

    if h <= 15:   conditions.append(("🔴", "Critical Humidity (<15%)", "#f85149"))
    elif h <= 25: conditions.append(("🟠", "Low Humidity (<25%)", "#f0883e"))
    else:         conditions.append(("🟢", "Optimal Humidity", "#3fb950"))

    if v >= 6:    conditions.append(("🔴", "High Wind (≥6 m/s)", "#f85149"))
    elif v >= 4:  conditions.append(("🟡", "Moderate Wind", "#d29922"))
    else:         conditions.append(("🟢", "Low Wind", "#3fb950"))

    if p == 0:    conditions.append(("🟡", "Zero Precipitation", "#d29922"))
    elif p >= 10: conditions.append(("🟢", "Significant Rain", "#3fb950"))
    else:         conditions.append(("🟢", "Light Rain", "#3fb950"))

    for icon, label, color in conditions:
        analysis_html += f"""
        <div style='padding:12px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);
                    display:flex; align-items:center; gap:12px;'>
            <span style='font-size:1.1rem;'>{icon}</span>
            <span style='color:{color}; font-size:0.85rem; font-weight:600;'>{label.upper()}</span>
        </div>
        """
    st.markdown(glass_card(analysis_html, title="Atmospheric Analysis", icon="📊"), unsafe_allow_html=True)

# ── Historical data ───────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
    <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
        <span style='font-size:1.2rem;'>📅</span>
        <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
            Historical Telemetry Logs
        </span>
    </div>
""", unsafe_allow_html=True)

if HISTORY_CSV.exists():
    df_hist = pd.read_csv(HISTORY_CSV).sort_values("timestamp", ascending=False).head(20)
    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"]).dt.strftime("%d/%m/%Y %H:%M")
    df_show = df_hist[["timestamp", "temperature", "humidite",
                        "precipitation", "vent", "risk_predicted", "confidence"]].copy()
    df_show.columns = ["Timestamp", "Temp (°C)", "Humidity (%)",
                        "Rain (mm)", "Wind (m/s)", "IA Risk", "Confidence"]
    df_show["Confidence"] = df_show["Confidence"].apply(lambda x: f"{x:.0%}")
    
    st.dataframe(
        df_show, 
        use_container_width=True, 
        hide_index=True,
    )
else:
    st.markdown(glass_card("<div style='text-align:center; padding:1.5rem; color:#484f58;'>No historical logs found. Run automated tasks to begin data collection.</div>"), unsafe_allow_html=True)

