"""
Page 7 — Modèle IA & Analytics
Feature importance, model metadata, training statistics, scenario results.
"""

import sys, json
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

from components.ui     import GLOBAL_CSS, section_header, kpi_card, glass_card
from components.charts import feature_importance, scenario_chart, probability_bars

st.set_page_config(page_title="Modèle IA · OASIS Fire", page_icon="🤖",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

META_PATH   = PROJECT_ROOT / "models" / "metadata" / "model_info.json"
FEAT_CSV    = PROJECT_ROOT / "models" / "metadata" / "feature_importance.csv"
SCEN_CSV    = PROJECT_ROOT / "models" / "metadata" / "predictions_scenarios_2026.csv"
PROJ_CSV    = PROJECT_ROOT / "models" / "metadata" / "projections_climatiques.csv"

RISK_COLORS = {"Faible":"#3fb950","Moyen":"#d29922","Élevé":"#f0883e","Très élevé":"#f85149"}

LAYOUT_BASE = dict(
    paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
    font=dict(family="Inter", color="#8b949e", size=12),
    margin=dict(l=40, r=20, t=40, b=40),
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_meta():
    if META_PATH.exists():
        with open(META_PATH) as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=3600, show_spinner=False)
def load_feat():
    if FEAT_CSV.exists():
        return pd.read_csv(FEAT_CSV)
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_scenarios():
    if SCEN_CSV.exists():
        return pd.read_csv(SCEN_CSV)
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_projections():
    if PROJ_CSV.exists():
        return pd.read_csv(PROJ_CSV)
    return None


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Modèle IA")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    meta = load_meta()
    st.markdown(f"""
    <div style='font-size:0.8rem;color:#8b949e;background:#0d1117;
                border:1px solid #21262d;border-radius:8px;padding:0.7rem;'>
        📦 <b style='color:#c9d1d9;'>{meta.get('modele','Random Forest')}</b><br>
        📅 {meta.get('annees_train','2017-2025')}<br>
        🎯 Précision CV : <b style='color:#3fb950;'>{meta.get('accuracy_cv',0):.1%}</b><br>
        📐 Features : {len(meta.get('features',[]))}<br>
        🏷️ Classes : {len(meta.get('classes',[]))}<br>
        🔖 v{meta.get('version','1.0.0')}
    </div>
    """, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "IA Model Architecture & Analytics",
    "Predictive engineering · Feature importance analysis · Neural explainability · Training logs",
    "🤖",
), unsafe_allow_html=True)

# ── KPIs ─────────────────────────────────────────────────────────
meta  = load_meta()
df_fe = load_feat()
df_sc = load_scenarios()

acc   = meta.get("accuracy_cv", 0)
std   = meta.get("accuracy_cv_std", 0)
n_ft  = len(meta.get("features", []))
n_cls = len(meta.get("classes", []))

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card("CV Accuracy Score", f"{acc:.1%}",
                         f"± {std:.1%} standard dev", "🎯",
                         "#3fb950" if acc > 0.8 else "#d29922"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Primary Algorithm", meta.get("modele","RF"),
                         "Auto-ML Optimized Selection", "🤖", "#58a6ff"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("Input Feature Space", str(n_ft),
                         "Dimensionality Index", "📐", "#8b5cf6"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Classification Layers", str(n_cls),
                         "Multi-Class Threat Levels", "🏷️", "#f0883e"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Feature Importance",
    "🔮 Scenario Inference",
    "📈 Dynamic Projections",
    "📋 Model Config & Specs",
])

with tab1:
    if df_fe is not None:
        col_chart, col_table = st.columns([2.2, 1.3])
        with col_chart:
            fig = feature_importance(df_fe)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with col_table:
            feat_rank_html = ""
            sorted_fe = df_fe.sort_values("importance", ascending=False)
            for _, row in sorted_fe.iterrows():
                imp = row["importance"]
                color = "#58a6ff" if imp > 0.05 else "#484f58"
                feat_rank_html += f"""
<div style='margin-bottom:12px;'>
    <div style='display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:5px;'>
        <span style='color:#c9d1d9; font-weight:600;'>{row['feature']}</span>
        <span style='color:{color}; font-family:JetBrains Mono;'>{imp:.4f}</span>
    </div>
    <div style='background:rgba(240, 246, 252, 0.05); border-radius:10px; height:6px; overflow:hidden;'>
        <div style='width:{imp/df_fe["importance"].max()*100:.0f}%; height:100%; background:{color}; border-radius:10px;'></div>
    </div>
</div>
""".strip()
            st.markdown(glass_card(feat_rank_html, title="Signal Ranking", icon="📐"), unsafe_allow_html=True)

            st.markdown(glass_card("""
                <div style='font-size:0.85rem; line-height:1.6;'>
                    <b style='color:#58a6ff;'>Signal Intelligence:</b> The model prioritizes <b style='color:#f0f6fc;'>Temperature</b> and <b style='color:#f0f6fc;'>Humidity</b> as the primary drivers of fuel aridity.<br><br>
                    <b style='color:#d29922;'>Topographic Coupling:</b> Aspect and Slope interact with wind vectors to create localized propagation 'funnels' in the Agdez valley.
                </div>
            """, title="Expert Data Science Note", icon="🔬"), unsafe_allow_html=True)

        zero_ft = df_fe[df_fe["importance"] == 0]["feature"].tolist()
        if zero_ft:
            st.markdown(f"""
                <div style='background:rgba(210,153,34,0.05); border:1px solid rgba(210,153,34,0.2);
                            border-left:5px solid #d29922; border-radius:12px;
                            padding:1rem 1.5rem; margin-top:1.5rem; display:flex; align-items:center; gap:20px;'>
                    <div style='font-size:1.8rem;'>⚠️</div>
                    <div>
                        <div style='color:#d29922; font-size:0.85rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;'>Invariant Features Detected</div>
                        <div style='color:#c9d1d9; font-size:0.9rem; margin-top:4px;'>{", ".join(zero_ft)}</div>
                        <div style='color:#8b949e; font-size:0.75rem; margin-top:5px;'>These inputs show zero variance in the Agdez locale and should be pruned to optimize dimensionality.</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Feature importance metrics not yet computed. Retrain model to generate.")

with tab2:
    if df_sc is not None:
        fig = scenario_chart(df_sc)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        for cat, grp in df_sc.groupby("categorie"):
            cat_html = ""
            for _, r in grp.iterrows():
                rc = RISK_COLORS.get(r["risque_predit"], "#8b949e")
                cat_html += f"""
<div style='display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
    <span style='color:#c9d1d9; font-size:0.85rem; font-weight:600;'>{r["scenario"]}</span>
    <div style='display:flex; gap:15px; align-items:center;'>
        <span style='color:#8b949e; font-size:0.75rem; font-family:JetBrains Mono;'>T={r["temperature"]}° H={r["humidite"]}%</span>
        <span style='color:{rc}; font-weight:800; font-size:0.8rem;'>{r["risque_predit"].upper()}</span>
        <span style='color:#484f58; font-size:0.8rem; font-weight:700;'>{r["confiance"]:.0%}</span>
    </div>
</div>
""".strip()
            st.markdown(glass_card(cat_html, title=f"Inference: {cat}", icon="🔮"), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("Scenario analysis requires `run_prediction_pipeline.py` execution.")

with tab3:
    df_proj = load_projections()
    if df_proj is not None:
        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(
            x=df_proj["annee"], y=df_proj["temperature"],
            mode="lines+markers", line=dict(color="#f85149", width=3),
            marker=dict(size=10, color="#f85149", line=dict(color="#0d1117", width=2)),
            fill="tozeroy", fillcolor="rgba(248,81,73,0.05)", name="July Projected Temp",
        ))
        fig_t.update_layout(**LAYOUT_BASE, height=320, 
                          title=dict(text="AI-Decadal Temperature Projection (2026-2035)", font=dict(size=14, family="Outfit")),
                          xaxis=dict(gridcolor="rgba(240,246,252,0.05)", dtick=1))
        st.plotly_chart(fig_t, use_container_width=True, config={"displayModeBar": False})

        fig_c = go.Figure(go.Bar(
            x=df_proj["annee"], y=df_proj["confiance"] * 100,
            marker_color=[RISK_COLORS.get(r, "#8b949e") for r in df_proj["risque_predit"]],
            text=[f"{c:.0%}" for c in df_proj["confiance"]], textposition="outside",
        ))
        fig_c.update_layout(**LAYOUT_BASE, height=280, 
                          title=dict(text="Model Reliability Decay over Time Horizon", font=dict(size=14, family="Outfit")),
                          yaxis=dict(range=[0, 115], showticklabels=False),
                          xaxis=dict(dtick=1))
        st.plotly_chart(fig_c, use_container_width=True, config={"displayModeBar": False})

with tab4:
    col_meta, col_details = st.columns(2)
    with col_meta:
        meta_html = ""
        meta_items = [
            ("Core Algorithm", meta.get("modele", "RandomForest")),
            ("CV Score (Avg)", f"{meta.get('accuracy_cv', 0):.4f}"),
            ("CV Variance (Std)", f"± {meta.get('accuracy_cv_std', 0):.4f}"),
            ("Input Dimension", str(n_ft)),
            ("Target Mapping", f"{n_cls} Discrete Risk Levels"),
            ("Region Code", meta.get("zone", "Agdez")),
            ("Training Epochs", meta.get("annees_train", "2017–2025")),
            ("Build Version", meta.get("version", "1.1.0")),
        ]
        for name, val in meta_items:
            meta_html += f"""
            <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
                <span style='color:#8b949e; font-size:0.85rem;'>{name}</span>
                <span style='color:#f0f6fc; font-weight:700; font-size:0.85rem; font-family:JetBrains Mono;'>{val}</span>
            </div>
            """
        st.markdown(glass_card(meta_html, title="Model Registry Metadata", icon="📋"), unsafe_allow_html=True)

    with col_details:
        features_html = ""
        for i, ft in enumerate(meta.get("features", []), 1):
            imp_val = 0.0
            if df_fe is not None:
                r_fe = df_fe[df_fe["feature"] == ft]
                if not r_fe.empty: imp_val = r_fe["importance"].values[0]
            features_html += f"""
            <div style='display:flex; justify-content:space-between; padding:6px 0; font-size:0.8rem;'>
                <span style='color:#8b949e;'>{i:02}. {ft}</span>
                <span style='color:#58a6ff; font-family:JetBrains Mono;'>{imp_val:.4f}</span>
            </div>
            """
        st.markdown(glass_card(features_html, title="Feature Vector Specs", icon="📐"), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(glass_card(f"""
        <div style='font-family:JetBrains Mono,monospace; font-size:0.8rem; color:#3fb950; line-height:1.8;'>
            <span style='color:#8b949e;'># AUTOMATED PIPELINE LOGS</span><br>
            StandardScaler() → RFClassifier(n_estimators=200, max_depth=6, random_state=42)<br>
            StandardScaler() → GBClassifier(n_estimators=150, learning_rate=0.1, max_depth=4)<br>
            StandardScaler() → LogisticRegression(C=1.0, penalty='l2', solver='lbfgs')<br>
            <span style='color:#58a6ff;'>>>> FINAL SELECTION: StratifiedKFold(n_splits=5) + RandomizedSearchCV()</span>
        </div>
    """, title="Engineering Pipeline", icon="⚙️"), unsafe_allow_html=True)

