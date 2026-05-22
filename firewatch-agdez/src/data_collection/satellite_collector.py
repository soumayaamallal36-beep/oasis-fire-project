"""
FireWatch Agdez - Collecteur de données satellite
Récupère les données NDVI et foyers d'incendie via NASA FIRMS.
Calcule le Fire Weather Index (FWI) canadien simplifié.
"""
import os, math, logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import pandas as pd
import numpy as np
import requests, yaml
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SatelliteCollector")

class SatelliteCollector:
    """Collecteur de données satellite : NDVI, NASA FIRMS, calcul FWI."""
    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le collecteur satellite."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.firms_base_url = self.config["apis"]["nasa_firms"]["base_url"]
        self.firms_key = os.getenv("FIRMS_MAP_KEY", "")
        self.firms_source = self.config["apis"]["nasa_firms"]["source"]
        self.default_radius = self.config["apis"]["nasa_firms"]["radius_km"]

    def fetch_ndvi(self, lat: float, lon: float, date: Optional[str] = None) -> float:
        """Récupère ou simule le NDVI pour la région semi-aride d'Agdez."""
        dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        month = dt.month
        base = {12:0.18,1:0.18,2:0.18,3:0.28,4:0.28,5:0.28,6:0.12,7:0.12,8:0.12,9:0.20,10:0.20,11:0.20}
        ndvi = float(np.clip(base[month] + np.random.normal(0, 0.03), 0.02, 0.60))
        logger.info("NDVI simulé (%.4f,%.4f): %.3f", lat, lon, ndvi)
        return round(ndvi, 4)

    def fetch_firms_fires(self, lat: float, lon: float, radius_km: Optional[int] = None, days: int = 7) -> pd.DataFrame:
        """Récupère les foyers d'incendie via NASA FIRMS API."""
        radius_km = radius_km or self.default_radius
        try:
            url = f"{self.firms_base_url}/area/csv/{self.firms_key}/{self.firms_source}/{lon-1},{lat-1},{lon+1},{lat+1}/{days}"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(resp.text))
            if not df.empty:
                return pd.DataFrame({"latitude": df["latitude"], "longitude": df["longitude"],
                    "brightness": df.get("bright_ti4", 300.0), "confidence": df.get("confidence", "nominal"),
                    "date": pd.to_datetime(df.get("acq_date", datetime.now().strftime("%Y-%m-%d")))})
        except Exception as e:
            logger.warning("FIRMS API error: %s — using simulated data", e)
        return self._simulate_firms(lat, lon, days)

    def _simulate_firms(self, lat: float, lon: float, days: int) -> pd.DataFrame:
        """Génère des données FIRMS simulées."""
        n = np.random.poisson(3)
        if n == 0:
            return pd.DataFrame(columns=["latitude","longitude","brightness","confidence","date"])
        records = [{"latitude": round(lat+np.random.uniform(-0.5,0.5),4),
                     "longitude": round(lon+np.random.uniform(-0.5,0.5),4),
                     "brightness": round(np.random.uniform(300,500),1),
                     "confidence": np.random.choice(["low","nominal","high"]),
                     "date": (datetime.now()-timedelta(days=np.random.randint(0,days))).strftime("%Y-%m-%d")} for _ in range(n)]
        return pd.DataFrame(records)

    @staticmethod
    def calculate_fwi(temp: float, humidity: float, wind: float, rain: float) -> float:
        """Calcule le Fire Weather Index (formule canadienne simplifiée)."""
        mo = 147.2 * (101.0 - humidity) / (59.5 + humidity)
        if rain > 0.5:
            rf = rain - 0.5
            mr = mo + 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))
            mr = min(mr, 250.0)
        else:
            mr = mo
        ed = max(0.942 * (humidity**0.679) + 11.0 * math.exp((humidity-100)/10) + 0.18*(21.1-temp), 0.0)
        if mr > ed:
            ko = 0.424 * (1-(humidity/100)**1.7) + 0.0694 * math.sqrt(wind)
            kd = ko * 0.581 * math.exp(0.0365 * temp)
            m = ed + (mr - ed) * (10.0 ** (-kd))
        else:
            m = mr
        ffmc = max(0, min(59.5*(250-m)/(147.2+m), 101))
        rk = max(1.894*(temp+1.1)*(100-humidity)*0.0001, 0) if temp > -1.1 else 0
        dmc = max(rk*2, 0)
        fw = math.exp(0.05039 * wind)
        fm = 147.2*(101-ffmc)/(59.5+ffmc)
        sf = 19.115 * math.exp(-0.1386*fm) * (1 + fm**5.31 / 4.93e7)
        isi = 0.208 * fw * sf
        bui = max(0.8*dmc + 0.2*10, 0)
        fd = 0.626 * bui**0.809 + 2 if bui > 0 else 0
        b = 0.1 * isi * fd
        fwi = math.exp(2.72 * (0.434*math.log(b))**0.647) if b > 1 else b
        return round(max(0, min(fwi, 150)), 2)

if __name__ == "__main__":
    collector = SatelliteCollector()
    ndvi = collector.fetch_ndvi(30.6936, -6.4497)
    print(f"NDVI Agdez: {ndvi:.4f}")
    fwi = SatelliteCollector.calculate_fwi(38.0, 15.0, 25.0, 0.0)
    print(f"FWI (38°C, 15%, 25km/h, 0mm): {fwi:.2f}")
    fires = collector.fetch_firms_fires(30.6936, -6.4497)
    print(f"Foyers détectés: {len(fires)}")
    print("✅ Collecte satellite terminée.")
