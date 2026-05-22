# daily_weather_task.py
import os
import sys
import json
import requests
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import smtplib
from email.mime.text import MIMEText

# إعداد المسارات
BASE = Path(__file__).parent
MODEL_PATH = BASE / "models" / "trained" / "model_risque_incendie.pkl"
LE_PATH = BASE / "models" / "trained" / "label_encoder.pkl"
METEOR_DATA_DIR = BASE / "data" / "meteo_daily"  # سننشئ هذا المجلد
METEOR_DATA_DIR.mkdir(parents=True, exist_ok=True)

# تحميل النموذج
model = joblib.load(MODEL_PATH)
le = joblib.load(LE_PATH)

# ثوابت منطقة أكدز (نفسها الموجودة في الداشبورد)
LAT, LON = 30.69, -6.45
PENTE = 5.73
ALTITUDE = 1169.3
EXPOSITION = 165.51

# دالة بناء الميزات (مطابقة للداشبورد)
FEAT_ORDER = [
    "temperature","humidite","precipitation","vent",
    "pente","altitude","exposition","ndvi_avant",
    "indice_secheresse","indice_propagation",
    "stress_vegetal","exposition_sud","mois_num",
]

def build_X(t, h, p, v, mois_num=1, ndvi=0.144):
    row = dict(temperature=t, humidite=h, precipitation=p, vent=v,
               pente=PENTE, altitude=ALTITUDE, exposition=EXPOSITION,
               ndvi_avant=ndvi, mois_num=mois_num)
    df = pd.DataFrame([row])
    df["indice_secheresse"]  = (df["temperature"] - df["humidite"]) / (df["precipitation"] + 0.1)
    df["indice_propagation"] = df["vent"] * np.sin(np.radians(PENTE))
    df["stress_vegetal"]     = (1 - df["ndvi_avant"]) * df["temperature"] / 10
    df["exposition_sud"]     = np.cos(np.radians(EXPOSITION - 180)).clip(0, 1)
    return df[FEAT_ORDER]

def predict_risk(t, h, p, v, mois_num=1, ndvi=0.144):
    X = build_X(t, h, p, v, mois_num, ndvi)
    y_pred = model.predict(X)[0]
    probas = model.predict_proba(X)[0]
    label = le.inverse_transform([y_pred])[0]
    conf = float(probas.max())
    proba_dict = {cls: float(pr) for cls, pr in zip(le.classes_, probas)}
    return label, conf, proba_dict

# جلب البيانات من API
def fetch_weather():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
           "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
           "&timezone=Africa%2FCasablanca")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()["current"]
        # تصفية سرعة الرياح: إذا تجاوزت 20 m/s نعتبرها خطأ ونستعمل قيمة افتراضية 4.0
        wind = data["wind_speed_10m"]
        if wind > 20:
            print(f"⚠️ Vent anormal ({wind} m/s) -> remplacement par 4.0")
            wind = 4.0
        return {
            "temperature": data["temperature_2m"],
            "humidite": data["relative_humidity_2m"],
            "precipitation": data["precipitation"],
            "vent": wind,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Erreur météo API: {e}")
        return None

# إرسال تنبيه بريد إلكتروني (اختياري)
def send_email_alert(risk, conf, weather):
    # يجب تكوين SMTP (مثال باستخدام Gmail)
    sender = "ton_email@gmail.com"
    password = "ton_mot_de_passe_app"
    receiver = "responsable@protectioncivile.ma"
    subject = f"🔥 ALERTE INCENDIE Agdez - Risque {risk}"
    body = f"""
    Alerte automatique du {datetime.now().strftime('%Y-%m-%d %H:%M')}
    Risque prédit : {risk} (confiance {conf:.0%})
    Conditions :
      - Température : {weather['temperature']}°C
      - Humidité : {weather['humidite']}%
      - Précipitations : {weather['precipitation']} mm
      - Vent : {weather['vent']} m/s
    Recommandation : {"DANGER IMMÉDIAT" if risk=="Très élevé" else "Surveillance renforcée"}
    """
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("Email envoyé")
    except Exception as e:
        print(f"Erreur email: {e}")

# إرسال تنبيه تيليغرام (اختياري)
def send_telegram_alert(risk, conf):
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    text = f"🔥 {risk} ({conf:.0%}) à Agdez - {datetime.now().strftime('%H:%M')}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
        print("Telegram envoyé")
    except:
        pass

# حفظ البيانات اليومية (للداشبورد)
def save_daily_data(weather, risk, conf, probas):
    # حفظ آخر ميتيو
    with open(METEOR_DATA_DIR / "latest_weather.json", "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    # حفظ آخر تنبيه
    alert_data = {
        "date": weather["timestamp"],
        "risk": risk,
        "confidence": conf,
        "probas": probas,
        "weather": weather
    }
    with open(METEOR_DATA_DIR / "last_alert.json", "w", encoding="utf-8") as f:
        json.dump(alert_data, f, ensure_ascii=False, indent=2)
    # إضافة إلى التاريخ (CSV)
    hist_file = METEOR_DATA_DIR / "weather_history.csv"
    df_new = pd.DataFrame([{
        "timestamp": weather["timestamp"],
        "temperature": weather["temperature"],
        "humidite": weather["humidite"],
        "precipitation": weather["precipitation"],
        "vent": weather["vent"],
        "risk_predicted": risk,
        "confidence": conf,
        "prob_faible": probas.get("Faible",0),
        "prob_moyen": probas.get("Moyen",0),
        "prob_eleve": probas.get("Élevé",0),
        "prob_tres_eleve": probas.get("Très élevé",0)
    }])
    if hist_file.exists():
        df_hist = pd.read_csv(hist_file)
        df_hist = pd.concat([df_hist, df_new], ignore_index=True)
    else:
        df_hist = df_new
    df_hist.to_csv(hist_file, index=False)
    print("Données sauvegardées")

# الوظيفة الرئيسية
def main():
    print(f"{datetime.now()} - Début de la tâche météo")
    weather = fetch_weather()
    if weather is None:
        print("Impossible d'obtenir la météo, arrêt.")
        return
    risk, conf, probas = predict_risk(
        weather["temperature"], weather["humidite"],
        weather["precipitation"], weather["vent"],
        mois_num=1  # Juillet par défaut
    )
    print(f"Risque prédit: {risk} (confiance {conf:.0%})")
    save_daily_data(weather, risk, conf, probas)
    if risk in ["Élevé", "Très élevé"]:
        print("Déclenchement des alertes")
        # send_email_alert(risk, conf, weather)   # décommenter après configuration
        # send_telegram_alert(risk, conf)         # décommenter après configuration
    print("Tâche terminée.")

if __name__ == "__main__":
    main()