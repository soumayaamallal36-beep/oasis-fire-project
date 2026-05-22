"""
Page 3 — Analyse Satellite
Sentinel-2 NDVI / dNBR / NBR / NDMI visualization using real raster files.
"""

import sys, warnings
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

warnings.filterwarnings("ignore")

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from components.ui import GLOBAL_CSS, section_header, kpi_card, glass_card

st.set_page_config(page_title="Satellite · OASIS Fire", page_icon="🛰️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Data paths ────────────────────────────────────────────────────
IDX_DIR   = PROJECT_ROOT / "data" / "processed" / "indices"
SAT_XLSX  = PROJECT_ROOT / "dashboard" / "data_" / "satellite _image"
IMG_DIR   = PROJECT_ROOT / "dashboard" / "image"

RASTERS = {
    "ndvi_before": IDX_DIR / "ndvi_before.tif",
    "ndvi_after":  IDX_DIR / "ndvi_after.tif",
    "dnbr":        IDX_DIR / "dnbr.tif",
    "nbr_before":  IDX_DIR / "nbr_before.tif",
    "nbr_after":   IDX_DIR / "nbr_after.tif",
    "ndmi_before": IDX_DIR / "ndmi_before.tif",
    "ndmi_after":  IDX_DIR / "ndmi_after.tif",
    "severity":    IDX_DIR / "severity_classified.tif",
}


@st.cache_data(show_spinner=False, ttl=3600)
def load_raster_array(path: Path, downsample: int = 4):
    """Load a raster TIF and return (data_array, nodata_value)."""
    try:
        import rasterio
        with rasterio.open(path) as src:
            data   = src.read(1).astype(float)
            nodata = src.nodata
        if nodata is not None:
            data[data == nodata] = np.nan
        data = data[::downsample, ::downsample]
        return data
    except Exception as e:
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def raster_stats(path: Path):
    """Return basic statistics dict from a raster."""
    data = load_raster_array(path, downsample=2)
    if data is None:
        return {}
    valid = data[~np.isnan(data)]
    return {
        "min":    float(np.nanmin(valid)),
        "max":    float(np.nanmax(valid)),
        "mean":   float(np.nanmean(valid)),
        "std":    float(np.nanstd(valid)),
        "pixels": len(valid),
    }


def plot_raster(data, title: str, colorscale: str = "RdYlGn",
                zmin=None, zmax=None) -> go.Figure:
    if data is None:
        return go.Figure()
    fig = px.imshow(
        data, color_continuous_scale=colorscale,
        zmin=zmin, zmax=zmax,
        aspect="equal", title=title,
    )
    fig.update_layout(
        paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
        font=dict(family="Inter", color="#8b949e", size=11),
        height=320, margin=dict(l=0, r=0, t=35, b=0),
        title_font=dict(size=13, color="#c9d1d9"),
        coloraxis_colorbar=dict(
            tickfont=dict(color="#8b949e"),
            title=dict(font=dict(color="#8b949e")),
        ),
    )
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    return fig


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛰️ Analyse Satellite")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.8rem;color:#8b949e;background:#0d1117;
                border:1px solid #21262d;border-radius:8px;padding:0.7rem;'>
        📡 Sentinel-2 L2A<br>
        📅 Données : Juillet 2025<br>
        📐 Résolution : 10m<br>
        🌍 Zone : Agdez, Maroc<br>
        📊 Indices : NDVI, NBR, dNBR, NDMI
    </div>
    """, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Satellite Multi-Spectral Intelligence",
    "Sentinel-2 Index Analysis · NDVI · NBR · dNBR · NDMI · Severity Classification",
    "🛰️",
), unsafe_allow_html=True)

# ── Stats KPIs ────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card("Burned Surface", "388.51 ha",
                         "Total impact 2025", "🔥", "#f85149"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Max dNBR", "0.5928",
                         "High severity peak", "📊", "#f0883e"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("Pre-Fire NDVI", "0.144",
                         "Mean vegetation density", "🌿", "#3fb950"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Post-Fire NDVI", "~0.05",
                         "Critical loss area", "🍂", "#d29922"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🌿 Vegetation Index (NDVI)",
    "🔥 Burn Severity (dNBR)",
    "💧 Moisture Index (NDMI)",
    "🏷️ Spatial Classification",
])

with tab1:
    st.markdown("#### NDVI — Normalized Difference Vegetation Index")
    st.markdown("""
        <div style='color:#8b949e; font-size:0.85rem; margin-bottom:1.5rem;'>
            Measures chlorophyll concentration and vegetation vigor. 
            <b style='color:#3fb950;'>Positive</b> = Healthy vegetation · <b style='color:#f85149;'>Low/Negative</b> = Bare soil or burned area.
        </div>
    """, unsafe_allow_html=True)
    
    c_bef, c_aft = st.columns(2)
    with c_bef:
        data_bef = load_raster_array(RASTERS["ndvi_before"])
        fig = plot_raster(data_bef, "NDVI: PRE-FIRE (JUNE 2025)", "RdYlGn", zmin=-0.1, zmax=0.5)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if data_bef is not None:
            st.markdown(f"""
                <div style='text-align:center; font-family:JetBrains Mono; font-size:0.8rem; color:#8b949e; margin-top:10px;'>
                    MEAN: <span style='color:#3fb950;'>{np.nanmean(data_bef):.3f}</span> | PEAK: {np.nanmax(data_bef):.3f}
                </div>
            """, unsafe_allow_html=True)
            
    with c_aft:
        data_aft = load_raster_array(RASTERS["ndvi_after"])
        fig = plot_raster(data_aft, "NDVI: POST-FIRE (AUGUST 2025)", "RdYlGn", zmin=-0.1, zmax=0.5)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if data_aft is not None:
            st.markdown(f"""
                <div style='text-align:center; font-family:JetBrains Mono; font-size:0.8rem; color:#8b949e; margin-top:10px;'>
                    MEAN: <span style='color:#f0883e;'>{np.nanmean(data_aft):.3f}</span> | PEAK: {np.nanmax(data_aft):.3f}
                </div>
            """, unsafe_allow_html=True)

with tab2:
    st.markdown("#### dNBR — Difference Normalized Burn Ratio")
    st.markdown("""
        <div style='color:#8b949e; font-size:0.85rem; margin-bottom:1.5rem;'>
            Standardized index for fire severity. <b style='color:#f85149;'>Positive values</b> represent burned pixels.
        </div>
    """, unsafe_allow_html=True)
    
    data_dnbr = load_raster_array(RASTERS["dnbr"])
    c_map, c_stat = st.columns([2, 1])
    with c_map:
        fig = plot_raster(data_dnbr, "dNBR SPATIAL DISTRIBUTION (2025)", "RdYlGn_r", zmin=-0.2, zmax=0.6)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    
    with c_stat:
        if data_dnbr is not None:
            valid = data_dnbr[~np.isnan(data_dnbr)]
            classes = [
                ("UNBURNED (< 0.1)", (valid < 0.1).sum(), "#3fb950"),
                ("LOW (0.1–0.27)",   ((valid >= 0.1) & (valid < 0.27)).sum(), "#d29922"),
                ("MODERATE (0.27–0.44)", ((valid >= 0.27) & (valid < 0.44)).sum(), "#f0883e"),
                ("HIGH (0.44–0.66)",  ((valid >= 0.44) & (valid < 0.66)).sum(), "#f85149"),
                ("CRITICAL (> 0.66)", (valid >= 0.66).sum(), "#b91c1c"),
            ]
            total = len(valid)
            class_html = ""
            for name, count, color in classes:
                pct = count / total * 100 if total > 0 else 0
                class_html += f"""
                <div style='padding:8px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
                    <div style='display:flex; justify-content:space-between; margin-bottom:5px;'>
                        <span style='color:#c9d1d9; font-size:0.8rem; font-weight:600;'>{name}</span>
                        <span style='color:{color}; font-size:0.8rem; font-weight:700;'>{pct:.1f}%</span>
                    </div>
                    <div style='background:rgba(48, 54, 61, 0.5); border-radius:10px; height:6px; overflow:hidden;'>
                        <div style='width:{pct}%; height:100%; background:{color}; box-shadow: 0 0 5px {color};'></div>
                    </div>
                </div>
                """
            st.markdown(glass_card(class_html, title="Severity Distribution", icon="🏷️"), unsafe_allow_html=True)

with tab3:
    st.markdown("#### NDMI — Normalized Difference Moisture Index")
    st.markdown("""
        <div style='color:#8b949e; font-size:0.85rem; margin-bottom:1.5rem;'>
            Estimates fuel moisture and vegetation water content. <b style='color:#58a6ff;'>Blue</b> = Hydrated · <b style='color:#f0883e;'>Red</b> = Arid/Dehydrated.
        </div>
    """, unsafe_allow_html=True)
    c_bef2, c_aft2 = st.columns(2)
    with c_bef2:
        fig = plot_raster(load_raster_array(RASTERS["ndmi_before"]), "NDMI: PRE-FIRE", "Blues", zmin=-0.3, zmax=0.5)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with c_aft2:
        fig = plot_raster(load_raster_array(RASTERS["ndmi_after"]), "NDMI: POST-FIRE", "Blues", zmin=-0.3, zmax=0.5)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with tab4:
    st.markdown("#### Standard Severity Classification (USGS)")
    data_sev = load_raster_array(RASTERS["severity"], downsample=1)
    c_sv, c_cl = st.columns([2, 1])
    with c_sv:
        if data_sev is not None:
            fig = px.imshow(data_sev, color_continuous_scale=["#3fb950", "#86d958", "#d29922", "#f0883e", "#f85149"], 
                            zmin=0, zmax=4, aspect="equal", title="CLASSIFIED SEVERITY MAP")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#8b949e"), 
                              height=400, margin=dict(l=0, r=0, t=40, b=0), title_font=dict(size=14, family="Outfit", color="#f0f6fc"))
            fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with c_cl:
        sev_labels = [("🟢 UNBURNED", "#3fb950"), ("🟡 LOW", "#d29922"), ("🟠 MODERATE", "#f0883e"), 
                      ("🔴 HIGH", "#f85149"), ("🟣 CRITICAL", "#b91c1c")]
        sev_html = ""
        for i, (name, color) in enumerate(sev_labels):
            if data_sev is not None:
                valid = data_sev[~np.isnan(data_sev)]
                pct = (valid == i).sum() / len(valid) * 100 if len(valid) > 0 else 0
            else: pct = 0
            sev_html += f"""
            <div style='display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
                <span style='color:{color}; font-size:0.85rem; font-weight:700;'>{name}</span>
                <span style='color:#8b949e; font-size:0.85rem; font-family:JetBrains Mono;'>{pct:.1f}%</span>
            </div>
            """
        st.markdown(glass_card(sev_html, title="Classification Key", icon="🔑"), unsafe_allow_html=True)


    # Static image fallback
    dnbr_img = IMG_DIR / "carte_dnbr.png"
    sev_img  = IMG_DIR / "carte_severite.png"
    if dnbr_img.exists() or sev_img.exists():
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**📷 Cartes générées (haute résolution)**")
        img_cols = st.columns(2)
        for i, (img_path, cap) in enumerate([
            (dnbr_img, "Carte dNBR — Sévérité incendie"),
            (sev_img,  "Carte sévérité classifiée"),
        ]):
            if img_path.exists():
                with img_cols[i]:
                    st.image(str(img_path), caption=cap, use_container_width=True)
