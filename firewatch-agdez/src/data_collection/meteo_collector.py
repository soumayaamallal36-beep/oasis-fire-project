"""
FireWatch Agdez - Collecteur de données météorologiques
Utilise l'API Open-Meteo pour récupérer les données météo en temps réel
et historiques pour la région d'Agdez, Drâa-Tafilalet.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

import pandas as pd
import numpy as np
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MeteoCollector")


class MeteoCollector:
    """Collecteur de données météorologiques via l'API Open-Meteo."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le collecteur avec la configuration du projet."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.base_url: str = self.config["apis"]["open_meteo"]["base_url"]
        self.historical_url: str = self.config["apis"]["open_meteo"]["historical_url"]
        self.timeout: int = self.config["apis"]["open_meteo"]["timeout"]
        self.retry_attempts: int = self.config["apis"]["open_meteo"]["retry_attempts"]
        self.retry_delay: int = self.config["apis"]["open_meteo"]["retry_delay"]
        self.default_lat: float = self.config["location"]["latitude"]
        self.default_lon: float = self.config["location"]["longitude"]
        logger.info("MeteoCollector initialisé pour %s (%.4f, %.4f)",
                     self.config["location"]["name"], self.default_lat, self.default_lon)

    def _request_with_retry(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Effectue une requête HTTP avec retry et backoff exponentiel."""
        last_exception: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                logger.info("Requête API (tentative %d/%d): %s", attempt, self.retry_attempts, url)
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                last_exception = e
                wait_time = self.retry_delay * (2 ** (attempt - 1))
                logger.warning("Erreur requête (tentative %d): %s. Retry dans %ds...",
                               attempt, str(e), wait_time)
                if attempt < self.retry_attempts:
                    time.sleep(wait_time)
        raise ConnectionError(
            f"Échec après {self.retry_attempts} tentatives: {last_exception}"
        )

    def fetch_current(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        """
        Récupère les données météo actuelles pour une position donnée.

        Args:
            lat: Latitude (défaut: Agdez)
            lon: Longitude (défaut: Agdez)

        Returns:
            Dictionnaire avec temp, humidity, wind_speed, wind_direction, precipitation.
        """
        lat = lat or self.default_lat
        lon = lon or self.default_lon

        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "temperature_2m,relativehumidity_2m,windspeed_10m,precipitation",
            "timezone": "auto",
            "forecast_days": 1,
        }

        data = self._request_with_retry(self.base_url, params)

        current = data.get("current_weather", {})
        hourly = data.get("hourly", {})

        # Récupérer l'index horaire le plus proche
        current_hour = datetime.now().hour
        idx = min(current_hour, len(hourly.get("temperature_2m", [])) - 1)

        humidity_list = hourly.get("relativehumidity_2m", hourly.get("relative_humidity_2m", []))
        humidity_val = humidity_list[idx] if idx < len(humidity_list) else 30.0

        precip_list = hourly.get("precipitation", [])
        precip_val = precip_list[idx] if idx < len(precip_list) else 0.0

        result = {
            "temperature": current.get("temperature", 25.0),
            "humidity": humidity_val,
            "wind_speed": current.get("windspeed", 10.0),
            "wind_direction": current.get("winddirection", 0),
            "precipitation": precip_val,
            "weather_code": current.get("weathercode", 0),
            "timestamp": datetime.now().isoformat(),
            "latitude": lat,
            "longitude": lon,
        }

        logger.info("Données actuelles: T=%.1f°C, H=%.0f%%, V=%.1f km/h",
                     result["temperature"], result["humidity"], result["wind_speed"])
        return result

    def fetch_historical(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo historiques pour une période donnée.

        Args:
            lat: Latitude (défaut: Agdez)
            lon: Longitude (défaut: Agdez)
            start_date: Date de début au format YYYY-MM-DD (défaut: 30 jours avant)
            end_date: Date de fin au format YYYY-MM-DD (défaut: hier)

        Returns:
            DataFrame avec colonnes: date, temperature, humidity, wind_speed, precipitation.
        """
        lat = lat or self.default_lat
        lon = lon or self.default_lon

        if not end_date:
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                     "precipitation_sum,windspeed_10m_max,et0_fao_evapotranspiration",
            "timezone": "auto",
        }

        data = self._request_with_retry(self.historical_url, params)
        daily = data.get("daily", {})

        df = pd.DataFrame({
            "date": pd.to_datetime(daily.get("time", [])),
            "temperature_max": daily.get("temperature_2m_max", []),
            "temperature_min": daily.get("temperature_2m_min", []),
            "temperature": daily.get("temperature_2m_mean", []),
            "precipitation": daily.get("precipitation_sum", []),
            "wind_speed": daily.get("windspeed_10m_max", []),
            "evapotranspiration": daily.get("et0_fao_evapotranspiration", []),
        })

        # Estimer l'humidité relative à partir de la plage de températures
        if not df.empty:
            temp_range = df["temperature_max"] - df["temperature_min"]
            df["humidity"] = np.clip(80 - temp_range * 3 + np.random.normal(0, 5, len(df)), 5, 95)
            df["humidity"] = df["humidity"].round(1)

        logger.info("Données historiques: %d jours récupérés (%s → %s)", len(df), start_date, end_date)
        return df

    def fetch_forecast(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        days: int = 7,
    ) -> pd.DataFrame:
        """
        Récupère les prévisions météo pour les prochains jours.

        Args:
            lat: Latitude
            lon: Longitude
            days: Nombre de jours de prévision (max 16)

        Returns:
            DataFrame avec les prévisions journalières.
        """
        lat = lat or self.default_lat
        lon = lon or self.default_lon

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "windspeed_10m_max,weathercode",
            "timezone": "auto",
            "forecast_days": min(days, 16),
        }

        data = self._request_with_retry(self.base_url, params)
        daily = data.get("daily", {})

        df = pd.DataFrame({
            "date": pd.to_datetime(daily.get("time", [])),
            "temperature_max": daily.get("temperature_2m_max", []),
            "temperature_min": daily.get("temperature_2m_min", []),
            "precipitation": daily.get("precipitation_sum", []),
            "wind_speed": daily.get("windspeed_10m_max", []),
            "weather_code": daily.get("weathercode", []),
        })

        df["temperature"] = (df["temperature_max"] + df["temperature_min"]) / 2
        logger.info("Prévisions: %d jours récupérés", len(df))
        return df

    @staticmethod
    def save_to_csv(data: pd.DataFrame, filepath: str) -> None:
        """
        Sauvegarde un DataFrame dans un fichier CSV.

        Args:
            data: DataFrame à sauvegarder.
            filepath: Chemin du fichier de sortie.
        """
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        data.to_csv(filepath, index=False, encoding="utf-8")
        logger.info("Données sauvegardées dans %s (%d lignes)", filepath, len(data))


if __name__ == "__main__":
    collector = MeteoCollector()

    # Récupérer les données actuelles
    current = collector.fetch_current()
    print("\n=== Données météo actuelles (Agdez) ===")
    for k, v in current.items():
        print(f"  {k}: {v}")

    # Récupérer l'historique des 30 derniers jours
    historical = collector.fetch_historical()
    print(f"\n=== Historique ({len(historical)} jours) ===")
    print(historical.head(10).to_string(index=False))

    # Sauvegarder
    collector.save_to_csv(historical, "data/raw/meteo_historical.csv")
    print("\n✅ Collecte météo terminée avec succès.")
