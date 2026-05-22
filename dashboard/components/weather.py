"""
components/weather.py
──────────────────────
Centralized Open-Meteo API fetcher with retry logic and cache fallback.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

LAT, LON = 30.69, -6.45
BASE_DIR = Path(__file__).resolve().parents[2]          # project root
WEATHER_CACHE = BASE_DIR / "data" / "meteo_daily" / "latest_weather.json"
HISTORY_CSV   = BASE_DIR / "data" / "meteo_daily" / "weather_history.csv"

WMO_CODES = {
    0:  ("☀️",  "Ciel dégagé"),
    1:  ("🌤️", "Principalement dégagé"),
    2:  ("⛅",  "Partiellement nuageux"),
    3:  ("☁️",  "Couvert"),
    45: ("🌫️", "Brouillard"),
    48: ("🌫️", "Brouillard givrant"),
    51: ("🌦️", "Bruine légère"),
    53: ("🌦️", "Bruine modérée"),
    61: ("🌧️", "Pluie légère"),
    63: ("🌧️", "Pluie modérée"),
    71: ("❄️",  "Neige légère"),
    80: ("🌦️", "Averses"),
    81: ("🌧️", "Averses modérées"),
    95: ("⛈️",  "Orage"),
}


def wmo_description(code: int) -> tuple[str, str]:
    """Return (emoji, label) for a WMO weather code."""
    for threshold in sorted(WMO_CODES.keys(), reverse=True):
        if code >= threshold:
            return WMO_CODES[threshold]
    return ("🌡️", "Variable")


def _build_api_url() -> str:
    return (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation,"
        f"wind_speed_10m,wind_direction_10m,weather_code"
        f"&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,"
        f"wind_speed_10m"
        f"&forecast_days=3"
        f"&timezone=Africa%2FCasablanca"
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_weather_api() -> dict | None:
    """Fetch current weather from Open-Meteo with 3 retries."""
    url = _build_api_url()
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
            cur = raw["current"]
            wind = float(cur["wind_speed_10m"])
            if wind > 25:          # sanity cap
                wind = 25.0
            emoji, desc = wmo_description(int(cur.get("weather_code", 0)))
            result = {
                "temperature":     float(cur["temperature_2m"]),
                "humidite":        float(cur["relative_humidity_2m"]),
                "precipitation":   float(cur["precipitation"]),
                "vent":            wind,
                "wind_direction":  float(cur.get("wind_direction_10m", 0)),
                "weather_code":    int(cur.get("weather_code", 0)),
                "weather_emoji":   emoji,
                "weather_desc":    desc,
                "timestamp":       cur["time"],
                "source":          "api",
                # include hourly for trend charts
                "hourly":          raw.get("hourly", {}),
            }
            return result
        except Exception:
            if attempt < 2:
                time.sleep(2)
    return None


def load_cached_weather() -> dict | None:
    """Load last saved weather from the JSON cache file."""
    if WEATHER_CACHE.exists():
        try:
            with open(WEATHER_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("source", "cache")
            data.setdefault("weather_emoji", "🌡️")
            data.setdefault("weather_desc", "Données en cache")
            data.setdefault("wind_direction", 0)
            data.setdefault("weather_code", 0)
            return data
        except Exception:
            return None
    return None


def get_weather() -> dict:
    """
    Primary entry point for weather data.
    Tries API → JSON cache → hardcoded fallback.
    Always returns a valid dict.
    """
    result = fetch_weather_api()
    if result is None:
        result = load_cached_weather()
    if result is None:
        result = {
            "temperature":   28.9,
            "humidite":      16.0,
            "precipitation": 0.0,
            "vent":          4.0,
            "wind_direction": 180,
            "weather_code":  0,
            "weather_emoji": "☀️",
            "weather_desc":  "Données de secours",
            "timestamp":     datetime.now().isoformat(),
            "source":        "fallback",
        }
    return result


def wind_direction_label(degrees: float) -> str:
    """Convert wind direction degrees to cardinal label."""
    dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    idx = round(degrees / 45) % 8
    return dirs[idx]
