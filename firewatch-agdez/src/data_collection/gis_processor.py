"""
FireWatch Agdez - Processeur de données géographiques
Gère les données GIS : élévation, pente, aspect, distance aux forêts.
"""
import logging
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GISProcessor")

class GISProcessor:
    """Processeur de données géospatiales pour la région Drâa-Tafilalet."""

    # Données d'élévation simulées pour les villes clés de la région
    ELEVATION_DATA: Dict[str, Dict[str, float]] = {
        "Agdez": {"lat": 30.6936, "lon": -6.4497, "elevation": 1050, "slope": 8.5, "aspect": 180},
        "Zagora": {"lat": 30.3306, "lon": -5.8381, "elevation": 720, "slope": 3.2, "aspect": 195},
        "Ouarzazate": {"lat": 30.9200, "lon": -6.8936, "elevation": 1160, "slope": 5.1, "aspect": 210},
        "Tinghir": {"lat": 31.5147, "lon": -5.5328, "elevation": 1342, "slope": 12.3, "aspect": 165},
        "Errachidia": {"lat": 31.9314, "lon": -4.4267, "elevation": 1045, "slope": 4.8, "aspect": 190},
        "Boumalne": {"lat": 31.3722, "lon": -5.9953, "elevation": 1586, "slope": 15.7, "aspect": 170},
        "Tazzarine": {"lat": 30.7736, "lon": -5.5656, "elevation": 980, "slope": 6.4, "aspect": 200},
        "Alnif": {"lat": 31.1167, "lon": -5.1667, "elevation": 1050, "slope": 7.1, "aspect": 185},
    }

    FOREST_ZONES = [
        {"name": "Forêt de Jbel Saghro", "lat": 30.98, "lon": -6.15, "area_km2": 45},
        {"name": "Palmeraie Draa", "lat": 30.50, "lon": -6.30, "area_km2": 120},
        {"name": "Forêt Atlas", "lat": 31.20, "lon": -6.50, "area_km2": 200},
        {"name": "Oasis Zagora", "lat": 30.33, "lon": -5.84, "area_km2": 35},
    ]

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le processeur GIS."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        logger.info("GISProcessor initialisé pour la région Drâa-Tafilalet")

    def get_elevation(self, lat: float, lon: float) -> float:
        """Retourne l'élévation estimée pour une position donnée (interpolation)."""
        closest = min(self.ELEVATION_DATA.values(),
                      key=lambda p: (p["lat"]-lat)**2 + (p["lon"]-lon)**2)
        noise = np.random.normal(0, 20)
        return round(closest["elevation"] + noise, 1)

    def get_slope(self, lat: float, lon: float) -> float:
        """Retourne la pente estimée en degrés pour une position."""
        closest = min(self.ELEVATION_DATA.values(),
                      key=lambda p: (p["lat"]-lat)**2 + (p["lon"]-lon)**2)
        noise = np.random.normal(0, 1.5)
        return round(max(0, closest["slope"] + noise), 1)

    def get_aspect(self, lat: float, lon: float) -> float:
        """Retourne l'orientation du terrain en degrés (0-360)."""
        closest = min(self.ELEVATION_DATA.values(),
                      key=lambda p: (p["lat"]-lat)**2 + (p["lon"]-lon)**2)
        noise = np.random.normal(0, 15)
        return round((closest["aspect"] + noise) % 360, 1)

    def get_distance_to_forest(self, lat: float, lon: float) -> float:
        """Calcule la distance minimale à la zone forestière la plus proche (km)."""
        min_dist = float("inf")
        for forest in self.FOREST_ZONES:
            dist = self._haversine(lat, lon, forest["lat"], forest["lon"])
            min_dist = min(min_dist, dist)
        return round(min_dist, 2)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distance haversine entre deux points en km."""
        import math
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    def get_previous_fires(self, lat: float, lon: float, years: int = 3) -> int:
        """Estime le nombre d'incendies dans un rayon de 10km sur N années."""
        base_risk = 0.3 if self.get_distance_to_forest(lat, lon) < 20 else 0.1
        return int(np.random.poisson(base_risk * years * 5))

    def get_terrain_features(self, lat: float, lon: float) -> Dict[str, float]:
        """Récupère toutes les features géographiques pour un point."""
        return {
            "elevation": self.get_elevation(lat, lon),
            "slope": self.get_slope(lat, lon),
            "aspect": self.get_aspect(lat, lon),
            "distance_to_forest": self.get_distance_to_forest(lat, lon),
            "previous_fires_3y": self.get_previous_fires(lat, lon, 3),
        }

    def generate_terrain_grid(self, n_points: int = 100) -> pd.DataFrame:
        """Génère une grille de points avec leurs features terrain."""
        lat_range = (30.0, 32.0)
        lon_range = (-7.0, -4.0)
        lats = np.random.uniform(*lat_range, n_points)
        lons = np.random.uniform(*lon_range, n_points)
        records = []
        for lat, lon in zip(lats, lons):
            feat = self.get_terrain_features(lat, lon)
            feat["latitude"] = round(lat, 4)
            feat["longitude"] = round(lon, 4)
            records.append(feat)
        return pd.DataFrame(records)

if __name__ == "__main__":
    processor = GISProcessor()
    features = processor.get_terrain_features(30.6936, -6.4497)
    print("=== Features terrain Agdez ===")
    for k, v in features.items():
        print(f"  {k}: {v}")
    grid = processor.generate_terrain_grid(10)
    print(f"\nGrille terrain ({len(grid)} points):")
    print(grid.to_string(index=False))
    print("\n✅ Traitement GIS terminé.")
