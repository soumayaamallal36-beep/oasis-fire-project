"""
components/ui.py
────────────────
Reusable UI helpers: KPI cards, badges, alert boxes, CSS injection.
Dark scientific theme — colors inspired by NASA/Copernicus dashboards.
"""

RISK_COLORS = {
    "Faible":      "#3fb950",
    "Moyen":       "#d29922",
    "Élevé":       "#f0883e",
    "Très élevé":  "#f85149",
}
RISK_BG = {
    "Faible":      "rgba(63,185,80,0.12)",
    "Moyen":       "rgba(210,153,34,0.12)",
    "Élevé":       "rgba(240,136,62,0.12)",
    "Très élevé":  "rgba(248,81,73,0.15)",
}

# ── Global CSS ─────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Outfit:wght@400;600;700&display=swap');

/* ── Root & Background ─────────────────────────── */
html, body, [class*="css"] { 
    font-family: 'Inter', sans-serif !important; 
}

.stApp { 
    background: radial-gradient(circle at top right, #161b22, #0d1117) !important; 
    color: #c9d1d9 !important; 
}

/* Subtle background noise/texture */
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    opacity: 0.02;
    z-index: -1;
    pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3仿真%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
}

.stApp > header { background: transparent !important; }

/* ── Sidebar ───────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(22, 27, 34, 0.8) !important;
    backdrop-filter: blur(12px) !important;
    border-right: 1px solid rgba(240, 246, 252, 0.1) !important;
}

/* ── Main content padding ───────────────────────── */
.main .block-container { 
    padding: 2rem 3rem 4rem 3rem !important; 
    max-width: 1500px; 
}

/* ── Headings ───────────────────────────────────── */
h1, h2, h3 { 
    font-family: 'Outfit', sans-serif !important; 
    letter-spacing: -0.02em !important;
}

h1 { 
    color: #f0f6fc !important; 
    font-weight: 700 !important; 
    background: linear-gradient(90deg, #f0f6fc, #8b949e);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem !important;
}

/* ── Cards & Metrics ────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(22, 27, 34, 0.6) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(240, 246, 252, 0.1) !important;
    border-radius: 12px !important;
    padding: 1.2rem !important;
    transition: transform 0.3s ease, border-color 0.3s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-4px);
    border-color: rgba(88, 166, 255, 0.4) !important;
}

/* ── Tabs ───────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(22, 27, 34, 0.5) !important;
    border-radius: 12px !important;
    padding: 6px !important;
    border: 1px solid rgba(240, 246, 252, 0.05) !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}

.stTabs [aria-selected="true"] {
    background: rgba(88, 166, 255, 0.1) !important;
    color: #58a6ff !important;
}

/* ── Buttons ────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #21262d, #161b22) !important;
    border: 1px solid rgba(240, 246, 252, 0.1) !important;
    border-radius: 10px !important;
    padding: 0.5rem 1.5rem !important;
    font-weight: 600 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.stButton > button:hover {
    border-color: #58a6ff !important;
    box-shadow: 0 0 15px rgba(88, 166, 255, 0.2) !important;
    transform: scale(1.02);
}

/* ── Inputs ─────────────────────────────────────── */
[data-baseweb="select"] > div, .stTextInput > div > div {
    background: rgba(22, 27, 34, 0.6) !important;
    border-radius: 10px !important;
    border-color: rgba(240, 246, 252, 0.1) !important;
}

/* ── Animations ─────────────────────────────────── */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.stApp .element-container {
    animation: fadeInUp 0.5s ease-out forwards;
}

/* ── Custom Scrollbar ───────────────────────────── */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { 
    background: #30363d; 
    border-radius: 10px;
    border: 2px solid #0d1117;
}
::-webkit-scrollbar-thumb:hover { background: #484f58; }

</style>
"""

# ── Custom card HTML builders ────────────────────────────────────

def kpi_card(title: str, value: str, subtitle: str = "",
             icon: str = "", color: str = "#58a6ff",
             delta: str = "", delta_positive: bool = True) -> str:
    delta_color = "#3fb950" if delta_positive else "#f85149"
    delta_html = f'<div style="font-size:0.75rem;color:{delta_color};margin-top:4px;font-weight:600;">{delta}</div>' if delta else ""
    return f"""
<div style="background: rgba(22, 27, 34, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(240, 246, 252, 0.1); border-radius: 16px; padding: 1.2rem 1.5rem; margin-bottom: 0.5rem; border-top: 3px solid {color}; transition: all 0.3s ease; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);" class="kpi-card">
<div style="color:#8b949e;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;display:flex; align-items:center; gap:6px;">
<span style="font-size: 1.1rem;">{icon}</span> {title}
</div>
<div style="color:#f0f6fc;font-size:2rem;font-weight:800;font-family:'Outfit',sans-serif;line-height:1.1;letter-spacing:-0.02em;">
{value}
</div>
{delta_html}
{'<div style="color:#8b949e;font-size:0.8rem;margin-top:8px;font-weight:500;">' + subtitle + '</div>' if subtitle else ""}
</div>
""".strip()

def glass_card(content: str, title: str = "", icon: str = "", border_color: str = "rgba(240, 246, 252, 0.1)") -> str:
    header = f"""
<div style="color:#8b949e;font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;display:flex; align-items:center; gap:8px;">
<span style="font-size: 1rem;">{icon}</span> {title}
</div>
""".strip() if title else ""
    
    return f"""
<div style="background: rgba(22, 27, 34, 0.4); backdrop-filter: blur(15px); border: 1px solid {border_color}; border-radius: 20px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);">
{header}
<div style="color:#c9d1d9;">
{content}
</div>
</div>
""".strip()

def risk_badge(level: str, size: str = "normal") -> str:
    color = RISK_COLORS.get(level, "#8b949e")
    bg = RISK_BG.get(level, "rgba(139,148,158,0.1)")
    font = "1rem" if size == "normal" else ("1.4rem" if size == "large" else "0.78rem")
    pad = "6px 16px" if size == "normal" else ("12px 24px" if size == "large" else "4px 10px")
    
    return f"""
<div style="
    background:{bg};
    color:{color};
    border:1px solid {color}40;
    border-radius:100px;
    padding:{pad};
    font-size:{font};
    font-weight:700;
    display:inline-flex;
    align-items:center;
    gap:8px;
    font-family: 'Outfit', sans-serif;
">
    <span style="width:8px; height:8px; background:{color}; border-radius:50%; box-shadow: 0 0 10px {color};"></span>
    {level.upper()}
</div>
""".strip()

def alert_card(title: str, message: str, level: str = "Élevé",
               timestamp: str = "", scenario: str = "") -> str:
    color = RISK_COLORS.get(level, "#8b949e")
    bg = RISK_BG.get(level, "rgba(139,148,158,0.1)")
    icon = "🔴" if level == "Très élevé" else ("🟠" if level == "Élevé" else "🟡")
    ts_html = f'<div style="color:#8b949e;font-size:0.75rem;margin-top:10px; display:flex; align-items:center; gap:5px;">⏱ {timestamp}</div>' if timestamp else ""
    sc_html = f'<div style="color:#8b949e;font-size:0.8rem;margin-top:8px; font-weight:600; color:{color};">📍 {scenario}</div>' if scenario else ""
    
    return f"""
<div style="background: linear-gradient(135deg, {bg}, transparent); backdrop-filter: blur(10px); border: 1px solid {color}30; border-left: 5px solid {color}; border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
<span style="font-size:1.2rem;">{icon}</span>
<span style="color:#f0f6fc;font-weight:700;font-size:1rem; font-family:'Outfit', sans-serif;">{title}</span>
<span style="margin-left:auto; background:{color}20; color:{color}; border-radius:6px; padding:3px 10px; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;">{level}</span>
</div>
<div style="color:#c9d1d9;font-size:0.9rem;line-height:1.5;">{message}</div>
{sc_html}
{ts_html}
</div>
""".strip()

def section_header(title: str, subtitle: str = "", icon: str = "") -> str:
    return f"""
<div style="margin-bottom:2.5rem; padding-bottom:1.2rem; border-bottom: 1px solid rgba(240, 246, 252, 0.1);">
<div style="font-size:1.8rem; font-weight:800; color:#f0f6fc; font-family:'Outfit', sans-serif; display:flex; align-items:center; gap:12px;">
<span style="background: rgba(88, 166, 255, 0.1); padding: 10px; border-radius: 12px; border: 1px solid rgba(88, 166, 255, 0.2);">{icon}</span>
{title}
</div>
{'<div style="color:#8b949e; font-size:1rem; margin-top:10px; font-weight:400; margin-left:60px;">' + subtitle + '</div>' if subtitle else ""}
</div>
""".strip()

def status_dot(online: bool = True) -> str:
    color = "#3fb950" if online else "#f85149"
    label = "Sytème Opérationnel" if online else "Hors ligne"
    return f"""
<div style="display:inline-flex;align-items:center;gap:10px;
             background: rgba(63, 185, 80, 0.05); padding: 6px 15px; border-radius: 100px;
             border: 1px solid rgba(63, 185, 80, 0.2);
             font-size:0.8rem; font-weight:600; color:{color};">
    <span style="width:10px;height:10px;border-radius:50%;
                 background:{color};
                 box-shadow:0 0 12px {color};
                 animation:pulse-dot 2s infinite;
                 display:inline-block;"></span>
    {label.upper()}
</div>
<style>
@keyframes pulse-dot {{ 0%,100% {{ opacity:1; transform: scale(1); }} 50% {{ opacity:0.5; transform: scale(0.85); }} }}
</style>
""".strip()


def metric_group(metrics: list) -> str:
    """
    metrics: list of dicts with {title, value, icon, color}
    """
    items_html = ""
    for m in metrics:
        items_html += f"""
<div style="flex: 1; min-width: 120px; padding: 0 10px; border-right: 1px solid rgba(240, 246, 252, 0.05);">
    <div style="color:#8b949e; font-size:0.68rem; text-transform:uppercase; font-weight:600; margin-bottom:4px;">{m.get('icon','')} {m.get('title','')}</div>
    <div style="color:#f0f6fc; font-size:1.2rem; font-weight:700; font-family:'Outfit';">{m.get('value','')}</div>
</div>
""".strip()
    return f"""
<div style="background: rgba(22, 27, 34, 0.4); backdrop-filter: blur(10px); border: 1px solid rgba(240, 246, 252, 0.1); border-radius: 16px; padding: 1rem; display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
{items_html}
</div>
""".strip()


# ── Animation Helpers ───────────────────────────────────────────
def scroll_reveal():
    return """
    <script>
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal');
            }
        });
    });
    document.querySelectorAll('.glass-card').forEach((el) => observer.observe(el));
    </script>
    """


