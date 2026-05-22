"""
Page 4 — Climatologie
Historical climate trends + future projections 2026-2035.
"""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.ui     import GLOBAL_CSS, section_header, kpi_card, glass_card
from components.charts import temperature_trend, climate_multivar, climate_projections

st.set_page_config(page_title="Climatologie · OASIS Fire", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Data paths ────────────────────────────────────────────────────
CLIMAT_DIR    = PROJECT_ROOT / "dashboard" / "data_" / "climate"
PROJ_CSV      = PROJECT_ROOT / "models" / "metadata" / "projections_climatiques.csv"
ANNUAL_CSV    = CLIMAT_DIR / "climat_statistiques_annuelles.csv"
SUMMER_CSV    = CLIMAT_DIR / "climat_conditions_ete_2025.csv"
LAYOUT_BASE   = dict(
    paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
    font=dict(family="Inter", color="#8b949e", size=12),
    margin=dict(l=40, r=20, t=40, b=40),
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_annual():
    if ANNUAL_CSV.exists():
        return pd.read_csv(ANNUAL_CSV)
    # Fallback inline data
    return pd.DataFrame({
        "Année": list(range(2017, 2026)),
        "Température_°C": [20.43,19.16,20.34,20.46,20.50,20.76,21.07,21.23,20.25],
        "Humidité_%":     [28.56,35.43,28.96,32.07,30.87,31.23,29.22,29.64,31.98],
        "Précipitations_mm":[45.43,103.64,111.66,108.69,75.10,82.65,93.92,70.68,109.69],
        "Vent_m_s":       [3.88,4.17,3.85,3.90,4.06,3.92,3.78,3.88,3.86],
    })


@st.cache_data(ttl=3600, show_spinner=False)
def load_summer():
    if SUMMER_CSV.exists():
        return pd.read_csv(SUMMER_CSV)
    return pd.DataFrame({
        "Mois":              ["Juin",   "Juillet", "Août"],
        "Température_°C":   [29.30,    32.69,     31.40],
        "Humidité_%":       [20.18,    16.42,     19.86],
        "Précipitations_mm":[2.85,     26.43,     0.18],
        "Vent_m_s":         [4.50,     4.01,      3.81],
    })


@st.cache_data(ttl=3600, show_spinner=False)
def load_projections():
    if PROJ_CSV.exists():
        return pd.read_csv(PROJ_CSV)
    return None


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📈 Climatologie")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.8rem;color:#8b949e;background:#0d1117;
                border:1px solid #21262d;border-radius:8px;padding:0.7rem;'>
        📡 Source : NASA POWER<br>
        📅 Période : 2017-2025<br>
        🔮 Projections : 2026-2035<br>
        📍 Zone : Agdez (30.69°N)
    </div>
    """, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Climate Analytics & Projections",
    "Historical multi-decadal trends · Seasonal anomalies · AI-driven 2035 projections",
    "📈",
), unsafe_allow_html=True)

df_ann  = load_annual()
df_sum  = load_summer()
df_proj = load_projections()

# ── Row 1: KPI cards ──────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    tmax = df_ann["Température_°C"].max()
    yr   = int(df_ann.loc[df_ann["Température_°C"].idxmax(), "Année"])
    st.markdown(kpi_card("Max Temp Recorded", f"{tmax:.2f}°C",
                         f"Peak Year: {yr}", "🔺", "#f85149"), unsafe_allow_html=True)
with c2:
    tmean = df_ann["Température_°C"].mean()
    st.markdown(kpi_card("Mean Temperature", f"{tmean:.2f}°C",
                         "Historical Avg (2017-25)", "🌡️", "#f0883e"), unsafe_allow_html=True)
with c3:
    ptot = df_ann["Précipitations_mm"].sum()
    st.markdown(kpi_card("Total Rainfall", f"{ptot:.0f} mm",
                         "Cumulative 2017-2025", "🌧️", "#58a6ff"), unsafe_allow_html=True)
with c4:
    if df_proj is not None and len(df_proj) > 0:
        t2035 = df_proj[df_proj["annee"] == 2035]["temperature"].values
        val   = f"{t2035[0]:.1f}°C" if len(t2035) > 0 else "N/A"
    else:
        val = "N/A"
    st.markdown(kpi_card("2035 Target Projection", val,
                         "July Linear Regression", "🔮", "#8b5cf6"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🌡️ Temperature Trends",
    "📊 Multi-Variable Analysis",
    "🔥 2025 Season Deep-Dive",
    "🔮 Future Projections (2035)",
])

with tab1:
    fig = temperature_trend(df_ann)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Linear regression annotation
    z = np.polyfit(df_ann["Année"], df_ann["Température_°C"], 1)
    slope = z[0]
    dir_label = "UPWARD" if slope > 0 else "DOWNWARD"
    color = "#f85149" if slope > 0 else "#3fb950"
    
    regression_html = f"""
    <div style='display:grid; grid-template-columns: repeat(4, 1fr); gap:20px;'>
        <div>
            <div style='font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;'>Slope Coefficient</div>
            <div style='font-size:1.2rem; font-weight:800; color:{color}; margin-top:5px;'>
                {dir_label} {abs(slope):.4f}°C/y
            </div>
        </div>
        <div>
            <div style='font-size:0.75rem; color:#8b949e;'>2026 Estimate</div>
            <div style='color:#f0f6fc; font-size:1.1rem; font-weight:700; margin-top:5px;'>{np.polyval(z, 2026):.2f}°C</div>
        </div>
        <div>
            <div style='font-size:0.75rem; color:#8b949e;'>2030 Estimate</div>
            <div style='color:#f0f6fc; font-size:1.1rem; font-weight:700; margin-top:5px;'>{np.polyval(z, 2030):.2f}°C</div>
        </div>
        <div>
            <div style='font-size:0.75rem; color:#8b949e;'>2035 Horizon</div>
            <div style='color:#f0883e; font-size:1.1rem; font-weight:800; margin-top:5px;'>{np.polyval(z, 2035):.2f}°C</div>
        </div>
    </div>
    """
    st.markdown(glass_card(regression_html, title="Linear Regression Intelligence", icon="📐"), unsafe_allow_html=True)

with tab2:
    fig = climate_multivar(df_ann)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
            <span style='font-size:1.2rem;'>📋</span>
            <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                Annual Climate Data Matrix
            </span>
        </div>
    """, unsafe_allow_html=True)
    st.dataframe(df_ann, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("#### Summer Season Intelligence — 2025 Condition Record")
    c_sum, c_comp = st.columns([1.5, 2.5])

    with c_sum:
        summer_html = ""
        for _, row in df_sum.iterrows():
            mois = row["Mois"]
            t, h = row["Température_°C"], row["Humidité_%"]
            accent = "#f85149" if mois == "Juillet" else "#f0883e"
            summer_html += f"""
<div style='background:rgba(22,27,34,0.4); border:1px solid rgba(240, 246, 252, 0.05);
            border-left:4px solid {accent}; border-radius:12px;
            padding:1rem; margin-bottom:12px; backdrop-filter:blur(10px);'>
    <div style='font-size:0.95rem; font-weight:700; color:#f0f6fc; margin-bottom:10px;'>{mois.upper()} 2025</div>
    <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px; font-family:JetBrains Mono; font-size:0.85rem;'>
        <div><span style='color:#8b949e;'>TEMP:</span> <b style='color:{accent};'>{t:.1f}°C</b></div>
        <div><span style='color:#8b949e;'>HUMI:</span> <b style='color:#58a6ff;'>{h:.0f}%</b></div>
        <div style='color:#484f58;'><span style='color:#8b949e;'>RAIN:</span> {row["Précipitations_mm"]:.1f}mm</div>
        <div style='color:#484f58;'><span style='color:#8b949e;'>WIND:</span> {row["Vent_m_s"]:.1f}m/s</div>
    </div>
</div>
""".strip()
        st.markdown(summer_html, unsafe_allow_html=True)

    with c_comp:
        months = df_sum["Mois"].tolist()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=months, y=df_sum["Température_°C"],
            marker_color=["#f0883e", "#f85149", "#f0883e"], name="Temperature (°C)",
            text=[f"{v:.1f}°C" for v in df_sum["Température_°C"]], textposition="outside",
        ))
        fig.add_trace(go.Scatter(
            x=months, y=df_sum["Humidité_%"], mode="lines+markers", name="Humidity (%)",
            line=dict(color="#58a6ff", width=3, dash='dot'), yaxis="y2",
        ))
        fig.update_layout(**LAYOUT_BASE, height=360, 
                          title=dict(text="2025 Season Index: Temp vs Humidity", font=dict(size=14, family="Outfit")),
                          yaxis2=dict(overlaying="y", side="right", showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        t_avg = df_ann["Température_°C"].mean()
        t_peak = df_sum.loc[df_sum["Mois"] == "Juillet", "Température_°C"].values
        if len(t_peak) > 0:
            anomaly = t_peak[0] - t_avg
            st.markdown(glass_card(f"""
                <div style='display:flex; align-items:center; gap:15px;'>
                    <div style='font-size:1.5rem;'>🔥</div>
                    <div>
                        <div style='font-size:0.75rem; color:#8b949e;'>July Seasonal Anomaly</div>
                        <div style='font-size:1.1rem; font-weight:700; color:#f85149;'>+{anomaly:.2f}°C above mean</div>
                    </div>
                </div>
            """), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        recap_data = [
            {"Facteur": "Température max (Juillet)", "Valeur": "32.69 °C", "Impact": "🔴 Très haut"},
            {"Facteur": "Humidité min (Juillet)", "Valeur": "16.42 %", "Impact": "🔴 Favorise le feu"},
            {"Facteur": "Vent max (Juin)", "Valeur": "4.50 m/s", "Impact": "🟠 Propagation"},
            {"Facteur": "Surface brûlée 2025", "Valeur": "388.51 ha", "Impact": "🔥 Important"},
        ]
        recap_html = ""
        for item in recap_data:
            recap_html += f"""
<div style='display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
    <span style='color:#8b949e; font-size:0.85rem;'>{item['Facteur']}</span>
    <span style='color:#f0f6fc; font-size:0.85rem; font-weight:700;'>{item['Valeur']}</span>
    <span style='font-size:0.8rem; font-weight:800;'>{item['Impact']}</span>
</div>
""".strip()
        st.markdown(glass_card(recap_html, title="Climate-Fire Impact Synthesis", icon="📋"), unsafe_allow_html=True)

with tab4:
    if df_proj is not None:
        fig = climate_projections(df_proj)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
                <span style='font-size:1.2rem;'>🔮</span>
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                    AI Predictive Horizon (2026-2035)
                </span>
            </div>
        """, unsafe_allow_html=True)
        
        df_disp = df_proj[["annee","temperature","humidite","precipitation","vent","risque_predit","confiance"]].copy()
        df_disp.columns = ["Year","Temp (°C)","Humidity (%)","Rain (mm)","Wind (m/s)","Risk Model","Confidence"]
        df_disp["Confidence"] = df_disp["Confidence"].apply(lambda x: f"{x:.0%}")
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

        critiques = df_proj[df_proj["risque_predit"].isin(["Élevé","Très élevé"])]
        if len(critiques) > 0:
            years = ", ".join(critiques["annee"].astype(int).astype(str).tolist())
            st.markdown(f"""
                <div style='background:rgba(248,81,73,0.05); border:1px solid rgba(248,81,73,0.3);
                            border-left:5px solid #f85149; border-radius:12px;
                            padding:1.2rem; margin-top:1.5rem; display:flex; align-items:center; gap:20px;'>
                    <div style='font-size:2rem;'>⚠️</div>
                    <div>
                        <div style='color:#f85149; font-size:0.9rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;'>Critical Risk Years Detected</div>
                        <div style='color:#c9d1d9; font-size:1rem; font-weight:600; margin-top:4px;'>{years}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Predictive models not yet calibrated. Run the pipeline to generate 10-year projections.")

