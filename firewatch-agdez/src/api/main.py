"""
FireWatch Agdez - API FastAPI principale
Endpoints : health, predict, current-risk, history, alert/test.
"""
import os, sys, logging, sqlite3
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import yaml, uvicorn

# Ajouter le chemin racine du projet
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.api.schemas import (PredictionRequest, PredictionResponse,
    HealthResponse, HistoryEntry, AlertTestRequest, AlertTestResponse)
from src.api.prediction_service import PredictionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("FireWatchAPI")

# --- Config ---
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

DB_PATH = os.path.join(ROOT, config["paths"]["database"])
MODELS_DIR = os.path.join(ROOT, config["paths"]["models"])

# --- Base SQLite ---
def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, temperature REAL,
        humidity REAL, wind_speed REAL, precipitation REAL, ndvi REAL,
        lat REAL, lon REAL, risk_level TEXT, risk_code INTEGER,
        confidence REAL, fwi REAL, factors TEXT, model_version TEXT)""")
    conn.commit()
    conn.close()

def save_prediction(data: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO predictions
        (timestamp,temperature,humidity,wind_speed,precipitation,ndvi,lat,lon,
         risk_level,risk_code,confidence,fwi,factors,model_version)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data.get("timestamp",""), data.get("temperature",0), data.get("humidity",0),
         data.get("wind_speed",0), data.get("precipitation",0), data.get("ndvi",0),
         data.get("lat",0), data.get("lon",0), data.get("risk_level",""),
         data.get("risk_code",0), data.get("confidence",0), data.get("fwi",0),
         str(data.get("factors",[])), data.get("model_version","")))
    conn.commit()
    conn.close()

# --- App ---
prediction_service: Optional[PredictionService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global prediction_service
    init_db()
    prediction_service = PredictionService(models_dir=MODELS_DIR, config_path=CONFIG_PATH)
    logger.info("API démarrée — modèle: %s", prediction_service.model_name)
    yield
    logger.info("API arrêtée")

app = FastAPI(title="FireWatch Agdez API", version=config["api"]["model_version"],
              description="API IA de prédiction d'incendies — Drâa-Tafilalet", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health", response_model=HealthResponse)
async def health():
    """Vérification de santé de l'API."""
    return HealthResponse(status="ok", model_version=config["api"]["model_version"],
        timestamp=datetime.now().isoformat(),
        models_loaded=prediction_service.models_loaded if prediction_service else 0)

@app.post("/predict", response_model=PredictionResponse)
async def predict(req: PredictionRequest):
    """Prédiction de risque d'incendie à partir de données météo."""
    features = {"temperature": req.temperature, "humidity": req.humidity,
        "wind_speed": req.wind_speed, "precipitation": req.precipitation,
        "ndvi": req.ndvi, "elevation": req.elevation or 1050.0}
    if req.season:
        features["season"] = req.season
    result = prediction_service.predict(features)
    save_prediction({**features, "lat": req.lat, "lon": req.lon, **result})
    return PredictionResponse(risk_level=result["level"], risk_code=result["level_code"],
        confidence=result["confidence"], fwi=result["fwi"], factors=result["factors"],
        probabilities=result["probabilities"], timestamp=result["timestamp"],
        model_version=result["model_version"])

@app.get("/current-risk")
async def current_risk():
    """Prédiction en temps réel avec données météo actuelles."""
    try:
        from src.data_collection.meteo_collector import MeteoCollector
        collector = MeteoCollector(config_path=CONFIG_PATH)
        meteo = collector.fetch_current()
    except Exception as e:
        logger.warning("Erreur météo live: %s — données simulées", e)
        import random
        meteo = {"temperature": round(random.uniform(25,42),1),
                 "humidity": round(random.uniform(8,50),1),
                 "wind_speed": round(random.uniform(5,35),1),
                 "precipitation": round(random.uniform(0,2),2)}
    features = {"temperature": meteo["temperature"], "humidity": meteo["humidity"],
        "wind_speed": meteo["wind_speed"], "precipitation": meteo.get("precipitation",0),
        "ndvi": 0.15}
    result = prediction_service.predict(features)
    save_prediction({**features, "lat": config["location"]["latitude"],
        "lon": config["location"]["longitude"], **result})
    return {**result, "meteo": meteo}

@app.get("/history")
async def history(days: int = Query(7, ge=1, le=90)):
    """Historique des dernières prédictions."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM predictions WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 100", (since,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/alert/test", response_model=AlertTestResponse)
async def alert_test(req: AlertTestRequest):
    """Envoie une alerte de test."""
    email_ok = slack_ok = False
    if req.send_email:
        try:
            from src.alerts.email_alert import EmailAlert
            ea = EmailAlert(config_path=CONFIG_PATH)
            ea.send_risk_alert(req.risk_level, 0.85, ["Test alert"], force=True)
            email_ok = True
        except Exception as e:
            logger.warning("Email test échoué: %s", e)
    if req.send_slack:
        try:
            from src.alerts.slack_alert import SlackAlert
            sa = SlackAlert(config_path=CONFIG_PATH)
            sa.send_risk_alert(req.risk_level, 0.85, ["Test alert"], force=True)
            slack_ok = True
        except Exception as e:
            logger.warning("Slack test échoué: %s", e)
    return AlertTestResponse(email_sent=email_ok, slack_sent=slack_ok,
        message=f"Test alerte '{req.risk_level}' envoyé")

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
