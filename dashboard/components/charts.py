"""
components/charts.py
─────────────────────
Reusable Plotly chart builders with consistent dark scientific styling.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Shared theme ─────────────────────────────────────────────────
LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#8b949e", size=12),
    margin=dict(l=40, r=20, t=60, b=40),
    xaxis=dict(
        gridcolor="rgba(240, 246, 252, 0.05)", 
        zerolinecolor="rgba(240, 246, 252, 0.1)", 
        linecolor="rgba(240, 246, 252, 0.1)",
        tickfont=dict(color="#8b949e")
    ),
    yaxis=dict(
        gridcolor="rgba(240, 246, 252, 0.05)", 
        zerolinecolor="rgba(240, 246, 252, 0.1)", 
        linecolor="rgba(240, 246, 252, 0.1)",
        tickfont=dict(color="#8b949e")
    ),
    legend=dict(
        bgcolor="rgba(22, 27, 34, 0.8)", 
        bordercolor="rgba(240, 246, 252, 0.1)", 
        borderwidth=1,
        font=dict(size=11)
    ),
)
RISK_COLORS = {
    "Faible": "#3fb950", "Moyen": "#d29922",
    "Élevé": "#f0883e",  "Très élevé": "#f85149",
}

def _apply_base(fig, title=""):
    fig.update_layout(**LAYOUT_BASE)
    if title:
        fig.update_layout(title=dict(
            text=title,
            font=dict(family="Outfit, sans-serif", size=16, color="#f0f6fc"),
            x=0, y=0.95
        ))
    fig.update_xaxes(showgrid=True, gridwidth=1)
    fig.update_yaxes(showgrid=True, gridwidth=1)
    return fig


# ── Risk gauge ───────────────────────────────────────────────────
def risk_gauge(label: str, confidence: float) -> go.Figure:
    level_map = {"Faible": 1, "Moyen": 2, "Élevé": 3, "Très élevé": 4}
    val   = level_map.get(label, 1)
    color = RISK_COLORS.get(label, "#8b949e")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={"font": {"size": 36, "family": "Outfit", "color": color}},
        gauge={
            "axis": {"range": [0, 4], "tickvals": [0.5, 1.5, 2.5, 3.5],
                     "ticktext": ["FAIBLE", "MOYEN", "ÉLEVÉ", "CRITIQUE"],
                     "tickcolor": "#8b949e", "tickfont": {"size": 10, "weight": 600}},
            "bar": {"color": color, "thickness": 0.4},
            "bgcolor": "rgba(22, 27, 34, 0.5)",
            "bordercolor": "rgba(240, 246, 252, 0.1)",
            "steps": [
                {"range": [0, 1], "color": "rgba(63,185,80,0.1)"},
                {"range": [1, 2], "color": "rgba(210,153,34,0.1)"},
                {"range": [2, 3], "color": "rgba(240,136,62,0.1)"},
                {"range": [3, 4], "color": "rgba(248,81,73,0.15)"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        font_color="#c9d1d9",
        height=220, 
        margin=dict(l=30, r=30, t=10, b=10)
    )
    return fig


# ── Probability bar chart ────────────────────────────────────────
def probability_bars(probas):

    import plotly.graph_objects as go

    labels = list(probas.keys())
    values = list(probas.values())

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=labels,
            y=values,
            width=0.6,
            marker=dict(
                opacity=0.8,
                line=dict(width=0)
            )
        )
    )

    layout = LAYOUT_BASE.copy()

    layout["yaxis"] = {
        **LAYOUT_BASE.get("yaxis", {}),
        "range": [0, 115],
        "title": "CONFIDENCE (%)"
    }

    layout["xaxis"] = {
        **LAYOUT_BASE.get("xaxis", {}),
        "title": "RISK LEVEL"
    }

    layout["height"] = 280

    layout["title"] = dict(
        text="PROBABILITY DISTRIBUTION",
        font=dict(
            family="Outfit",
            size=14,
            color="#f0f6fc"
        ),
        x=0,
        y=0.95
    )

    fig.update_layout(**layout)

    return fig

# ── Temperature trend ────────────────────────────────────────────
def temperature_trend(df: pd.DataFrame) -> go.Figure:
    """df must have columns: Année, Température_°C"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Température_°C"],
        mode="lines+markers",
        line=dict(color="#58a6ff", width=4, shape="spline"),
        marker=dict(size=10, color="#58a6ff",
                    line=dict(color="#0d1117", width=2)),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.1)",
        name="TEMPÉRATURE MOYENNE",
    ))
    # Trend line
    z = np.polyfit(df["Année"], df["Température_°C"], 1)
    p = np.poly1d(z)
    fig.add_trace(go.Scatter(
        x=df["Année"], y=p(df["Année"]),
        mode="lines", line=dict(color="#f0883e", width=2, dash="dot"),
        name=f"TENDANCE (+{z[0]:.3f}°C/AN)",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text="TEMPERATURE EVOLUTION — AGDEZ (2017-2025)",
            font=dict(family="Outfit", size=16, color="#f0f6fc"),
            x=0, y=0.98
        ),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="TEMP (°C)"),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="YEAR",
                   tickmode="linear", dtick=1),
        height=350, 
        legend=dict(
            x=0.02, y=0.95, 
            bgcolor="rgba(22, 27, 34, 0.6)",
            orientation="h"
        ),
    )
    return fig


# ── Multi-variable climate chart ─────────────────────────────────
def climate_multivar(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=2, shared_xaxes=False,
                        subplot_titles=["TEMPÉRATURE (°C)", "HUMIDITÉ (%)",
                                        "PRÉCIPITATIONS (MM)", "VENT (M/S)"],
                        vertical_spacing=0.15, horizontal_spacing=0.1)
    pairs = [
        ("Année", "Température_°C", "#f0883e", 1, 1),
        ("Année", "Humidité_%",     "#58a6ff", 1, 2),
        ("Année", "Précipitations_mm", "#3fb950", 2, 1),
        ("Année", "Vent_m_s",       "#8b5cf6", 2, 2),
    ]
    for x_col, y_col, color, row, col in pairs:
        if y_col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col],
            mode="lines+markers",
            line=dict(color=color, width=3, shape="spline"),
            marker=dict(size=8, color=color, line=dict(color="#0d1117", width=1.5)),
            fill="tozeroy", fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}",
            showlegend=False,
        ), row=row, col=col)
        
    fig.update_layout(
        **LAYOUT_BASE,
        height=500,
        margin=dict(l=40, r=20, t=80, b=40),
        title=dict(
            text="ANNUAL CLIMATE TRENDS — AGDEZ",
            font=dict(family="Outfit", size=18, color="#f0f6fc"),
            x=0, y=0.98
        ),
    )
    
    # Update subplot titles font
    for i in fig['layout']['annotations']:
        i['font'] = dict(family="Outfit", size=13, color="#8b949e")
        
    for i in range(1, 5):
        row, col = (1 if i <= 2 else 2), (1 if i % 2 else 2)
        fig.update_xaxes(gridcolor="rgba(240, 246, 252, 0.05)", linecolor="rgba(240, 246, 252, 0.1)", row=row, col=col)
        fig.update_yaxes(gridcolor="rgba(240, 246, 252, 0.05)", linecolor="rgba(240, 246, 252, 0.1)", row=row, col=col)
    return fig


# ── Climate projections ──────────────────────────────────────────
def climate_projections(df: pd.DataFrame) -> go.Figure:
    """df: projections_climatiques.csv"""
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["PROJECTED TEMPERATURE (°C)",
                                        "PREDICTED RISK BY YEAR"],
                        horizontal_spacing=0.15)
    # Temperature projection
    fig.add_trace(go.Scatter(
        x=df["annee"], y=df["temperature"],
        mode="lines+markers",
        line=dict(color="#f85149", width=4, shape="spline"),
        marker=dict(size=10, color="#f85149", line=dict(color="#0d1117", width=2)),
        fill="tozeroy", fillcolor="rgba(248,81,73,0.1)",
        name="TEMPERATURE",
    ), row=1, col=1)

    # Risk level bar
    risk_num = {"Faible": 1, "Moyen": 2, "Élevé": 3, "Très élevé": 4}
    colors = [RISK_COLORS.get(r, "#8b949e") for r in df["risque_predit"]]
    fig.add_trace(go.Bar(
        x=df["annee"],
        y=[risk_num.get(r, 0) for r in df["risque_predit"]],
        marker_color=colors, marker_line_width=0,
        text=df["risque_predit"], textposition="inside",
        textfont=dict(color="#0d1117", size=10, family="Outfit", weight=700),
        name="RISK",
        width=0.7,
        marker=dict(opacity=0.8)
    ), row=1, col=2)

    fig.update_layout(
        **LAYOUT_BASE,
        height=380, 
        margin=dict(l=40, r=20, t=80, b=40),
        showlegend=False,
        title=dict(
            text="CLIMATE PROJECTIONS & FIRE RISK (2026-2035)",
            font=dict(family="Outfit", size=18, color="#f0f6fc"),
            x=0, y=0.98
        ),
    )
    
    for i in fig['layout']['annotations']:
        i['font'] = dict(family="Outfit", size=13, color="#8b949e")
        
    fig.update_xaxes(gridcolor="rgba(240, 246, 252, 0.05)", linecolor="rgba(240, 246, 252, 0.1)",
                     tickmode="linear", dtick=1)
    fig.update_yaxes(gridcolor="rgba(240, 246, 252, 0.05)", linecolor="rgba(240, 246, 252, 0.1)")
    return fig


# ── Feature importance ───────────────────────────────────────────
def feature_importance(df: pd.DataFrame) -> go.Figure:
    df = df.sort_values("importance", ascending=True)
    colors = ["#58a6ff" if v > 0 else "#30363d" for v in df["importance"]]
    fig = go.Figure(go.Bar(
        x=df["importance"], y=df["feature"],
        orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[f" {v:.3f}" for v in df["importance"]],
        textposition="outside", 
        textfont=dict(color="#f0f6fc", size=12, family="JetBrains Mono"),
        width=0.6,
        marker=dict(opacity=0.8)
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        height=400,
        margin=dict(l=120, r=40, t=80, b=40),
        title=dict(
            text="RANDOM FOREST FEATURE IMPORTANCE",
            font=dict(family="Outfit", size=18, color="#f0f6fc"),
            x=0, y=0.98
        ),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="RELATIVE IMPORTANCE",
                   range=[0, df["importance"].max() * 1.25]),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title=""),
    )
    return fig


# ── Scenario comparison ──────────────────────────────────────────
def scenario_chart(df: pd.DataFrame) -> go.Figure:
    colors = [RISK_COLORS.get(r, "#8b949e") for r in df["risque_predit"]]
    fig = go.Figure(go.Bar(
        x=df["scenario"], y=df["confiance"] * 100,
        marker_color=colors, marker_line_width=0,
        text=[f"<b>{r.upper()}</b><br>{c:.0%}" for r, c in
              zip(df["risque_predit"], df["confiance"])],
        textposition="outside",
        textfont=dict(color="#f0f6fc", size=10, family="Outfit"),
        width=0.6,
        marker=dict(opacity=0.8)
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        height=400,
        margin=dict(l=40, r=20, t=80, b=60),
        title=dict(
            text="2026 SCENARIO RESULTS — MODEL CONFIDENCE",
            font=dict(family="Outfit", size=18, color="#f0f6fc"),
            x=0, y=0.98
        ),
        xaxis=dict(**LAYOUT_BASE["xaxis"], tickangle=-25, tickfont=dict(size=10)),
        yaxis=dict(**LAYOUT_BASE["yaxis"], range=[0, 120], title="CONFIDENCE (%)"),
    )
    return fig


# ── Hourly weather trend ─────────────────────────────────────────
def hourly_trend(hourly: dict) -> go.Figure:
    if not hourly or "time" not in hourly:
        return go.Figure()
    times = hourly["time"][:24]
    temps = hourly.get("temperature_2m", [])[:24]
    hum   = hourly.get("relative_humidity_2m", [])[:24]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=times, y=temps, mode="lines+markers",
        name="TEMPÉRATURE (°C)", line=dict(color="#f0883e", width=4, shape="spline"),
        marker=dict(size=8, color="#f0883e", line=dict(color="#0d1117", width=1.5)),
        fill="tozeroy", fillcolor="rgba(240, 136, 62, 0.1)"
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=times, y=hum, mode="lines+markers",
        name="HUMIDITÉ (%)", line=dict(color="#58a6ff", width=4, shape="spline"),
        marker=dict(size=8, color="#58a6ff", line=dict(color="#0d1117", width=1.5)),
        fill="tozeroy", fillcolor="rgba(88, 166, 255, 0.1)"
    ), secondary_y=True)
    
    fig.update_layout(
        **LAYOUT_BASE, 
        height=320,
        margin=dict(l=40, r=40, t=60, b=40),
        title=dict(
            text="WEATHER TREND — NEXT 24 HOURS",
            font=dict(family="Outfit", size=16, color="#f0f6fc"),
            x=0, y=0.98
        ),
        legend=dict(
            x=0.5, y=1.15, 
            orientation="h",
            xanchor="center",
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)"
        ),
    )
    fig.update_yaxes(title_text="TEMP (°C)", secondary_y=False)
    fig.update_yaxes(title_text="HUMIDITY (%)", secondary_y=True)
    return fig

