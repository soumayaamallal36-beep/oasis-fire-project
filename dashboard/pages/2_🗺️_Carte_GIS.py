"""
Page 2 — Carte GIS Interactive
Multi-layer Folium map with real raster overlays.
"""

import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import streamlit.components.v1 as components

from components.ui         import GLOBAL_CSS, section_header, kpi_card, glass_card
from components.weather    import get_weather
from components.prediction import get_current_prediction, RISK_COLORS
from components.maps       import build_risk_map

st.set_page_config(page_title="Carte GIS · OASIS Fire", page_icon="🗺️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🗺️ Carte GIS Interactive")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)

    st.markdown("**🗂️ Couches raster**")
    st.markdown("<div style='font-size:0.78rem;color:#8b949e;margin-bottom:8px;'>Sélectionnez les couches à afficher</div>",
                unsafe_allow_html=True)

    layer_options = {
        "dnbr":        "🔥 Sévérité dNBR (2025)",
        "ndvi_before": "🌿 NDVI avant incendie",
        "ndvi_after":  "🍂 NDVI après incendie",
        "severity":    "🏷️ Classes de sévérité",
        "slope":       "⛰️ Pente topographique",
        "aspect":      "🧭 Exposition (aspect)",
    }
    selected_layers = []
    for key, label in layer_options.items():
        default = key in ["dnbr", "ndvi_before"]
        if st.checkbox(label, value=default, key=f"layer_{key}"):
            selected_layers.append(key)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**📍 Location Data**")
    st.markdown("""
    <div style='font-size:0.8rem;color:#c9d1d9;background:rgba(22,27,34,0.5);
                border:1px solid #30363d;border-radius:10px;padding:1rem;'>
        <b>Site:</b> Agdez, Province de Zagora<br>
        <b>Coords:</b> 30.697°N · 6.448°O<br>
        <b>Impact:</b> ~388 ha brûlés (2025)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Map View", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Interactive GIS Intelligence",
    "Multi-layer spatial analysis · Sentinel-2 Imagery · DEM Topography · AI Risk Overlays",
    "🗺️",
), unsafe_allow_html=True)

# ── Load current prediction ───────────────────────────────────────
weather = get_weather()
label, conf, probas = get_current_prediction(weather)

# ── Row 1: KPI cards ──────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
risk_color = RISK_COLORS.get(label, "#8b949e")
with c1:
    st.markdown(kpi_card("Current Risk", label.upper(),
                         f"Confidence {conf:.0%}", "🔥", risk_color),
                unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Burned Area", "388 ha",
                         "2025 Event Record", "🔥", "#f0883e"),
                unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("Max dNBR", "0.59",
                         "High severity detected", "📊", "#d29922"),
                unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Active Layers", f"{len(selected_layers)} / 6",
                         "Multi-spectral analysis", "🗂️", "#58a6ff"),
                unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Map Container ───────────────────────────────────────────────────
with st.spinner("Processing spatial telemetry & raster overlays…"):
    map_html = build_risk_map(
        risk_label=label,
        confidence=conf,
        active_layers=selected_layers if selected_layers else ["dnbr"],
    )

st.markdown(f"""
    <div style='background: rgba(22, 27, 34, 0.4); backdrop-filter: blur(10px);
                border: 1px solid rgba(240, 246, 252, 0.1); border-radius: 20px;
                padding: 10px; box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
                margin-bottom: 2rem; overflow: hidden;'>
        <iframe srcdoc="{map_html.replace('"', '&quot;')}" width="100%" height="650" style="border:none; border-radius:15px;"></iframe>
    </div>
""", unsafe_allow_html=True)

# ── Legend & Layer Info ────────────────────────────────────────────
col_leg, col_info = st.columns([1.5, 2.5])

with col_leg:
    legend_html = ""
    for lvl, color in RISK_COLORS.items():
        legend_html += f"""
        <div style='display:flex; align-items:center; gap:12px; padding:10px 0;
                    border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
            <div style='width:12px; height:12px; border-radius:50%;
                        background:{color}; box-shadow: 0 0 8px {color}; flex-shrink:0;'></div>
            <span style='color:#c9d1d9; font-size:0.85rem; font-weight:600;'>{lvl.upper()}</span>
        </div>
        """
    st.markdown(glass_card(legend_html, title="Risk Level Color Key", icon="🎨"), unsafe_allow_html=True)

with col_info:
    layer_desc = {
        "🔥 dNBR Severity": "Normalized Burn Ratio difference. High values indicate severe vegetation loss.",
        "🌿 Pre-Fire NDVI": "Vegetation density before the event. Green = dense foliage, Red = bare soil.",
        "🍂 Post-Fire NDVI": "Vegetation index after the event. Used to calculate recovery potential.",
        "🏷️ Class Severity": "Standardized classification: Unburned → Low → Moderate → High → Critical.",
        "⛰️ Slope Analysis": "Topographical slope in degrees. Steep terrain accelerates fire propagation.",
        "🧭 Aspect (Exposure)": "Terrain orientation. South-facing slopes have higher fuel aridity.",
    }
    desc_html = ""
    for name, desc in layer_desc.items():
        desc_html += f"""
        <div style='padding:8px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
            <div style='color:#c9d1d9; font-size:0.82rem; font-weight:600;'>{name}</div>
            <div style='color:#8b949e; font-size:0.78rem; margin-top:2px;'>{desc}</div>
        </div>
        """
    st.markdown(glass_card(desc_html, title="Layer Intelligence Guide", icon="📚"), unsafe_allow_html=True)
