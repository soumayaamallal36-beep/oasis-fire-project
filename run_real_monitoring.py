import json
import time

from src.prediction.risk_engine import calculate_fire_risk
from src.alerts.email_alert import send_fire_alert

print("🔥 Fire Monitoring Started...")

while True:

    try:

        # Load ETL data
        with open(
            "data/meteo_daily/latest_weather.json",
            "r"
        ) as f:

            weather = json.load(f)

        # Extract values
        temperature = weather["temperature"]

        humidity = weather["humidite"]

        wind_speed = weather["vent"]

        # Temporary NDVI
        ndvi = 0.2

        # Calculate risk
        risk = calculate_fire_risk(
            temperature,
            humidity,
            wind_speed,
            ndvi
        )

        print(f"🔥 Current Risk: {risk}")

        # Send automatic alert
        if risk in ["Élevé", "Très élevé"]:

            message = f"""
            Fire Risk Alert

            Risk Level: {risk}

            Temperature: {temperature} °C
            Humidity: {humidity} %
            Wind Speed: {wind_speed} km/h
            """

            send_fire_alert(message)

        else:

            print("✅ No danger detected")

    except Exception as e:

        print(f"❌ Error: {e}")

    # Wait 5 minutes
    time.sleep(300)