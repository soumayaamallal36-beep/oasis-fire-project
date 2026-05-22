"""
FireWatch Agdez - Préprocesseur de données
Normalisation, imputation des valeurs manquantes, et encodage.
"""
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
import joblib, yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Preprocessor")

class Preprocessor:
    """Préprocesseur pour la normalisation et l'imputation des données."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise le préprocesseur."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.scaler: Optional[StandardScaler] = None
        self.imputer: Optional[SimpleImputer] = None
        self.feature_columns = self.config["features"]["feature_columns"]
        logger.info("Preprocessor initialisé (%d features)", len(self.feature_columns))

    def fit_transform(self, df: pd.DataFrame, target_col: str = "fire_risk_level") -> Tuple[np.ndarray, np.ndarray]:
        """Ajuste et transforme les données pour l'entraînement."""
        X = df[self.feature_columns].copy()
        y = df[target_col].values if target_col in df.columns else np.zeros(len(df))
        self.imputer = SimpleImputer(strategy="median")
        X_imputed = self.imputer.fit_transform(X)
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_imputed)
        logger.info("Fit-transform: %d échantillons, %d features", X_scaled.shape[0], X_scaled.shape[1])
        return X_scaled, y

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transforme de nouvelles données avec le scaler ajusté."""
        if self.scaler is None or self.imputer is None:
            raise ValueError("Le préprocesseur n'a pas été ajusté. Appelez fit_transform d'abord.")
        X = df[self.feature_columns].copy()
        X_imputed = self.imputer.transform(X)
        return self.scaler.transform(X_imputed)

    def save(self, path: str = "models/preprocessor.pkl") -> None:
        """Sauvegarde le préprocesseur."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({"scaler": self.scaler, "imputer": self.imputer, "features": self.feature_columns}, path)
        logger.info("Préprocesseur sauvegardé: %s", path)

    def load(self, path: str = "models/preprocessor.pkl") -> None:
        """Charge un préprocesseur sauvegardé."""
        data = joblib.load(path)
        self.scaler = data["scaler"]
        self.imputer = data["imputer"]
        self.feature_columns = data["features"]
        logger.info("Préprocesseur chargé: %s", path)

    @staticmethod
    def detect_outliers(df: pd.DataFrame, columns: List[str], threshold: float = 3.0) -> pd.DataFrame:
        """Détecte les outliers par z-score."""
        from scipy import stats
        z_scores = np.abs(stats.zscore(df[columns].fillna(0)))
        mask = (z_scores < threshold).all(axis=1)
        n_outliers = (~mask).sum()
        logger.info("Outliers détectés: %d/%d (seuil z=%.1f)", n_outliers, len(df), threshold)
        return df[mask].copy()

    @staticmethod
    def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
        """Traite les valeurs manquantes avec des stratégies adaptées."""
        result = df.copy()
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if result[col].isna().sum() > 0:
                result[col].fillna(result[col].median(), inplace=True)
        logger.info("Valeurs manquantes traitées")
        return result

if __name__ == "__main__":
    np.random.seed(42)
    data = pd.DataFrame({
        "temperature": np.random.uniform(20, 45, 100),
        "humidity": np.random.uniform(5, 70, 100),
        "wind_speed": np.random.uniform(5, 40, 100),
        "precipitation": np.random.uniform(0, 10, 100),
        "ndvi": np.random.uniform(0.05, 0.4, 100),
        "fwi": np.random.uniform(0, 50, 100),
        "kbdi": np.random.uniform(0, 600, 100),
        "spi_3m": np.random.uniform(-2, 2, 100),
        "season": np.random.choice([1,2,3,4], 100),
        "elevation": np.random.uniform(700, 1600, 100),
        "slope": np.random.uniform(0, 20, 100),
        "aspect": np.random.uniform(0, 360, 100),
        "distance_to_forest": np.random.uniform(0, 50, 100),
        "previous_fires_3y": np.random.randint(0, 10, 100),
        "drought_index": np.random.uniform(0, 1, 100),
        "fire_risk_level": np.random.choice([0,1,2,3], 100),
    })
    pp = Preprocessor()
    X, y = pp.fit_transform(data)
    print(f"X shape: {X.shape}, y shape: {y.shape}")
    pp.save()
    print("✅ Préprocesseur testé et sauvegardé.")
