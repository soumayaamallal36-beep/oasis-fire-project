"""
FireWatch Agdez - Service de prédiction (inference pipeline)
Charge les modèles et expose la prédiction de risque d'incendie.
"""
import os, logging, math
from datetime import datetime
from typing import Dict, Any, Optional, List
import numpy as np
import joblib
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PredictionService")

RISK_LABELS = {0: "Faible", 1: "Moyen", 2: "Élevé", 3: "Très Élevé"}
FEATURE_ORDER = [
    "temperature","humidity","wind_speed","precipitation","ndvi","fwi","kbdi",
    "spi_3m","season","elevation","slope","aspect","distance_to_forest",
    "previous_fires_3y","drought_index"
]

class PredictionService:
    """Service d'inférence pour la prédiction de risque d'incendie."""

    def __init__(self, models_dir: str = "models", config_path: str = "config.yaml") -> None:
        """Charge le meilleur modèle disponible."""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.model_version = self.config["api"]["model_version"]
        self.model = None
        self.model_name = "none"
        self.models_loaded = 0
        self._load_best_model(models_dir)

    def _load_best_model(self, models_dir: str) -> None:
        """Charge le meilleur modèle (ensemble > XGBoost > autre)."""
        candidates = [
            ("ensemble_best.pkl", "Ensemble"),
            ("stacking_model.pkl", "Stacking"),
            ("voting_model.pkl", "Voting"),
            ("xgboost_model.pkl", "XGBoost"),
            ("lightgbm_model.pkl", "LightGBM"),
        ]
        for fname, name in candidates:
            path = os.path.join(models_dir, fname)
            if os.path.exists(path):
                try:
                    data = joblib.load(path)
                    if isinstance(data, dict) and "model" in data:
                        self.model = data["model"]
                        self.model_name = data.get("name", name)
                    else:
                        self.model = data
                        self.model_name = name
                    self.models_loaded = 1
                    logger.info("Modèle chargé: %s (%s)", self.model_name, path)
                    return
                except Exception as e:
                    logger.warning("Impossible de charger %s: %s", path, e)
        logger.warning("Aucun modèle trouvé. Utilisation du modèle de fallback.")
        self._create_fallback_model(models_dir)

    def _create_fallback_model(self, models_dir: str) -> None:
        """Crée un modèle de règles simples si aucun modèle ML n'est disponible."""
        self.model = None
        self.model_name = "RuleBasedFallback"

    def _compute_fwi(self, temp: float, hum: float, wind: float, rain: float) -> float:
        """Calcule le FWI simplifié."""
        hum = max(1, min(hum, 100))
        mo = 147.2*(101-hum)/(59.5+hum)
        if rain > 0.5:
            rf = rain-0.5
            mo = min(mo+42.5*rf*math.exp(-100/(251-mo))*(1-math.exp(-6.93/rf)), 250)
        ed = max(0.942*(hum**0.679)+11*math.exp((hum-100)/10)+0.18*(21.1-temp), 0)
        m = ed+(mo-ed)*0.5 if mo > ed else mo
        ffmc = max(0, min(59.5*(250-m)/(147.2+m), 101))
        fw = math.exp(0.05039*wind)
        fm = 147.2*(101-ffmc)/(59.5+ffmc)
        sf = 19.115*math.exp(-0.1386*fm)*(1+fm**5.31/4.93e7)
        isi = 0.208*fw*sf
        rk = max(1.894*(temp+1.1)*(100-hum)*1e-4, 0) if temp > -1.1 else 0
        bui = max(0.8*rk*2+2, 0)
        fd = 0.626*bui**0.809+2 if bui > 0 else 0
        b = 0.1*isi*fd
        fwi = math.exp(2.72*(0.434*math.log(b))**0.647) if b > 1 else b
        return round(max(0, min(fwi, 150)), 2)

    def _rule_based_predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """Prédiction par règles simples (fallback)."""
        t = features.get("temperature", 25)
        h = features.get("humidity", 50)
        w = features.get("wind_speed", 10)
        fwi = features.get("fwi", self._compute_fwi(t, h, w, features.get("precipitation", 0)))
        score = 0
        if t > 40: score += 3
        elif t > 35: score += 2
        elif t > 30: score += 1
        if h < 10: score += 3
        elif h < 20: score += 2
        elif h < 35: score += 1
        if w > 35: score += 2
        elif w > 25: score += 1
        if fwi > 40: score += 3
        elif fwi > 25: score += 2
        elif fwi > 15: score += 1
        level = min(score // 3, 3)
        conf_map = {0: 0.75, 1: 0.70, 2: 0.72, 3: 0.80}
        proba = [0.0]*4
        proba[level] = conf_map[level]
        remaining = 1 - proba[level]
        for i in range(4):
            if i != level:
                proba[i] = remaining / 3
        return {"level": RISK_LABELS[level], "level_code": level,
                "confidence": conf_map[level], "fwi": fwi,
                "probabilities": {RISK_LABELS[i]: round(p, 4) for i, p in enumerate(proba)}}

    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """Prédit le niveau de risque d'incendie."""
        t = features.get("temperature", 25)
        h = features.get("humidity", 50)
        w = features.get("wind_speed", 10)
        rain = features.get("precipitation", 0)
        fwi = self._compute_fwi(t, h, w, rain)
        features["fwi"] = fwi

        # KBDI simplifié
        tf = t*9/5+32
        kbdi = max(0, min((800-100)*(0.001+0.01*max(tf-50,0))/(1+10.88*math.exp(-0.001736*30))*10, 800))
        features.setdefault("kbdi", round(kbdi, 2))
        features.setdefault("spi_3m", 0.0)
        features.setdefault("season", ((datetime.now().month-1)//3)+1)
        features.setdefault("elevation", 1050.0)
        features.setdefault("slope", 8.5)
        features.setdefault("aspect", 180.0)
        features.setdefault("distance_to_forest", 15.0)
        features.setdefault("previous_fires_3y", 2)
        h_norm = max(1, min(h, 100))
        features.setdefault("drought_index", round(kbdi/800*0.5+(1-h_norm/100)*0.3+t/50*0.2, 3))
        features.setdefault("ndvi", 0.15)

        if self.model is None:
            result = self._rule_based_predict(features)
        else:
            X = np.array([[features.get(f, 0) for f in FEATURE_ORDER]])
            proba = self.model.predict_proba(X)[0]
            predicted = int(np.argmax(proba))
            result = {"level": RISK_LABELS[predicted], "level_code": predicted,
                      "confidence": round(float(np.max(proba)), 4), "fwi": fwi,
                      "probabilities": {RISK_LABELS[i]: round(float(p), 4) for i, p in enumerate(proba)}}

        # Facteurs de risque
        factors: List[str] = []
        if t > 35: factors.append(f"Température critique ({t:.1f}°C > 35°C)")
        if h < 20: factors.append(f"Humidité très basse ({h:.0f}% < 20%)")
        if w > 25: factors.append(f"Vent fort ({w:.1f} km/h > 25 km/h)")
        if fwi > 25: factors.append(f"FWI élevé ({fwi:.1f})")
        ndvi = features.get("ndvi", 0.2)
        if ndvi < 0.15: factors.append(f"Végétation sèche (NDVI={ndvi:.2f})")
        if not factors: factors.append("Conditions météo normales")

        result.update({"factors": factors, "timestamp": datetime.now().isoformat(),
                        "model_version": self.model_version})
        return result

if __name__ == "__main__":
    svc = PredictionService()
    test = {"temperature":38.5,"humidity":12.0,"wind_speed":28.0,"precipitation":0.0,"ndvi":0.10}
    result = svc.predict(test)
    print("=== Prédiction test ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
