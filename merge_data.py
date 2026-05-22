import pandas as pd

# =========================
# LOAD DATA
# =========================

weather = pd.read_csv(
    "data/meteo_daily/weather_history.csv"
)

climat = pd.read_csv(
    "data/processed/csv/climat/climat_donnees_prediction.csv",
    sep=";",
    encoding="latin1"
)

# =========================
# CLEAN
# =========================

weather = weather.dropna()
climat = climat.dropna()

# =========================
# SELECT FEATURES
# =========================

weather = weather[
    [
        "temperature",
        "humidite",
        "precipitation",
        "vent"
    ]
]

climat = climat[
    [
        "Température (°C)",
        "Humidité (%)",
        "Précipitations (mm)",
        "Vent (m/s)",
        "Risque"
    ]
]

# =========================
# RENAME COLUMNS
# =========================

climat.columns = [
    "temperature",
    "humidity",
    "precipitation",
    "wind",
    "risk"
]

weather.columns = [
    "temperature",
    "humidity",
    "precipitation",
    "wind"
]

# =========================
# COMBINE DATA
# =========================

final_df = pd.concat(
    [weather, climat],
    ignore_index=True
)

# =========================
# SAVE
# =========================

final_df.to_csv(
    "data/final/final_dataset.csv",
    index=False
)

print("✅ Final dataset created")
print(final_df.head())