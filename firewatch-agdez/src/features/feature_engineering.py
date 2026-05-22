"""
FireWatch Agdez - Feature Engineering
Calcule FWI, KBDI, SPI, et construit la matrice de features complète.
"""
import logging, math
from datetime import datetime
from typing import Dict, Optional, List
import numpy as np
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("FeatureEngineer")

class FeatureEngineer:
    """Ingénierie des features pour la prédiction d'incendies."""

    FEATURE_COLUMNS = [
        "temperature", "humidity", "wind_speed", "precipitation", "ndvi",
        "fwi", "kbdi", "spi_3m", "season", "elevation", "slope", "aspect",
        "distance_to_forest", "previous_fires_3y", "drought_index"
    ]

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le moteur de feature engineering."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        logger.info("FeatureEngineer initialisé")

    @staticmethod
    def compute_fwi(row: Dict[str, float]) -> float:
        """Calcule le Fire Weather Index (Van Wagner simplifié)."""
        temp = row.get("temperature", 25)
        hum = row.get("humidity", 50)
        wind = row.get("wind_speed", 10)
        rain = row.get("precipitation", 0)
        hum = max(1, min(hum, 100))
        mo = 147.2 * (101 - hum) / (59.5 + hum)
        if rain > 0.5:
            rf = rain - 0.5
            mo = mo + 42.5 * rf * math.exp(-100/(251-mo)) * (1 - math.exp(-6.93/rf))
            mo = min(mo, 250)
        ed = max(0.942*(hum**0.679) + 11*math.exp((hum-100)/10) + 0.18*(21.1-temp), 0)
        m = ed + (mo - ed) * 0.5 if mo > ed else mo
        ffmc = max(0, min(59.5*(250-m)/(147.2+m), 101))
        fw = math.exp(0.05039 * wind)
        fm = 147.2*(101-ffmc)/(59.5+ffmc)
        sf = 19.115 * math.exp(-0.1386*fm) * (1 + fm**5.31/4.93e7)
        isi = 0.208 * fw * sf
        rk = max(1.894*(temp+1.1)*(100-hum)*1e-4, 0) if temp > -1.1 else 0
        dmc = max(rk * 2, 0)
        bui = max(0.8*dmc + 2, 0)
        fd = 0.626 * bui**0.809 + 2 if bui > 0 else 0
        b = 0.1 * isi * fd
        fwi = math.exp(2.72*(0.434*math.log(b))**0.647) if b > 1 else b
        return round(max(0, min(fwi, 150)), 2)

    @staticmethod
    def compute_kbdi(temp: float, rain: float, prev_kbdi: float = 100.0) -> float:
        """Calcule le Keetch-Byram Drought Index."""
        temp_f = temp * 9/5 + 32
        net_rain = max(rain * 0.0394 - 0.2, 0)  # mm to inches, net
        drought_factor = (800 - prev_kbdi) * (0.001 + 0.01 * max(temp_f - 50, 0)) / (1 + 10.88 * math.exp(-0.001736 * 30))
        kbdi = prev_kbdi - net_rain * 100 + drought_factor
        return round(max(0, min(kbdi, 800)), 2)

    @staticmethod
    def compute_spi(precipitation_series: List[float], scale: int = 3) -> float:
        """Calcule le Standardized Precipitation Index sur N mois."""
        if len(precipitation_series) < scale:
            return 0.0
        window = precipitation_series[-scale:]
        mean_p = np.mean(window) if window else 1
        std_p = np.std(window) if len(window) > 1 else 1
        if std_p == 0:
            return 0.0
        current = window[-1]
        spi = (current - mean_p) / std_p
        return round(float(np.clip(spi, -3, 3)), 2)

    @staticmethod
    def encode_season(date: datetime) -> int:
        """Encode la saison : 1=hiver, 2=printemps, 3=été, 4=automne."""
        month = date.month if isinstance(date, datetime) else int(date)
        if month in [12, 1, 2]: return 1
        if month in [3, 4, 5]: return 2
        if month in [6, 7, 8]: return 3
        return 4

    def create_feature_matrix(self, meteo_df: pd.DataFrame, ndvi_values: Optional[List[float]] = None,
                               gis_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Construit la matrice de features complète pour l'entraînement."""
        df = meteo_df.copy()
        n = len(df)
        if ndvi_values is not None:
            df["ndvi"] = ndvi_values[:n] if len(ndvi_values) >= n else ndvi_values + [0.2]*(n-len(ndvi_values))
        elif "ndvi" not in df.columns:
            df["ndvi"] = 0.2
        df["fwi"] = df.apply(lambda r: self.compute_fwi(r.to_dict()), axis=1)
        prev_kbdi = 100.0
        kbdi_vals = []
        for _, row in df.iterrows():
            prev_kbdi = self.compute_kbdi(row.get("temperature",25), row.get("precipitation",0), prev_kbdi)
            kbdi_vals.append(prev_kbdi)
        df["kbdi"] = kbdi_vals
        precip = df["precipitation"].tolist() if "precipitation" in df.columns else [0]*n
        df["spi_3m"] = [self.compute_spi(precip[:i+1], 3) for i in range(n)]
        if "date" in df.columns:
            df["season"] = pd.to_datetime(df["date"]).apply(lambda d: self.encode_season(d))
        elif "season" not in df.columns:
            df["season"] = 3
        if gis_data is not None and not gis_data.empty:
            for col in ["elevation","slope","aspect","distance_to_forest","previous_fires_3y"]:
                if col in gis_data.columns:
                    df[col] = gis_data[col].values[:n] if len(gis_data) >= n else list(gis_data[col])+[gis_data[col].mean()]*(n-len(gis_data))
        for col, default in [("elevation",1050),("slope",8.5),("aspect",180),("distance_to_forest",15),("previous_fires_3y",2)]:
            if col not in df.columns:
                df[col] = default
        df["drought_index"] = (df["kbdi"]/800*0.5 + (1-df["humidity"]/100)*0.3 + df["temperature"]/50*0.2).round(3)
        result = df[self.FEATURE_COLUMNS].copy()
        logger.info("Matrice de features créée: %d lignes x %d colonnes", len(result), len(result.columns))
        return result

if __name__ == "__main__":
    fe = FeatureEngineer()
    fwi = fe.compute_fwi({"temperature":40,"humidity":10,"wind_speed":30,"precipitation":0})
    print(f"FWI (40°C, 10%, 30km/h): {fwi}")
    kbdi = fe.compute_kbdi(38, 0, 150)
    print(f"KBDI: {kbdi}")
    spi = fe.compute_spi([10,5,2,1,0.5], 3)
    print(f"SPI-3: {spi}")
    print(f"Saison mai: {fe.encode_season(datetime(2024,5,15))}")
    print("✅ Feature engineering terminé.")
