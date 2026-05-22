"""
Page 6 — Système d'Alertes
Real-time alert monitoring, history, severity levels, future predictions.
"""

import sys, json
from pathlib import Path
from datetime import datetime

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT  = DASHBOARD_DIR.parent
for p in [str(DASHBOARD_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.ui         import GLOBAL_CSS, section_header, alert_card, risk_badge, kpi_card, glass_card
from components.weather    import get_weather
from components.prediction import get_current_prediction, risk_recommendation, RISK_COLORS

st.set_page_config(page_title="Alertes · OASIS Fire", page_icon="🚨",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

ALERTS_DIR  = PROJECT_ROOT / "reports"
SYNTH_JSON  = PROJECT_ROOT / "reports" / "synthese_risque.json"
PROJ_CSV    = PROJECT_ROOT / "models" / "metadata" / "projections_climatiques.csv"
SC_CSV      = PROJECT_ROOT / "models" / "metadata" / "predictions_scenarios_2026.csv"

PRIORITY_COLORS = {
    "CRITIQUE": ("#f85149", "rgba(248,81,73,0.12)"),
    "HAUTE":    ("#f0883e", "rgba(240,136,62,0.12)"),
    "NORMALE":  ("#d29922", "rgba(210,153,34,0.12)"),
}


@st.cache_data(ttl=60, show_spinner=False)
def load_all_alerts():
    alerts = []
    for fp in sorted(ALERTS_DIR.glob("alerte_*.json"), reverse=True):
        try:
            with open(fp) as f:
                a = json.load(f)
            a["_file"] = fp.name
            alerts.append(a)
        except Exception:
            pass
    return alerts


@st.cache_data(ttl=60, show_spinner=False)
def load_synthesis():
    if SYNTH_JSON.exists():
        with open(SYNTH_JSON) as f:
            return json.load(f)
    return {}


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚨 Système d'Alertes")
    st.markdown("<hr style='border-color:#21262d;'>", unsafe_allow_html=True)
    filter_prio = st.multiselect(
        "Filtrer par priorité",
        ["CRITIQUE", "HAUTE", "NORMALE"],
        default=["CRITIQUE", "HAUTE"],
    )
    if st.button("🔄 Rafraîchir les alertes", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Header ────────────────────────────────────────────────────────
st.markdown(section_header(
    "Active Alert Monitoring System",
    "Real-time threat detection · Historical logs · Automated IA severity classification",
    "🚨",
), unsafe_allow_html=True)

# ── Current prediction ────────────────────────────────────────────
weather = get_weather()
label, conf, probas = get_current_prediction(weather)
reco    = risk_recommendation(label)
rc      = RISK_COLORS.get(label, "#8b949e")

# ── KPIs ─────────────────────────────────────────────────────────
alerts  = load_all_alerts()
synth   = load_synthesis()
n_crit  = sum(1 for a in alerts if a.get("priorite") == "CRITIQUE")
n_haute = sum(1 for a in alerts if a.get("priorite") == "HAUTE")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card("System Risk Status", label.upper(),
                         f"Confidence {conf:.0%}", "🔥", rc), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Critical Alerts", str(n_crit),
                         "L3 Severity Logs", "🔴", "#f85149"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("High Priority", str(n_haute),
                         "L2 Severity Logs", "🟠", "#f0883e"), unsafe_allow_html=True)
with c4:
    nb_sc = synth.get("scenarios_2026", {}).get("nb_alertes_eleve", 0)
    st.markdown(kpi_card("2026 Threat Scenarios", str(nb_sc),
                         "/ 10 Reference Case", "📋", "#d29922"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Current live alert ────────────────────────────────────────────
st.markdown("""
    <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
        <span style='font-size:1.2rem;'>⚡</span>
        <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
            Live Intelligence Feed — Active Session
        </span>
    </div>
""", unsafe_allow_html=True)
st.markdown(alert_card(
    f"SYSTEM ALERT: {label.upper()} RISK DETECTED",
    reco,
    level=label,
    timestamp=datetime.now().strftime("%H:%M · %d %b %Y"),
    scenario=f"TELEMETRY: T={weather['temperature']:.1f}°C · H={weather['humidite']:.0f}% · V={weather['vent']:.1f}m/s",
), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📋 Event History Log",
    "📊 Severity Distribution",
    "🔮 Predictive Alerts (2035)",
])

with tab1:
    filtered = [a for a in alerts if a.get("priorite", "NORMALE") in (filter_prio or ["CRITIQUE","HAUTE","NORMALE"])]
    if filtered:
        for a in filtered:
            pr, lv, ts = a.get("priorite", "NORMALE"), a.get("risque", "Élevé"), a.get("timestamp", "")[:16].replace("T", " ")
            sc, msg, cnf = a.get("scenario", ""), a.get("message", ""), a.get("confiance", 0)
            prcolor, prbg = PRIORITY_COLORS.get(pr, ("#8b949e", "rgba(139,148,158,0.1)"))
            
            history_item_html = f"""
            <div style='display:flex; align-items:center; justify-content:space-between; gap:15px;'>
                <div style='flex:1;'>
                    <div style='display:flex; align-items:center; gap:12px; margin-bottom:5px;'>
                        <span style='background:{prcolor}; width:8px; height:8px; border-radius:50%; box-shadow: 0 0 5px {prcolor};'></span>
                        <span style='color:{prcolor}; font-size:0.8rem; font-weight:700; text-transform:uppercase;'>{pr} Priority</span>
                        <span style='color:#484f58; font-size:0.75rem;'>|</span>
                        <span style='color:#8b949e; font-size:0.8rem; font-family:JetBrains Mono;'>{ts}</span>
                    </div>
                    <div style='color:#f0f6fc; font-size:0.9rem; font-weight:700;'>{lv.upper()} RISK DETECTED</div>
                    <div style='color:#8b949e; font-size:0.85rem; margin-top:4px;'>{msg}</div>
                </div>
                <div style='text-align:right;'>
                    <div style='color:#484f58; font-size:0.7rem; font-weight:600;'>CONFIDENCE</div>
                    <div style='color:#f0f6fc; font-size:1.1rem; font-weight:800; font-family:JetBrains Mono;'>{cnf:.0%}</div>
                </div>
            </div>
            """
            st.markdown(glass_card(history_item_html), unsafe_allow_html=True)
    else:
        st.markdown(glass_card("<div style='text-align:center; padding:2rem; color:#484f58;'>NO ACTIVE LOGS FOUND FOR SELECTED PRIORITY</div>"), unsafe_allow_html=True)

with tab2:
    if alerts:
        prio_count = {"CRITIQUE": n_crit, "HAUTE": n_haute, "NORMALE": len(alerts) - n_crit - n_haute}
        col_chart, col_info = st.columns([2, 1.5])
        with col_chart:
            fig = go.Figure(go.Pie(
                labels=list(prio_count.keys()), values=list(prio_count.values()),
                marker=dict(colors=["#f85149", "#f0883e", "#d29922"], line=dict(color="#0d1117", width=3)),
                hole=0.6, textinfo='none'
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#8b949e", family="Outfit"),
                              height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                              annotations=[dict(text=f"<span style='font-size:24px; font-weight:900; color:#f0f6fc;'>{len(alerts)}</span><br><span style='font-size:12px; color:#8b949e;'>EVENTS</span>",
                                                x=0.5, y=0.5, showarrow=False)])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_info:
            dist_html = ""
            for pr, cnt in prio_count.items():
                clr, bg = PRIORITY_COLORS.get(pr, ("#8b949e", "rgba(139,148,158,0.1)"))
                pct = cnt / len(alerts) * 100 if len(alerts) > 0 else 0
                dist_html += f"""
                <div style='display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid rgba(240, 246, 252, 0.05);'>
                    <div>
                        <div style='color:{clr}; font-size:0.75rem; font-weight:800; text-transform:uppercase;'>{pr}</div>
                        <div style='color:#f0f6fc; font-size:1.2rem; font-weight:800;'>{cnt}</div>
                    </div>
                    <div style='text-align:right;'>
                        <div style='color:#484f58; font-size:0.7rem;'>PROPORTION</div>
                        <div style='color:#8b949e; font-size:0.85rem; font-family:JetBrains Mono;'>{pct:.0f}%</div>
                    </div>
                </div>
                """
            st.markdown(glass_card(dist_html, title="System Breakdown", icon="📊"), unsafe_allow_html=True)

with tab3:
    if PROJ_CSV.exists():
        df_proj = pd.read_csv(PROJ_CSV)
        st.markdown("""
            <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
                <span style='font-size:1.2rem;'>🔮</span>
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                    Predictive Criticality Thresholds (2026-2035)
                </span>
            </div>
        """, unsafe_allow_html=True)
        high_risk = df_proj[df_proj["risque_predit"].isin(["Élevé","Très élevé"])]
        for _, row in high_risk.iterrows():
            rc2 = RISK_COLORS.get(row["risque_predit"], "#8b949e")
            proj_alert_html = f"""
            <div style='display:flex; align-items:center; justify-content:space-between; gap:20px;'>
                <div style='display:flex; align-items:center; gap:15px;'>
                    <div style='font-size:1.5rem; font-weight:900; color:{rc2}; font-family:JetBrains Mono;'>{int(row["annee"])}</div>
                    <div>
                        <div style='color:#f0f6fc; font-size:0.95rem; font-weight:700;'>{row["risque_predit"].upper()} RISK HORIZON</div>
                        <div style='color:#8b949e; font-size:0.8rem; margin-top:2px;'>T={row["temperature"]:.1f}°C · H={row["humidite"]:.1f}%</div>
                    </div>
                </div>
                <div style='text-align:right;'>
                    <div style='color:#484f58; font-size:0.7rem;'>IA CONFIDENCE</div>
                    <div style='color:{rc2}; font-size:1.1rem; font-weight:800;'>{row["confiance"]:.0%}</div>
                </div>
            </div>
            """
            st.markdown(glass_card(proj_alert_html), unsafe_allow_html=True)
    
    if SC_CSV.exists():
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='margin-bottom: 1rem; display:flex; align-items:center; gap:10px;'>
                <span style='font-size:1.2rem;'>📋</span>
                <span style="font-size:0.75rem; color:#8b949e; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;">
                    Reference Scenario Hazard Log
                </span>
            </div>
        """, unsafe_allow_html=True)
        df_sc = pd.read_csv(SC_CSV)
        df_crit = df_sc[df_sc["risque_predit"].isin(["Élevé","Très élevé"])]
        for _, row in df_crit.iterrows():
            st.markdown(alert_card(
                f"SCENARIO: {row['scenario'].upper()}",
                f"T={row['temperature']}°C · H={row['humidite']}% · P={row['precipitation']}mm · V={row['vent']}m/s",
                level=row["risque_predit"],
                timestamp=f"MATCH CONFIDENCE {row['confiance']:.0%}",
                scenario=row["categorie"].upper(),
            ), unsafe_allow_html=True)

