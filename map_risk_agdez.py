# map_risk_agdez.py
import folium
import pandas as pd
from pathlib import Path

# قراءة توقعات السيناريوهات باش ناخذو الخطر ديال يوليوز العادي
scenarios = pd.read_csv("models/metadata/predictions_scenarios_2026.csv")
july_normal = scenarios[(scenarios["scenario"] == "Juillet 2026 (conditions moyennes)")]

if not july_normal.empty:
    risk = july_normal.iloc[0]["risque_predit"]
    conf = july_normal.iloc[0]["confiance"] * 100
else:
    risk = "غير معروف"
    conf = 0

# تحديد اللون
color_map = {
    "Faible": "green",
    "Moyen": "orange",
    "Élevé": "darkorange",
    "Très élevé": "red"
}
color = color_map.get(risk, "gray")

# إحداثيات أكدز (تقريبية)
agdez_coords = [30.697, -6.448]

# إنشاء الخريطة
m = folium.Map(location=agdez_coords, zoom_start=13)

# إضافة علامة دائرية
folium.CircleMarker(
    location=agdez_coords,
    radius=30,
    popup=f"<b>Agdez</b><br>Risque {risk}<br>Confiance {conf:.0f}%",
    color=color,
    fill=True,
    fill_color=color,
    fill_opacity=0.6,
    weight=2
).add_to(m)

# حفظ الخريطة
output_path = "reports/carte_risque_agdez.html"
m.save(output_path)
print(f"✅ الخريطة تما حفظها: {output_path}")
print(f"  ⇒  افتح الملف في المتصفح باش تشوفها.")