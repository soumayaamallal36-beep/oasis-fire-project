"""
FireWatch Agdez - Schémas Pydantic pour l'API FastAPI
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator

class PredictionRequest(BaseModel):
    """Requête de prédiction de risque d'incendie."""
    temperature: float = Field(..., ge=-10, le=60, description="Température en °C")
    humidity: float = Field(..., ge=0, le=100, description="Humidité relative en %")
    wind_speed: float = Field(..., ge=0, le=200, description="Vitesse du vent en km/h")
    precipitation: float = Field(0.0, ge=0, description="Précipitations en mm")
    ndvi: float = Field(0.2, ge=0, le=1, description="NDVI (indice végétation)")
    lat: float = Field(30.6936, ge=27, le=36, description="Latitude")
    lon: float = Field(-6.4497, ge=-14, le=0, description="Longitude")
    elevation: Optional[float] = Field(1050.0, description="Altitude en m")
    season: Optional[int] = Field(None, ge=1, le=4, description="Saison (1=hiver, 4=automne)")

    class Config:
        json_schema_extra = {
            "example": {
                "temperature": 38.5, "humidity": 12.0, "wind_speed": 28.0,
                "precipitation": 0.0, "ndvi": 0.10, "lat": 30.6936, "lon": -6.4497
            }
        }

class PredictionResponse(BaseModel):
    """Réponse de prédiction."""
    risk_level: str
    risk_code: int
    confidence: float
    fwi: float
    factors: List[str]
    probabilities: Dict[str, float]
    timestamp: str
    model_version: str

class HealthResponse(BaseModel):
    """Réponse santé de l'API."""
    status: str
    model_version: str
    timestamp: str
    models_loaded: int

class HistoryEntry(BaseModel):
    """Entrée d'historique des prédictions."""
    id: int
    timestamp: str
    temperature: float
    humidity: float
    wind_speed: float
    risk_level: str
    confidence: float
    fwi: float

class AlertTestRequest(BaseModel):
    """Requête de test d'alerte."""
    risk_level: str = Field("Élevé", description="Niveau de risque à simuler")
    send_email: bool = Field(True)
    send_slack: bool = Field(True)

class AlertTestResponse(BaseModel):
    """Réponse de test d'alerte."""
    email_sent: bool
    slack_sent: bool
    message: str
