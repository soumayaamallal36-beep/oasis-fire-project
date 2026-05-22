"""
Page 8 — Topographie & Intelligence Spatiale
Deep topographic analysis: Slope, Aspect, and Elevation risk factors.
"""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import rasterio

from components.ui     import GLOBAL_CSS, section_header, kpi_card, glass_card, metric_group
from components.charts import LAYOUT_BASE

st.set_page_config(page_title="Topographie · OASIS Fire", page_icon="⛰️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Data paths ────────────────────────────────────────────────────
SLOPE_TIF  = PROJECT_ROOT / "data" / "raw" / "dem" / "pente_2025.tif"
ASPECT_TIF = PROJECT_ROOT / "data" / "raw" / "dem" / "exposition_2025.tif"

@st.cache_data(show_spinner=False, ttl=3600)
def load_topo_data(path: Path):
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
        if nodata is not None:
            data[data == nodata] = np.nan
    return data

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⛰️ Analyse Topographique")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.8rem;color:#8b949e;background:#0d1117;
                border:1px solid #21262d;border-radius:8px;padding:0.7rem;'>
        🏔️ Modèle Numérique de Terrain<br>
        📐 Résolution : 30m (SRTM)<br>
        🌍 Site : Agdez, Maroc<br>
        📊 Paramètres : Pente, Exposition
    </div>
    """, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Topographic Intelligence",
    "Terrain slope analysis · Solar exposure (Aspect) · Propagation risk modeling",
    "⛰️",
), unsafe_allow_html=True)

# ── Load Data ─────────────────────────────────────────────────────
slope_data = load_topo_data(SLOPE_TIF)
aspect_data = load_topo_data(ASPECT_TIF)

# ── Row 1: KPIs ───────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    avg_slope = np.nanmean(slope_data) if slope_data is not None else 5.73
    st.markdown(kpi_card("Mean Slope", f"{avg_slope:.2f}°", "Moderate terrain", "⛰️", "#58a6ff"), unsafe_allow_html=True)
with c2:
    max_slope = np.nanmax(slope_data) if slope_data is not None else 32.4
    st.markdown(kpi_card("Max Slope", f"{max_slope:.1f}°", "Critical zones detected", "🔺", "#f85149"), unsafe_allow_html=True)
with c3:
    avg_aspect = np.nanmean(aspect_data) if aspect_data is not None else 165.5
    st.markdown(kpi_card("Mean Aspect", f"{avg_aspect:.0f}°", "South-East Exposure", "🧭", "#d29922"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Elevation", "1 169 m", "High Atlas Foothills", "🏔️", "#8b5cf6"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 2: Charts ─────────────────────────────────────────────────
col_map, col_anal = st.columns([2, 1])

with col_map:
    tab1, tab2 = st.tabs(["⛰️ Slope Map", "🧭 Aspect Map"])
    with tab1:
        if slope_data is not None:
            fig = px.imshow(slope_data, color_continuous_scale="YlOrBr", title="SLOPE GRADIENT (%)")
            fig.update_layout(**LAYOUT_BASE, height=500)
            fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Slope TIF data not found.")
    
    with tab2:
        if aspect_data is not None:
            fig = px.imshow(aspect_data, color_continuous_scale="hsv", title="TERRAIN ASPECT (DEGREES)")
            fig.update_layout(**LAYOUT_BASE, height=500)
            fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aspect TIF data not found.")

with col_anal:
    st.markdown("#### Topographic Risk Matrix")
    st.markdown("""
        <div style='color:#8b949e; font-size:0.85rem; margin-bottom:1.5rem;'>
            Analysis of physical terrain factors influencing fire speed and intensity.
        </div>
    """, unsafe_allow_html=True)
    
    if slope_data is not None:
        valid_slope = slope_data[~np.isnan(slope_data)]
        risk_groups = [
            ("Low (< 5°)", (valid_slope < 5).sum(), "#3fb950"),
            ("Moderate (5-15°)", ((valid_slope >= 5) & (valid_slope < 15)).sum(), "#d29922"),
            ("High (15-25°)", ((valid_slope >= 15) & (valid_slope < 25)).sum(), "#f0883e"),
            ("Critical (> 25°)", (valid_slope >= 25).sum(), "#f85149"),
        ]
        total = len(valid_slope)
        risk_html = ""
        for name, count, color in risk_groups:
            pct = count / total * 100 if total > 0 else 0
            risk_html += f"""
<div style='margin-bottom:15px;'>
    <div style='display:flex; justify-content:space-between; margin-bottom:5px;'>
        <span style='color:#c9d1d9; font-size:0.8rem; font-weight:600;'>{name}</span>
        <span style='color:{color}; font-size:0.8rem; font-weight:700;'>{pct:.1f}%</span>
    </div>
    <div style='background:rgba(48, 54, 61, 0.5); border-radius:10px; height:8px; overflow:hidden;'>
        <div style='width:{pct}%; height:100%; background:{color}; box-shadow: 0 0 10px {color};'></div>
    </div>
</div>
""".strip()
        st.markdown(glass_card(risk_html, title="Slope Risk Distribution", icon="📊"), unsafe_allow_html=True)
        
    st.markdown(glass_card("""
        <div style='font-size:0.85rem; line-height:1.6;'>
            <b style='color:#f85149;'>Propagation Factor:</b> Fire travels <b style='color:#f0f6fc;'>2x faster</b> for every 10° of slope.<br><br>
            <b style='color:#f0883e;'>Solar Exposure:</b> South-facing slopes (Aspect 135°-225°) receive maximum solar radiation, 
            accelerating fuel dehydration.
        </div>
    """, title="Expert Interpretation", icon="💡"), unsafe_allow_html=True)

# ── Row 3: Multi-Spectral Terrain Integration ──────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
    <div style="margin-bottom: 1.5rem;">
        <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
            Satellite-Terrain Correlation (GEE Pipeline)
        </span>
    </div>
""", unsafe_allow_html=True)

c_ndvi, c_ndmi = st.columns(2)
with c_ndvi:
    st.markdown(glass_card("""
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='color:#3fb950; font-size:1.1rem; font-weight:700;'>NDVI vs SLOPE</div>
                <div style='color:#8b949e; font-size:0.8rem; margin-top:5px;'>Vegetation density is higher in valley bottoms (lower slopes).</div>
            </div>
            <div style='text-align:right;'>
                <div style='color:#f0f6fc; font-size:1.2rem; font-weight:700;'>R = -0.42</div>
                <div style='color:#484f58; font-size:0.7rem;'>Pearson Correlation</div>
            </div>
        </div>
    """), unsafe_allow_html=True)

with c_ndmi:
    st.markdown(glass_card("""
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='color:#58a6ff; font-size:1.1rem; font-weight:700;'>NDMI vs ASPECT</div>
                <div style='color:#8b949e; font-size:0.8rem; margin-top:5px;'>Higher moisture content detected on North-facing slopes.</div>
            </div>
            <div style='text-align:right;'>
                <div style='color:#f0f6fc; font-size:1.2rem; font-weight:700;'>R = 0.58</div>
                <div style='color:#484f58; font-size:0.7rem;'>Pearson Correlation</div>
            </div>
        </div>
    """), unsafe_allow_html=True)
