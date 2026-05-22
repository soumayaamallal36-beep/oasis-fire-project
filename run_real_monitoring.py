import json
import time
import joblib
import numpy as np

from src.alerts.email_alert import send_fire_alert

# =========================
# LOAD AI MODEL
# =========================

model = joblib.load("best_model.pkl")

print("🔥 AI Fire Monitoring Started...")

while True:

    try:

        # =========================
        # LOAD ETL DATA
        # =========================

        with open(
            "data/meteo_daily/latest_weather.json",
            "r"
        ) as f:

            weather = json.load(f)

        # =========================
        # EXTRACT VALUES
        # =========================

        temperature = weather["temperature"]

        humidity = weather["humidite"]

        precipitation = weather["precipitation"]

        wind_speed = weather["vent"]

        # =========================
        # AI PREDICTION
        # =========================

        features = np.array([[
            temperature,
            humidity,
            precipitation,
            wind_speed
        ]])

        prediction = model.predict(features)[0]

        # =========================
        # RISK LEVEL
        # =========================

        if prediction == 1:

            risk = "Élevé"

        else:

            risk = "Faible"

        print(f"\n🔥 AI Current Risk: {risk}")

        # =========================
        # EMAIL ALERT
        # =========================

        if risk == "Élevé":

            message = f"""
            🔥 FIRE RISK ALERT 🔥

            AI detected a HIGH wildfire risk.

            Risk Level: {risk}

            Temperature: {temperature} °C
            Humidity: {humidity} %
            Precipitation: {precipitation} mm
            Wind Speed: {wind_speed} km/h
            """

            send_fire_alert(message)

            print("✅ Alert email sent")

        else:

            print("✅ No danger detected")

    except Exception as e:

        print(f"❌ Error: {e}")

    # =========================
    # WAIT 5 MINUTES
    # =========================

    time.sleep(300)