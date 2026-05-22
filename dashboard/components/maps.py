"""
components/maps.py
───────────────────
Multi-layer Folium map builder using real raster assets.
"""

import io
import warnings
from pathlib import Path

import folium
import numpy as np
from folium import plugins
import streamlit as st

warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Agdez centre
LAT, LON = 30.697, -6.448

# Raster paths
RASTERS = {
    "dnbr":       PROJECT_ROOT / "data" / "processed" / "indices" / "dnbr.tif",
    "ndvi_before":PROJECT_ROOT / "data" / "processed" / "indices" / "ndvi_before.tif",
    "ndvi_after": PROJECT_ROOT / "data" / "processed" / "indices" / "ndvi_after.tif",
    "severity":   PROJECT_ROOT / "data" / "processed" / "indices" / "severity_classified.tif",
    "slope":      PROJECT_ROOT / "data" / "raw"       / "dem"     / "pente_2025.tif",
    "aspect":     PROJECT_ROOT / "data" / "raw"       / "dem"     / "exposition_2025.tif",
}

RISK_COLORS = {
    "Faible":     "#3fb950",
    "Moyen":      "#d29922",
    "Élevé":      "#f0883e",
    "Très élevé": "#f85149",
}


def _raster_to_png_overlay(raster_path: Path, colormap_name: str = "RdYlGn_r",
                             vmin=None, vmax=None, alpha: float = 0.6):
    """
    Read a GeoTIFF and convert to a base64 PNG + bounds for Folium ImageOverlay.
    Returns (png_bytes_io, [[south, west], [north, east]]) or (None, None).
    """
    try:
        import rasterio
        from rasterio.plot import reshape_as_image
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        from matplotlib.colors import Normalize

        with rasterio.open(raster_path) as src:
            data = src.read(1).astype(float)
            bounds = src.bounds
            nodata = src.nodata

        if nodata is not None:
            data[data == nodata] = np.nan

        # Downsample for performance (max 512px)
        max_dim = 512
        if max(data.shape) > max_dim:
            factor = max(data.shape) // max_dim + 1
            data = data[::factor, ::factor]

        cmap = plt.get_cmap(colormap_name)
        v_min = vmin if vmin is not None else np.nanpercentile(data, 2)
        v_max = vmax if vmax is not None else np.nanpercentile(data, 98)
        norm  = Normalize(vmin=v_min, vmax=v_max)
        rgba  = cmap(norm(np.ma.masked_invalid(data)))
        rgba[:, :, 3] = np.where(np.isnan(data), 0, alpha)

        buf = io.BytesIO()
        plt.imsave(buf, rgba, format="png")
        buf.seek(0)

        sw = [bounds.bottom, bounds.left]
        ne = [bounds.top,    bounds.right]
        return buf, [sw, ne]
    except Exception:
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def build_risk_map(risk_label: str = "Élevé", confidence: float = 0.75,
                   active_layers: list = None) -> str:
    """
    Build a multi-layer Folium map and return HTML string.
    active_layers: list of layer keys to add (default: all available)
    """
    if active_layers is None:
        active_layers = ["dnbr", "ndvi_before", "slope"]

    m = folium.Map(
        location=[LAT, LON],
        zoom_start=13,
        tiles=None,
        prefer_canvas=True,
    )

    # ── Base tile layers ─────────────────────────────────────────
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB",
        name="🌑 Dark (défaut)",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI",
        name="🛰️ Satellite ESRI",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="🗺️ OpenStreetMap",
        control=True,
    ).add_to(m)

    # ── Raster overlay layers ────────────────────────────────────
    layer_config = {
        "dnbr":        ("🔥 Sévérité dNBR",  "RdYlGn_r",  -0.3,  0.8,  0.65),
        "ndvi_before": ("🌿 NDVI avant",      "RdYlGn",    -0.1,  0.5,  0.60),
        "ndvi_after":  ("🍂 NDVI après",      "RdYlGn",    -0.1,  0.5,  0.60),
        "severity":    ("🏷️ Classes sévérité","RdYlGn_r",  0,     4,    0.65),
        "slope":       ("⛰️ Pente (%)",       "YlOrBr",    0,     30,   0.55),
        "aspect":      ("🧭 Exposition (°)",  "hsv",       0,     360,  0.50),
    }

    for key in active_layers:
        if key not in RASTERS or not RASTERS[key].exists():
            continue
        cfg = layer_config.get(key)
        if not cfg:
            continue
        name, cmap, vmin, vmax, alpha = cfg
        buf, bounds = _raster_to_png_overlay(RASTERS[key], cmap, vmin, vmax, alpha)
        if buf and bounds:
            import base64
            img_b64 = base64.b64encode(buf.read()).decode()
            folium.raster_layers.ImageOverlay(
                image=f"data:image/png;base64,{img_b64}",
                bounds=bounds,
                opacity=alpha,
                name=name,
                show=(key == "dnbr"),
            ).add_to(m)

    # ── Risk zone circle ─────────────────────────────────────────
    risk_color = RISK_COLORS.get(risk_label, "#8b949e")
    folium.CircleMarker(
        location=[LAT, LON],
        radius=18,
        popup=folium.Popup(
            f"""<div style='font-family:Inter,sans-serif;min-width:180px'>
            <b style='color:{risk_color}'>● Agdez — Risque {risk_label}</b><br>
            <small>Confiance: {confidence:.0%}</small><br>
            <small>Lat: {LAT} | Lon: {LON}</small><br>
            <small>Alt: 1169 m | Pente: 5.73°</small>
            </div>""",
            max_width=220,
        ),
        tooltip=f"Agdez — Risque {risk_label} ({confidence:.0%})",
        color=risk_color,
        fill=True,
        fill_color=risk_color,
        fill_opacity=0.35,
        weight=2.5,
    ).add_to(m)

    # Pulse animation marker
    folium.CircleMarker(
        location=[LAT, LON],
        radius=30,
        color=risk_color,
        fill=False,
        weight=1.5,
        opacity=0.5,
    ).add_to(m)

    # ── Fire perimeter (approximate 2025 burn zone) ──────────────
    burn_coords = [
        [30.71, -6.47], [30.72, -6.44], [30.70, -6.42],
        [30.68, -6.43], [30.67, -6.46], [30.69, -6.48], [30.71, -6.47],
    ]
    folium.Polygon(
        locations=burn_coords,
        color="#f85149",
        fill=True,
        fill_color="#f85149",
        fill_opacity=0.12,
        weight=2,
        dash_array="6 4",
        tooltip="Zone brûlée approximative — 2025 (388 ha)",
        popup=folium.Popup(
            """<div style='font-family:Inter,sans-serif'>
            <b style='color:#f85149'>🔥 Zone brûlée 2025</b><br>
            Surface: ~388 ha<br>dNBR max: 0.59<br>
            Sévérité: Élevée à Très élevée
            </div>""",
            max_width=180,
        ),
    ).add_to(m)

    # ── Layer control & plugins ──────────────────────────────────
    folium.LayerControl(collapsed=False, position="topright").add_to(m)
    plugins.Fullscreen(position="topleft").add_to(m)
    plugins.MiniMap(position="bottomleft", toggle_display=True).add_to(m)
    plugins.MousePosition(position="bottomright",
                          numDigits=4, prefix="📍").add_to(m)

    # Scale
    folium.plugins.MeasureControl(position="bottomleft",
                                   primary_length_unit="kilometers").add_to(m)

    return m._repr_html_()
