"""
src/ops/dashboard_ops.py
──────────────────────────
Fonctions de rendu pour le centre opérationnel du dashboard.
Interface unique page unique avec 9 sections.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from src.prediction.feature_engineering import calculer_features
from src.prediction.model_inference import charger_modele, predire_risque
from src.prediction.report_generator import generer_synthese
from src.prediction.risk_alert import evaluer_et_alerter
from src.prediction.scenario_runner import build_scenarios
from src.prediction.climate_trend import project_climate
from src.ai.bulletin import generer_bulletin
from src.ai.explanator import analyser_risque, generer_explication
from src.ai.recommender import generer_recommandations
from src.ai.awareness import generer_message_population, generer_message_autorites
from src.ops.stats import kpi_alertes, repartition_niveaux
from src.ops.timeline import charger_timeline


# ─── SECTION 1 : HEADER ───

def render_header(risque: str, confiance: float):
    couleurs = {
        "Faible": ("🟢", "#28A745"),
        "Moyen": ("🟡", "#FFC107"),
        "Élevé": ("🟠", "#FD7E14"),
        "Très élevé": ("🔴", "#DC3545"),
    }
    icone, color = couleurs.get(risque, ("⚪", "#6C757D"))

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, {color}15, {color}05);
                    padding: 1.5rem; border-radius: 15px;
                    border-left: 8px solid {color}; margin-bottom: 1rem;">
            <h1 style="margin:0; color:{color};">
                {icone} Centre Opérationnel — Surveillance Incendie Agdez
            </h1>
            <p style="color:#666; margin:0;">
                {datetime.now().strftime("%d/%m/%Y %H:%M")}
                · Risque actuel : <strong style="color:{color};">{risque}</strong>
                · Confiance : {confiance:.0%}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── SECTION 2 : KPIs ───

def render_kpis(risque: str, temperature=None, humidite=None, vent=None,
                precipitation=None, ndvi=None):
    ops = kpi_alertes()
    cols = st.columns(7)
    data = [
        ("🔥 Risque", risque, "Très élevé" in risque),
        ("📈 Confiance", f"{ops['aujourdhui']}",
         ops["aujourdhui"] > 0),
        ("📅 Cette semaine", f"{ops['semaine']}",
         ops["semaine"] >= 2),
        ("📊 Ce mois", f"{ops['mois']}",
         ops["mois"] >= 5),
        ("⏱ Dernière alerte", ops["temps_ecoule_str"] if ops["temps_ecoule"] else "Aucune",
         ops["temps_ecoule"] is not None and ops["temps_ecoule"].total_seconds() < 3600),
        ("🌡️ Temp.", f"{temperature}°C" if temperature else "N/A",
         temperature is not None and temperature > 35),
        ("💧 Humidité", f"{humidite}%" if humidite else "N/A",
         humidite is not None and humidite < 15),
    ]
    for col, (label, value, alert) in zip(cols, data):
        bg = "#FFEAA7" if alert else "#F0F2F6"
        col.markdown(
            f"""<div style="background:{bg}; padding:0.8rem; border-radius:12px; text-align:center;">
                <small>{label}</small><br/><strong style="font-size:1.3rem;">{value}</strong>
            </div>""",
            unsafe_allow_html=True,
        )


# ─── SECTION 3 : DASHBOARD CONDENSÉ ───

def render_dashboard_condense(temperature, humidite, precipitation, vent,
                               ndvi, risque, confiance, probas, features):
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Bulletin IA", "📊 Facteurs", "📈 Graphiques", "🌍 Carte"
    ])

    with tab1:
        st.subheader("Bulletin Automatique")
        bulletin = generer_bulletin(
            risque, confiance, temperature, humidite, precipitation, vent, ndvi
        )
        st.markdown(bulletin["bulletin_texte"])

        with st.expander("Message à la population"):
            st.markdown(bulletin["message_population"])
        with st.expander("Message aux autorités"):
            st.markdown(bulletin["message_autorites"])

    with tab2:
        col1, col2 = st.columns(2)
        analyse = analyser_risque(
            temperature, humidite, precipitation, vent, ndvi, risque
        )
        with col1:
            st.subheader("🔴 Facteurs aggravants")
            if analyse["facteurs_aggravants"]:
                for nom, val, sev in analyse["facteurs_aggravants"]:
                    label = nom.replace("_", " ").title()
                    ic = "🔴" if sev == "CRITIQUE" else "🟠"
                    st.markdown(f"{ic} **{label}** : {val}")
            else:
                st.success("Aucun facteur aggravant détecté.")
        with col2:
            st.subheader("✅ Facteurs favorables")
            if analyse["facteurs_favorables"]:
                for nom, val, _ in analyse["facteurs_favorables"]:
                    label = nom.replace("_", " ").title()
                    st.markdown(f"✅ **{label}** : {val}")
            else:
                st.warning("Aucun facteur favorable notable.")

        if features:
            st.subheader("Importance des facteurs")
            try:
                imp = pd.read_csv("models/metadata/feature_importance.csv")
                imp = imp.sort_values("importance", ascending=False).head(8)
                st.bar_chart(imp, x="feature", y="importance", height=250)
            except Exception:
                st.caption("Fichier feature_importance.csv non disponible")

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Conditions météo")
            meteo_df = pd.DataFrame([{
                "Température": temperature, "Humidité": humidite,
                "Précipitation": precipitation, "Vent": vent,
            }])
            st.bar_chart(meteo_df.T, height=250)
        with col2:
            st.subheader("Probabilités")
            if probas:
                proba_df = pd.DataFrame(
                    list(probas.items()), columns=["Niveau", "Probabilité"]
                )
                st.bar_chart(proba_df.set_index("Niveau"), height=250)

        st.subheader("Tendance climatique")
        try:
            clim = project_climate()
            col_a, col_b = st.columns(2)
            col_a.metric("Température moyenne", f"{clim.get('mean_temp_2035', 'N/A')}°C")
            col_b.metric("Évolution", clim.get("trend_temp", "N/A"))
        except Exception:
            st.caption("Tendance climatique indisponible")

    with tab4:
        st.subheader("Carte de risque")
        try:
            from dashboard.components.maps import afficher_carte_folium
            afficher_carte_folium()
        except ImportError:
            st.warning("Module carte Folium non disponible.")


# ─── SECTION 4 : RECOMMANDATIONS ───

def render_recommandations(risque: str, temperature=None, humidite=None,
                            vent=None, precipitation=None, ndvi=None):
    st.markdown("## 🛡️ Recommandations opérationnelles")
    recs = generer_recommandations(risque, temperature, humidite, vent,
                                    precipitation, ndvi)
    for r in recs:
        st.markdown(f"- {r}")


# ─── SECTION 5 : TIMELINE ───

def render_timeline():
    st.markdown("## ⏳ Timeline des alertes")
    entries = charger_timeline(limite=15, ordre="desc")
    if entries:
        for e in entries:
            ic = "🔴" if e["classe"] == "danger" else "🟠" if e["classe"] == "warning" else "🟡"
            st.markdown(f"{ic} **{e['date_str']}** — Risque **{e['risque']}** — 🌡️ {e['temperature']} 💧 {e['humidite']} 💨 {e['vent']}")
    else:
        st.info("Aucune alerte dans l'historique.")


# ─── SECTION 6 : STATISTIQUES ───

def render_statistiques():
    st.markdown("## 📊 Statistiques opérationnelles")
    ops = kpi_alertes()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Alertes aujourd'hui", ops["aujourdhui"])
    col2.metric("Cette semaine", ops["semaine"])
    col3.metric("Ce mois", ops["mois"])
    col4.metric("Total", ops["total"])

    try:
        rep = repartition_niveaux()
        if rep:
            st.subheader("Répartition par niveau de risque")
            cols = st.columns(len(rep))
            for col, (niveau, count) in zip(cols, rep.items()):
                col.metric(niveau, count)
    except Exception:
        pass


# ─── SECTION 7 : SENSIBILISATION ───

def render_sensibilisation(risque: str, temperature=None, vent=None):
    st.markdown("## 📢 Messages de sensibilisation")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 👥 Population")
        st.info(generer_message_population(risque, temperature, vent))
    with col_b:
        st.markdown("### 🏛️ Autorités")
        st.warning(generer_message_autorites(risque))


# ─── SECTION 8 : EXPORT ───

def render_export(bulletin_texte: str):
    st.markdown("## 📤 Export & Partage")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "📄 Télécharger le bulletin (TXT)",
            data=bulletin_texte,
            file_name=f"bulletin_incendie_agdez_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "📊 Exporter les KPIs (CSV)",
            data="",
            file_name=f"kpi_export_{datetime.now().strftime('%Y%m%d')}.csv",
            use_container_width=True,
        )
    with col3:
        if st.button("🔄 Rafraîchir les données", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


# ─── SECTION 9 : LOGS ───

def render_logs():
    st.markdown("## 📝 Journal d'activité")
    try:
        with open("logs/dashboard.log", "r", encoding="utf-8") as f:
            lignes = f.readlines()[-30:]
        for l in lignes:
            st.text(l.strip())
    except (FileNotFoundError, IOError):
        st.warning("Fichier de logs non trouvé.")
