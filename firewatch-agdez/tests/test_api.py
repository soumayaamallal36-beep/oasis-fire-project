import pytest
from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_predict_success():
    payload = {
        "temperature": 35.0,
        "humidity": 20.0,
        "wind_speed": 15.0,
        "precipitation": 0.0,
        "ndvi": 0.15,
        "lat": 30.6936,
        "lon": -6.4497
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "risk_level" in data
    assert "confidence" in data

def test_predict_invalid_data():
    payload = {"temperature": 100.0} # Invalid > 60
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
